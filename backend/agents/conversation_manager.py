"""
Core real-time conversation manager.

Orchestrates the full pipeline for a single active call:
  1. Receives final transcript from Deepgram STT
  2. Builds message history with agent system prompt
  3. Streams to Groq LLM
  4. Detects tool calls and executes them
  5. Streams text response tokens to Edge TTS
  6. Handles agent transfers (hot-swap system prompt + tools)
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, Callable, Awaitable

from agents.registry import get_system_prompt, get_tools, get_agent
from memory.session import session_manager
from services.llm_service import llm_service
from tools.router import execute_tool

logger = logging.getLogger(__name__)

# Sentinel prefix emitted by llm_service when a tool call is detected
TOOL_CALL_PREFIX = "__TOOL_CALL__:"


class ConversationManager:
    """
    Manages one active call's conversation state.

    Usage:
        manager = ConversationManager(call_id, on_text_chunk)
        await manager.start(customer_id="phone_or_id")
        await manager.handle_transcript("Hi, I'd like to book a demo")
        await manager.stop()
    """

    def __init__(
        self,
        call_id: str,
        on_text_chunk: Callable[[str], Awaitable[None]],
        on_agent_changed: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tts_flush: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> None:
        """
        Args:
            call_id:           Unique identifier for this call (LiveKit room name).
            on_text_chunk:     Async callback called with each text token for TTS.
            on_agent_changed:  Optional callback when agent is transferred.
            on_tts_flush:      Optional callback to flush TTS after responses.
        """
        self._call_id = call_id
        self._on_text = on_text_chunk
        self._on_agent_changed = on_agent_changed
        self._on_tts_flush = on_tts_flush
        self._lock = asyncio.Lock()  # Prevent concurrent LLM calls

    async def start(self, customer_id: Optional[str] = None) -> None:
        """Initialize session state for this call."""
        # Determine starting agent
        await session_manager.set_current_agent(self._call_id, "receptionist")

        # Fetch long-term customer context from DB if available
        customer_ctx: dict = {}
        if customer_id:
            from tools.crm import get_customer
            customer_ctx = await get_customer(customer_id) or {}
            await session_manager.set_customer_context(self._call_id, customer_ctx)

        # Initialize with system prompt (no user messages yet)
        agent_name = "receptionist"
        system_prompt = get_system_prompt(agent_name, customer_ctx)
        await session_manager.set_messages(
            self._call_id,
            [{"role": "system", "content": system_prompt}],
        )
        
        # Trigger initial greeting
        from memory.database import AsyncSessionFactory, AgentConfig
        from sqlalchemy import select
        async with AsyncSessionFactory() as session:
            result = await session.execute(select(AgentConfig).limit(1))
            cfg = result.scalar_one_or_none()
            greeting = cfg.greeting if cfg and cfg.greeting else "Hello! I'm your AI assistant. How can I help you today?"
            
        await self._on_text(greeting)
        await session_manager.append_message(
            self._call_id, {"role": "assistant", "content": greeting}
        )
        await session_manager.append_transcript(
            self._call_id, f"Agent ({agent_name}): {greeting}\n"
        )
        logger.info(f"✅ ConversationManager started: call={self._call_id}, agent={agent_name}")

    async def handle_transcript(self, text: str) -> None:
        """
        Called when Deepgram emits a final transcript.
        Runs the full LLM + tool-call + TTS pipeline.
        """
        if not text.strip():
            return

        async with self._lock:  # One response at a time
            try:
                await self._process_turn(text)
            except Exception as e:
                logger.error(f"❌ Conversation error on call {self._call_id}: {e}")
                await self._on_text("I'm sorry, I had a technical issue. Could you repeat that?")

    async def _process_turn(self, user_text: Optional[str] = None) -> None:
        """Run one full conversation turn."""
        # Append user message if provided
        if user_text is not None:
            await session_manager.append_message(
                self._call_id, {"role": "user", "content": user_text}
            )
            await session_manager.append_transcript(
                self._call_id, f"User: {user_text}\n"
            )

        # Get current state
        messages = await session_manager.get_messages(self._call_id)
        
        # Enforce sliding window (keep system prompt, retain last 12 messages)
        if len(messages) > 13:
            # messages[0] is system prompt
            messages = [messages[0]] + messages[-12:]
            
        agent_name = await session_manager.get_current_agent(self._call_id)
        tools = get_tools(agent_name)

        # Stream LLM response
        full_response = ""
        tool_call_data: Optional[str] = None

        async for chunk in llm_service.stream_response(messages, tools=tools):
            if chunk.startswith(TOOL_CALL_PREFIX):
                # Tool call detected — don't send to TTS
                tool_call_data = chunk[len(TOOL_CALL_PREFIX):]
            else:
                full_response += chunk
                # Stream to TTS in real-time
                await self._on_text(chunk)

        # If we got a text response, save it and flush TTS
        if full_response:
            await session_manager.append_message(
                self._call_id,
                {"role": "assistant", "content": full_response}
            )
            await session_manager.append_transcript(
                self._call_id, f"Agent ({agent_name}): {full_response}\n"
            )

        # Execute any tool call
        if tool_call_data:
            await self._handle_tool_call(tool_call_data, messages)

    async def _handle_tool_call(self, tool_call_json: str, messages: list) -> None:
        """Execute a tool, then generate the assistant's verbal response."""
        try:
            tc = json.loads(tool_call_json)
            tool_name: str = tc["name"]
            arguments: str = tc["arguments"]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"❌ Could not parse tool call: {e}")
            return

        logger.info(f"🔧 Tool call: {tool_name}")

        # Execute tool
        tool_result, is_transfer = await execute_tool(
            tool_name, arguments, self._call_id
        )

        # Add tool call + result to message history FIRST
        messages_now = await session_manager.get_messages(self._call_id)
        messages_now.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tool_0",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": arguments},
                }
            ],
        })
        messages_now.append({
            "role": "tool",
            "tool_call_id": "tool_0",
            "content": tool_result,
        })
        await session_manager.set_messages(self._call_id, messages_now)

        # Agent transfer
        if is_transfer:
            new_agent = tool_result  # router returns agent name for transfers
            current = await session_manager.get_current_agent(self._call_id)
            
            # Guard: prevent self-transfer loops
            if new_agent.lower() == current.lower():
                logger.warning(f"⚠️ Agent '{current}' tried to transfer to itself — blocking loop")
                # Replace tool messages with a nudge so the LLM helps directly
                messages_now = await session_manager.get_messages(self._call_id)
                # Remove the tool_call and tool result we just added
                messages_now = [m for m in messages_now if m.get("role") not in ("tool",) and not m.get("tool_calls")]
                messages_now.append({
                    "role": "system",
                    "content": f"You ARE the {get_agent(current)['name']}. Do NOT transfer. Help the user directly with their request."
                })
                await session_manager.set_messages(self._call_id, messages_now)
                # Re-run the turn so the agent actually responds
                await self._process_turn(None)
                if self._on_tts_flush:
                    await self._on_tts_flush()
                return
            
            await self._transfer_agent(new_agent)
            
            # Immediately generate the new agent's greeting/response!
            await self._process_turn(None)
            
            # Flush TTS after the transfer response
            if self._on_tts_flush:
                await self._on_tts_flush()
            return

        # Ask Groq to verbally confirm the action
        agent_name = await session_manager.get_current_agent(self._call_id)
        tools = get_tools(agent_name)
        verbal_response = ""
        
        # Enforce sliding window for the tool confirmation response
        if len(messages_now) > 13:
            messages_now = [messages_now[0]] + messages_now[-12:]
            
        async for chunk in llm_service.stream_response(messages_now, tools=tools):
            if not chunk.startswith(TOOL_CALL_PREFIX):
                verbal_response += chunk
                await self._on_text(chunk)

        if verbal_response:
            await session_manager.append_message(
                self._call_id,
                {"role": "assistant", "content": verbal_response}
            )
            await session_manager.append_transcript(
                self._call_id, f"Agent: {verbal_response}\n"
            )

    async def _transfer_agent(self, new_agent_name: str) -> None:
        """Hot-swap to a new agent persona."""
        agent_name = new_agent_name.lower()
        old_agent = await session_manager.get_current_agent(self._call_id)
        
        # Step 1: Send handoff message BEFORE swapping (so it's attributed to old agent)
        handoff_msg = f"Let me connect you with our {get_agent(agent_name)['name']} right away."
        await self._on_text(handoff_msg)
        await session_manager.append_message(
            self._call_id,
            {"role": "assistant", "content": handoff_msg}
        )
        await session_manager.append_transcript(
            self._call_id, f"Agent ({old_agent}): {handoff_msg}\n"
        )
        
        # Flush TTS so handoff message is spoken before voice changes
        if self._on_tts_flush:
            await self._on_tts_flush()
        
        # Step 2: Swap agent identity (system prompt + voice)
        customer_ctx = await session_manager.get_customer_context(self._call_id)
        new_system_prompt = get_system_prompt(agent_name, customer_ctx)

        # Step 3: Clean up message history for the new agent
        # Strip tool_call and tool messages — they confuse Groq/Llama models
        # and cause the new agent to re-execute the transfer tool.
        messages = await session_manager.get_messages(self._call_id)
        clean_messages = []
        for msg in messages:
            role = msg.get("role")
            # Skip tool_call messages (assistant with tool_calls and no content)
            if role == "assistant" and msg.get("tool_calls"):
                continue
            # Skip tool result messages
            if role == "tool":
                continue
            # Skip old injected system messages (not the first one)
            if role == "system" and msg != messages[0]:
                continue
            clean_messages.append(msg)
        
        # Replace the system prompt
        if clean_messages and clean_messages[0]["role"] == "system":
            clean_messages[0]["content"] = new_system_prompt
        else:
            clean_messages.insert(0, {"role": "system", "content": new_system_prompt})
        
        # Add transfer context so the new agent knows what happened
        clean_messages.append({
            "role": "system",
            "content": (
                f"The call was just transferred to you from the {get_agent(old_agent)['name']}. "
                f"You are now the {get_agent(agent_name)['name']}. "
                "Introduce yourself briefly and immediately help the user with their last request. "
                "Do NOT transfer the call again — you are the correct agent for this. "
                "Do NOT ask the user to repeat themselves."
            )
        })
        
        await session_manager.set_messages(self._call_id, clean_messages)
        await session_manager.set_current_agent(self._call_id, agent_name)

        if self._on_agent_changed:
            await self._on_agent_changed(agent_name)

        logger.info(f"🔀 Agent transferred: {old_agent} → {agent_name}")

    async def stop(self) -> str:
        """Return the full call transcript and clean up."""
        transcript = await session_manager.get_transcript(self._call_id)
        logger.info(f"✅ ConversationManager stopped: call={self._call_id}")
        return transcript
