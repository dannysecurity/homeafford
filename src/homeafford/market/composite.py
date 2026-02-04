"""Composable providers with caching and fallback behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeafford.market.base import (
    BaseMarketProvider,
    DelegatingMarketProvider,
    provider_capabilities,
    provider_list_metros,
    provider_name,
)
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.errors import MarketDataError, MarketDataUnavailable
from homeafford.market.planner import plan_query, QuerySatisfiability
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.snapshot import MarketSnapshot

__all__ = [
    "CachedMarketProvider",
    "FallbackMarketProvider",
    "MarketDataError",
    "MarketDataUnavailable",
    "build_provider_stack",
]


class CachedMarketProvider(DelegatingMarketProvider):
    """Cache snapshots from an inner provider for a configurable TTL."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        ttl: timedelta | None = None,
    ) -> None:
        self._inner = inner
        self.ttl = ttl if ttl is not None else timedelta(hours=1)
        self._cache: dict[
            tuple[int, str | None, int | None],
            tuple[MarketSnapshot, datetime],
        ] = {}

    @property
    def inner(self) -> MarketDataProvider:
        return self._inner

    @property
    def name(self) -> str:
        return f"cached:{self.inner.name}"

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        key = query.cache_key()
        now = datetime.now(timezone.utc)
        cached = self._cache.get(key)
        if cached is not None:
            snapshot, cached_at = cached
            if now - cached_at < self.ttl:
                return snapshot

        inner_plan = plan_query(query, provider_capabilities(self.inner))
        snapshot = self.inner.get_snapshot(query=inner_plan.effective)
        self._cache[key] = (snapshot, now)
        return snapshot

    def invalidate(self, *, query: MarketQuery | None = None) -> None:
        """Drop cached entries for one query or the entire cache."""
        if query is None:
            self._cache.clear()
            return
        normalized = normalize_query(query)
        self._cache.pop(normalized.cache_key(), None)


def build_provider_stack(
    inner: MarketDataProvider,
    *,
    cache: bool = True,
    ttl: timedelta | None = None,
) -> MarketDataProvider:
    """Wrap a provider with optional caching for registry and factory use."""
    if not cache:
        return inner
    if ttl is None:
        return CachedMarketProvider(inner)
    return CachedMarketProvider(inner, ttl=ttl)


class FallbackMarketProvider(BaseMarketProvider):
    """Try providers in order until one returns a snapshot."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("providers must be non-empty")
        self._providers = providers

    @property
    def name(self) -> str:
        names = "+".join(provider_name(provider) for provider in self._providers)
        return f"fallback:{names}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        merged = ProviderCapabilities()
        for provider in self._providers:
            merged = merged.merged_with(provider_capabilities(provider))
        return merged

    def list_metros(self) -> tuple[str, ...] | None:
        for provider in self._providers:
            listed = provider_list_metros(provider)
            if listed is not None:
                return listed
        return None

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        errors: list[str] = []
        for provider in self._providers:
            query_plan = plan_query(query, provider_capabilities(provider))
            if query_plan.satisfiability == QuerySatisfiability.NONE:
                errors.append(
                    f"{provider_name(provider)!r} cannot satisfy query: "
                    + ", ".join(query_plan.dropped_fields)
                )
                continue
            try:
                return provider.get_snapshot(query=query)
            except MarketDataError as exc:
                errors.append(f"{provider_name(provider)!r}: {exc}")
        raise MarketDataError(
            "all providers failed: " + "; ".join(errors) if errors else "no providers"
        )
