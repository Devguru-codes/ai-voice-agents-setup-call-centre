"""
Redis-backed short-term session memory.

Stores per-call conversation state: messages, current agent,
tool call results. Each key expires after 2 hours automatically.
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

import config

logger = logging.getLogger(__name__)

SESSION_TTL = 7200  # 2 hours in seconds


class SessionManager:
    """Manages real-time call state in Redis."""

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Initialize the Redis connection pool."""
        try:
            self._redis = aioredis.from_url(
                config.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            await self._redis.ping()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.aclose()

    # ── Low-level helpers ────────────────────────────────────────────────────

    def _key(self, call_id: str, suffix: str) -> str:
        return f"call:{call_id}:{suffix}"

    async def _get(self, key: str) -> Any:
        if not self._redis:
            raise RuntimeError("SessionManager not connected")
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def _set(self, key: str, value: Any) -> None:
        if not self._redis:
            raise RuntimeError("SessionManager not connected")
        await self._redis.setex(key, SESSION_TTL, json.dumps(value, default=str))

    # ── Conversation history ─────────────────────────────────────────────────

    async def get_messages(self, call_id: str) -> list[dict]:
        """Return the full message list for a call (OpenAI format)."""
        data = await self._get(self._key(call_id, "messages"))
        return data or []

    async def append_message(self, call_id: str, message: dict) -> None:
        """Append a single message and refresh TTL."""
        messages = await self.get_messages(call_id)
        messages.append(message)
        await self._set(self._key(call_id, "messages"), messages)

    async def set_messages(self, call_id: str, messages: list[dict]) -> None:
        await self._set(self._key(call_id, "messages"), messages)

    # ── Current agent ────────────────────────────────────────────────────────

    async def get_current_agent(self, call_id: str) -> str:
        data = await self._get(self._key(call_id, "agent"))
        return data or "receptionist"

    async def set_current_agent(self, call_id: str, agent_name: str) -> None:
        await self._set(self._key(call_id, "agent"), agent_name)

    # ── Customer context ─────────────────────────────────────────────────────

    async def get_customer_context(self, call_id: str) -> dict:
        data = await self._get(self._key(call_id, "customer"))
        return data or {}

    async def set_customer_context(self, call_id: str, ctx: dict) -> None:
        await self._set(self._key(call_id, "customer"), ctx)

    # ── Partial transcript (for streaming) ───────────────────────────────────

    async def append_transcript(self, call_id: str, chunk: str) -> None:
        key = self._key(call_id, "transcript")
        current = await self._redis.get(key) or ""  # type: ignore[union-attr]
        await self._redis.setex(key, SESSION_TTL, current + chunk)

    async def get_transcript(self, call_id: str) -> str:
        raw = await self._redis.get(self._key(call_id, "transcript"))  # type: ignore[union-attr]
        return raw or ""

    # ── Cleanup ──────────────────────────────────────────────────────────────

    async def delete_session(self, call_id: str) -> None:
        """Delete all keys for a finished call."""
        pattern = self._key(call_id, "*")
        keys = await self._redis.keys(pattern)  # type: ignore[union-attr]
        if keys:
            await self._redis.delete(*keys)  # type: ignore[union-attr]
        logger.info(f"🗑️ Session deleted: {call_id}")


# Global singleton (connected on app startup)
session_manager = SessionManager()
