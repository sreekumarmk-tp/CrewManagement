"""
Redis cache-aside helper (Step 3 of the caching plan).

A thin async wrapper over ``redis.asyncio`` used to cache slow-changing crew-list
queries. Every operation degrades gracefully: if Redis is unreachable,
misconfigured, or the ``redis`` package isn't installed, reads return ``None``
(treated as a cache miss) and writes/deletes are no-ops — so callers transparently
fall back to the database. The cache is an optimization, never a hard dependency.

The client is created lazily on first use and reused (it owns a connection pool),
so importing this module never opens a socket. ``close()`` is called from the app
lifespan on shutdown.
"""
import json
from typing import Any, Optional

import structlog

from config import settings

log = structlog.get_logger()

try:  # redis is optional — the app must boot/run even if it's absent or unreachable
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover - import guard
    aioredis = None


class CacheService:
    """Best-effort JSON cache over Redis. All ops swallow connection errors."""

    def __init__(self) -> None:
        self._client = None
        self._disabled = aioredis is None  # redis package not installed → no-op mode
        self._warned = False
        # Step 3 observability — counted in get_json and surfaced via stats().
        self._hits = 0
        self._misses = 0
        self._errors = 0

    def _get_client(self):
        if self._disabled:
            return None
        if self._client is None:
            try:
                # Short timeouts so a missing/slow Redis can't stall a request — on
                # any failure we fall through to the DB rather than block.
                self._client = aioredis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
            except Exception as exc:  # bad URL / construction error → disable permanently
                self._note_unavailable(exc)
                self._disabled = True
                return None
        return self._client

    def _note_unavailable(self, exc: Exception) -> None:
        # Log the first failure only, so a down Redis doesn't flood the logs. The
        # gate resets on the next successful write so a recovery is logged once too.
        if not self._warned:
            log.warning("cache.unavailable", error=str(exc))
            self._warned = True

    async def get_json(self, key: str) -> Optional[Any]:
        """Return the cached value for ``key``, or ``None`` on miss/error."""
        client = self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
        except Exception as exc:
            self._errors += 1
            self._note_unavailable(exc)
            return None
        if raw is None:
            self._misses += 1
            return None
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            self._misses += 1  # corrupt entry — treat as a miss
            return None
        self._hits += 1
        return value

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Cache ``value`` (JSON-encoded) under ``key`` with a TTL. No-op on error."""
        client = self._get_client()
        if client is None:
            return
        try:
            await client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
            if self._warned:
                log.info("cache.recovered")
                self._warned = False
        except Exception as exc:
            self._note_unavailable(exc)

    async def delete(self, *keys: str) -> None:
        """Invalidate one or more keys. No-op on error or when no keys given."""
        client = self._get_client()
        if client is None or not keys:
            return
        try:
            await client.delete(*keys)
        except Exception as exc:
            self._note_unavailable(exc)

    def stats(self) -> dict:
        """Hit/miss/error counters for monitoring (Step 3). ``hit_rate`` is over
        actual lookups (hits + misses); errors are counted separately since they
        fall through to the DB rather than being a true cache miss."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "hit_rate": round(self._hits / total * 100, 1) if total else 0.0,
            "available": not self._disabled,
        }

    async def close(self) -> None:
        """Close the connection pool (called from the app lifespan on shutdown)."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None


# Module-level singleton, mirroring state_service.
cache_service = CacheService()
