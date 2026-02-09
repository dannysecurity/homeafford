"""Pluggable snapshot caches for market data providers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import MarketSnapshot

CacheKey = tuple[int, str | None, int | None]


@runtime_checkable
class SnapshotCache(Protocol):
    """Storage backend for cached market snapshots keyed by query dimensions."""

    def get(self, key: CacheKey) -> MarketSnapshot | None:
        """Return a cached snapshot when present and still valid."""
        ...

    def set(self, key: CacheKey, snapshot: MarketSnapshot) -> None:
        """Store a snapshot for the given query key."""
        ...

    def invalidate(self, key: CacheKey | None = None) -> None:
        """Drop one entry or clear the entire cache when key is None."""
        ...


class InMemorySnapshotCache:
    """TTL-backed in-process cache for market snapshots."""

    def __init__(self, *, ttl: timedelta | None = None) -> None:
        self.ttl = ttl if ttl is not None else timedelta(hours=1)
        self._entries: dict[CacheKey, tuple[MarketSnapshot, datetime]] = {}

    def get(self, key: CacheKey) -> MarketSnapshot | None:
        cached = self._entries.get(key)
        if cached is None:
            return None
        snapshot, cached_at = cached
        if datetime.now(timezone.utc) - cached_at >= self.ttl:
            self._entries.pop(key, None)
            return None
        return snapshot

    def set(self, key: CacheKey, snapshot: MarketSnapshot) -> None:
        self._entries[key] = (snapshot, datetime.now(timezone.utc))

    def invalidate(self, key: CacheKey | None = None) -> None:
        if key is None:
            self._entries.clear()
            return
        self._entries.pop(key, None)


class NullSnapshotCache:
    """No-op cache that never stores snapshots."""

    def get(self, key: CacheKey) -> MarketSnapshot | None:
        return None

    def set(self, key: CacheKey, snapshot: MarketSnapshot) -> None:
        return None

    def invalidate(self, key: CacheKey | None = None) -> None:
        return None


def cache_key_for_query(query: MarketQuery) -> CacheKey:
    """Return the canonical cache key for a market query."""
    return query.cache_key()
