"""Composable providers with caching and fallback behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from homeafford.market.base import BaseMarketProvider
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.snapshot import MarketSnapshot


class MarketDataError(Exception):
    """Base error for market provider failures."""


class MarketDataUnavailable(MarketDataError):
    """Raised when a provider cannot supply market data for a query."""


@dataclass
class CachedMarketProvider(BaseMarketProvider):
    """Cache snapshots from an inner provider for a configurable TTL."""

    inner: MarketDataProvider
    ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))
    _cache: dict[tuple[int, str | None, int | None], tuple[MarketSnapshot, datetime]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    @property
    def name(self) -> str:
        return f"cached:{self.inner.name}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self.inner.capabilities

    def list_metros(self) -> tuple[str, ...] | None:
        return self.inner.list_metros()

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        normalized = normalize_query(query)
        key = (normalized.loan_term_years, normalized.metro_id, normalized.reference_year)
        now = datetime.now(timezone.utc)
        cached = self._cache.get(key)
        if cached is not None:
            snapshot, cached_at = cached
            if now - cached_at < self.ttl:
                return snapshot

        snapshot = self.inner.get_snapshot(query=normalized)
        self._cache[key] = (snapshot, now)
        return snapshot

    def invalidate(self, *, query: MarketQuery | None = None) -> None:
        """Drop cached entries for one query or the entire cache."""
        if query is None:
            self._cache.clear()
            return
        normalized = normalize_query(query)
        self._cache.pop(
            (normalized.loan_term_years, normalized.metro_id, normalized.reference_year),
            None,
        )


class FallbackMarketProvider(BaseMarketProvider):
    """Try providers in order until one returns a snapshot."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("providers must be non-empty")
        self._providers = providers

    @property
    def name(self) -> str:
        names = "+".join(provider.name for provider in self._providers)
        return f"fallback:{names}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        merged = ProviderCapabilities()
        for provider in self._providers:
            merged = merged.merged_with(provider.capabilities)
        return merged

    def list_metros(self) -> tuple[str, ...] | None:
        for provider in self._providers:
            metros = provider.list_metros()
            if metros is not None:
                return metros
        return None

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        normalized = normalize_query(query)
        errors: list[str] = []
        for provider in self._providers:
            try:
                return provider.get_snapshot(query=normalized)
            except MarketDataError as exc:
                errors.append(str(exc))
        raise MarketDataError(
            "all providers failed: " + "; ".join(errors) if errors else "no providers"
        )
