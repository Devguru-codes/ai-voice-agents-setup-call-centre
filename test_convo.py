import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from backend.agents.conversation_manager import ConversationManager
from backend.services.session_manager import get_messages

async def main():
    print("Testing ConversationManager...")
    
    # Mock callbacks
    async def on_text_chunk(text: str):
        print(f"[Assistant] {text}", end="", flush=True)
        
    async def on_agent_changed(agent_name: str):
        print(f"\n[Agent Switched] -> {agent_name}")
        
    manager = ConversationManager(
        call_id="test_call_123",
        on_text_chunk=on_text_chunk,
        on_agent_changed=on_agent_changed
    )
    
    await manager.start(customer_id="test_user")
    
    print("\n\n--- Turn 1: User says hello ---")
    await manager.handle_transcript("Hello, I need some help.")
    print("\n")
    
    print("\n--- Turn 2: User asks for support ---")
    await manager.handle_transcript("I want to know how to use that GPT.")
    print("\n")
    
    print("\n--- Turn 3: User says something else ---")
    await manager.handle_transcript("Are you there?")
    print("\n")
    
    messages = await get_messages("test_call_123")
    print("\n--- Final Message History ---")
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            print(f"[{role}] (Tool Calls: {tool_calls})")
        else:
            print(f"[{role}] {content}")
            
if __name__ == "__main__":
    asyncio.run(main())
