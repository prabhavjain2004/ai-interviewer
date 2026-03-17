"""
api/deps.py
-----------
FastAPI dependency injectors.
Redis, ChromaDB, and API key are app-level singletons injected via request state.
"""

from __future__ import annotations

from fastapi import Request

from services.redis_client import RedisClient
from services.chroma_client import ChromaClient


def get_redis(request: Request) -> RedisClient:
    return request.app.state.redis


def get_chroma(request: Request) -> ChromaClient:
    return request.app.state.chroma


def get_api_key(request: Request) -> str:
    return request.app.state.gemini_api_key
