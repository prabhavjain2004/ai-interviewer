"""
services/redis_client.py
------------------------
Redis connection + session state persistence.

All session state lives here — workers are fully stateless (architecture.md §6).
24-hour TTL on all keys — auto-expires, no manual cleanup (architecture.md §7).
Async throughout using Upstash Redis REST API (rules.md §7).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from upstash_redis.asyncio import Redis

logger = logging.getLogger(__name__)

DEFAULT_TTL = 86400  # 24 hours in seconds


class RedisClient:
    """
    Thin async wrapper around Upstash Redis REST API.
    One instance shared across the app (created in main.py lifespan).
    """

    def __init__(self, url: str, token: str, ttl: int = DEFAULT_TTL) -> None:
        self._url = url
        self._token = token
        self._ttl = ttl
        self._redis: Redis | None = None

    async def connect(self) -> None:
        try:
            self._redis = Redis(url=self._url, token=self._token)
            await self._redis.ping()
            logger.info("Upstash Redis connected | url=%s", self._url)
        except Exception as e:
            logger.error("Failed to connect to Upstash Redis: %s", e)
            raise

    async def disconnect(self) -> None:
        if self._redis:
            # Upstash Redis client doesn't require explicit disconnect
            logger.info("Upstash Redis disconnected.")

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def set_json(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        """Serialise dict to JSON and store with TTL."""
        assert self._redis, "Redis not connected."
        await self._redis.set(
            key,
            json.dumps(value, default=str),
            ex=ttl or self._ttl,
        )

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve and deserialise JSON. Returns None if key missing."""
        assert self._redis, "Redis not connected."
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def delete(self, key: str) -> None:
        assert self._redis, "Redis not connected."
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        assert self._redis, "Redis not connected."
        return bool(await self._redis.exists(key))

    async def refresh_ttl(self, key: str, ttl: int | None = None) -> None:
        """Reset TTL on an existing key (e.g. on session activity)."""
        assert self._redis, "Redis not connected."
        await self._redis.expire(key, ttl or self._ttl)

    # ------------------------------------------------------------------
    # Session-specific helpers
    # ------------------------------------------------------------------

    def state_key(self, session_id: str) -> str:
        return f"session:{session_id}:state"

    def report_key(self, session_id: str) -> str:
        return f"session:{session_id}:report"

    async def save_state(self, session_id: str, state: dict[str, Any]) -> None:
        await self.set_json(self.state_key(session_id), state)

    async def load_state(self, session_id: str) -> dict[str, Any] | None:
        return await self.get_json(self.state_key(session_id))

    async def save_report(self, session_id: str, report: dict[str, Any]) -> None:
        await self.set_json(self.report_key(session_id), report)

    async def load_report(self, session_id: str) -> dict[str, Any] | None:
        return await self.get_json(self.report_key(session_id))

    async def delete_session(self, session_id: str) -> None:
        """Removes both state and report keys for a session."""
        await self.delete(self.state_key(session_id))
        await self.delete(self.report_key(session_id))
        logger.info("Session data deleted from Redis | session=%s", session_id)
