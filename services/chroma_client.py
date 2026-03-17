"""
services/chroma_client.py
--------------------------
ChromaDB per-session resume RAG.

Each session gets its own collection namespaced by session_id.
Used by core/parser.py to embed resume chunks for context retrieval.
Collections are cleaned up on session delete (TTL-based via Redis expiry signal).
Async-compatible via run_in_executor for ChromaDB's sync client (rules.md §7).
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Chunk size for splitting resume text into embeddable segments
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Simple sliding-window text chunker."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


class ChromaClient:
    """
    Thin async wrapper around chromadb.HttpClient.
    One instance shared across the app (created in main.py lifespan).
    ChromaDB's Python client is synchronous — all calls run in a thread executor.
    """

    def __init__(self, host: str = "localhost", port: int = 8000) -> None:
        self._host = host
        self._port = port
        self._client: chromadb.HttpClient | None = None

    def connect(self) -> None:
        """
        Connects to ChromaDB. Uses HttpClient if host is reachable,
        falls back to in-memory EphemeralClient for local dev/testing.
        """
        try:
            self._client = chromadb.HttpClient(
                host=self._host,
                port=self._port,
                settings=Settings(anonymized_telemetry=False),
            )
            # Test connection
            self._client.heartbeat()
            logger.info("ChromaDB connected (HTTP) | host=%s:%d", self._host, self._port)
        except Exception:
            logger.warning(
                "ChromaDB HTTP unavailable — falling back to in-memory client (dev mode)"
            )
            self._client = chromadb.EphemeralClient(
                settings=Settings(anonymized_telemetry=False)
            )

    def disconnect(self) -> None:
        self._client = None

    def _collection_name(self, session_id: str) -> str:
        # ChromaDB collection names: alphanumeric + underscores only
        return f"resume_{session_id.replace('-', '_')}"

    async def _run(self, fn, *args, **kwargs):
        """Run a sync ChromaDB call in the default thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # ------------------------------------------------------------------
    # Resume embedding
    # ------------------------------------------------------------------

    async def embed_resume(self, session_id: str, raw_text: str) -> None:
        """
        Chunks the resume text and upserts into a per-session ChromaDB collection.
        Called once after core/parser.py returns a ResumeProfile.
        """
        assert self._client, "ChromaDB not connected."
        collection_name = self._collection_name(session_id)

        chunks = _chunk_text(raw_text)
        ids = [f"{session_id}_chunk_{i}" for i in range(len(chunks))]

        def _upsert():
            collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"session_id": session_id},
            )
            collection.upsert(
                documents=chunks,
                ids=ids,
            )

        await self._run(_upsert)
        logger.info(
            "Resume embedded | session=%s | chunks=%d", session_id, len(chunks)
        )

    async def query_resume(
        self,
        session_id: str,
        query: str,
        n_results: int = 3,
    ) -> list[str]:
        """
        Retrieves the top-n most relevant resume chunks for a given query.
        Used by the Interviewer to ground questions in resume context.
        Returns list of text chunks (empty list if collection not found).
        """
        assert self._client, "ChromaDB not connected."
        collection_name = self._collection_name(session_id)

        def _query():
            try:
                collection = self._client.get_collection(collection_name)
                results = collection.query(
                    query_texts=[query],
                    n_results=min(n_results, collection.count()),
                )
                return results.get("documents", [[]])[0]
            except Exception:
                return []

        chunks = await self._run(_query)
        return chunks

    async def delete_session_collection(self, session_id: str) -> None:
        """
        Deletes the ChromaDB collection for a session.
        Called on session cleanup (after Redis TTL expiry or explicit delete).
        """
        assert self._client, "ChromaDB not connected."
        collection_name = self._collection_name(session_id)

        def _delete():
            try:
                self._client.delete_collection(collection_name)
                logger.info("ChromaDB collection deleted | session=%s", session_id)
            except Exception as e:
                logger.warning(
                    "ChromaDB collection delete failed | session=%s | error=%s",
                    session_id, e,
                )

        await self._run(_delete)
