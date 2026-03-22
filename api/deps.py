"""
api/deps.py
-----------
FastAPI dependency injectors.
Redis and API key are app-level singletons injected via request state.
"""

from __future__ import annotations

from fastapi import Request

from services.redis_client import RedisClient


def get_redis(request: Request) -> RedisClient:
    return request.app.state.redis


def get_api_key(request: Request) -> str:
    return request.app.state.gemini_api_key
