"""
Dual-backend LLM service (Groq + Ollama Fallback).

Supports:
  - Streaming text responses (for low-latency TTS pipeline)
  - Tool/function calling
  - Primary inference via Groq, fallback to local Ollama on failure/limits
"""
import json
import logging
from typing import AsyncGenerator, Optional

from groq import AsyncGroq, APIStatusError
from ollama import AsyncClient as OllamaAsyncClient, ResponseError as OllamaResponseError

import config

logger = logging.getLogger(__name__)


class LLMService:
    """Wraps Groq async client with fallback to Ollama async client."""

    def __init__(self) -> None:
        # Groq Setup
        self._groq_keys = config.GROQ_API_KEYS
        self._key_index = 0
        self._groq_clients: dict[str, AsyncGroq] = {}
        
        # Ollama Setup
        self._ollama_client = OllamaAsyncClient(host=config.OLLAMA_HOST)

    # ── Groq Helpers ─────────────────────────────────────────────────────────
    @property
    def _current_groq_key(self) -> str:
        if not self._groq_keys:
            return ""
        return self._groq_keys[self._key_index % len(self._groq_keys)]

    def _get_groq_client(self, key: Optional[str] = None) -> Optional[AsyncGroq]:
        k = key or self._current_groq_key
        if not k:
            return None
        if k not in self._groq_clients:
            self._groq_clients[k] = AsyncGroq(api_key=k)
        return self._groq_clients[k]

    def _rotate_groq_key(self) -> bool:
        if len(self._groq_keys) <= 1:
            return False
        self._key_index = (self._key_index + 1) % len(self._groq_keys)
        logger.warning(f"🔄 Rotated to Groq key #{self._key_index + 1}")
        return True

    # ── Streaming text ────────────────────────────────────────────────────────

    async def stream_response(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream text tokens. Tries Groq first (with key rotation), 
        falls back to Ollama on exhaustion.
        Yields special sentinel '__TOOL_CALL__:{json}' for tools.
        """
        
        # 1. Try Groq
        if self._groq_keys:
            groq_model = model or config.GROQ_MODEL
            attempts = len(self._groq_keys)
            
            for attempt in range(attempts):
                try:
                    kwargs: dict = dict(
                        model=groq_model,
                        messages=messages,
                        temperature=0.4,
                        max_tokens=1024,
                        stream=True,
                    )
                    if tools:
                        kwargs["tools"] = tools
                        kwargs["tool_choice"] = "auto"

                    client = self._get_groq_client()
                    if not client:
                        break
                        
                    tool_call_acc: dict[int, dict] = {}
                    
                    stream = await client.chat.completions.create(**kwargs)
                    async for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta is None:
                            continue

                        if delta.content:
                            yield delta.content

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_call_acc:
                                    tool_call_acc[idx] = {"name": "", "arguments": ""}
                                if tc.function.name:
                                    tool_call_acc[idx]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_call_acc[idx]["arguments"] += tc.function.arguments

                    for tc in tool_call_acc.values():
                        yield f"__TOOL_CALL__:{json.dumps(tc)}"
                    
                    return  # Success with Groq

                except APIStatusError as e:
                    if e.status_code == 429 and self._rotate_groq_key():
                        continue
                    logger.error(f"❌ Groq error ({e.status_code}): {e.message}. Falling back to Ollama.")
                    break # Fall back to Ollama
                except Exception as e:
                    logger.error(f"❌ Groq stream error: {e}. Falling back to Ollama.")
                    break # Fall back to Ollama

        # 2. Fallback to Ollama
        logger.warning("🔄 Using Ollama fallback for streaming inference...")
        ollama_model = model or config.OLLAMA_MODEL
        try:
            kwargs = dict(
                model=ollama_model,
                messages=messages,
                stream=True,
                options={"temperature": 0.4}
            )
            if tools:
                kwargs["tools"] = tools

            async for chunk in await self._ollama_client.chat(**kwargs):
                content = chunk.get("message", {}).get("content")
                if content:
                    yield content

                tool_calls = chunk.get("message", {}).get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        name = tc.get("function", {}).get("name", "")
                        args = tc.get("function", {}).get("arguments", {})
                        
                        formatted_tc = {
                            "name": name,
                            "arguments": json.dumps(args) if isinstance(args, dict) else args
                        }
                        yield f"__TOOL_CALL__:{json.dumps(formatted_tc)}"

        except OllamaResponseError as e:
            logger.error(f"❌ Ollama API error ({e.status_code}): {e.error}")
            raise
        except Exception as e:
            logger.error(f"❌ Ollama stream error: {e}")
            raise


    # ── Non-streaming (analytics, post-call) ─────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        response_format: Optional[dict] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Non-streaming completion. Tries Groq, falls back to Ollama.
        """
        # 1. Try Groq
        if self._groq_keys:
            groq_model = model or config.GROQ_MODEL
            attempts = len(self._groq_keys)
            
            for attempt in range(attempts):
                try:
                    client = self._get_groq_client()
                    if not client: break
                    
                    kwargs: dict = dict(
                        model=groq_model,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=2048,
                    )
                    if response_format:
                        kwargs["response_format"] = response_format

                    response = await client.chat.completions.create(**kwargs)
                    return response.choices[0].message.content or ""

                except APIStatusError as e:
                    if e.status_code == 429 and self._rotate_groq_key():
                        continue
                    logger.error(f"❌ Groq completion error ({e.status_code}). Falling back to Ollama.")
                    break
                except Exception as e:
                    logger.error(f"❌ Groq complete error: {e}. Falling back to Ollama.")
                    break

        # 2. Fallback to Ollama
        logger.warning("🔄 Using Ollama fallback for completion inference...")
        ollama_model = model or config.OLLAMA_MODEL
        try:
            kwargs = dict(
                model=ollama_model,
                messages=messages,
                stream=False,
                options={"temperature": 0.2, "num_predict": 2048}
            )
            if response_format and response_format.get("type") == "json_object":
                kwargs["format"] = "json"

            response = await self._ollama_client.chat(**kwargs)
            return response.get("message", {}).get("content", "")

        except OllamaResponseError as e:
            logger.error(f"❌ Ollama completion error ({e.status_code}): {e.error}")
            raise
        except Exception as e:
            logger.error(f"❌ Ollama complete error: {e}")
            raise

# Global singleton
llm_service = LLMService()
