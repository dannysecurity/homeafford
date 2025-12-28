"""Composable providers with caching and fallback behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from homeafford.market.protocol import MarketDataProvider
from homeafford.market.snapshot import MarketSnapshot


class MarketDataError(Exception):
    """Raised when no provider in a chain can supply market data."""


@dataclass
class CachedMarketProvider:
    """Cache snapshots from an inner provider for a configurable TTL."""

    inner: MarketDataProvider
    ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))
    _cached: MarketSnapshot | None = field(default=None, init=False, repr=False)
    _cached_at: datetime | None = field(default=None, init=False, repr=False)

    def get_snapshot(self, *, loan_term_years: int = 30) -> MarketSnapshot:
        now = datetime.now(timezone.utc)
        if (
            self._cached is not None
            and self._cached_at is not None
            and now - self._cached_at < self.ttl
        ):
            return self._cached

        snapshot = self.inner.get_snapshot(loan_term_years=loan_term_years)
        self._cached = snapshot
        self._cached_at = now
        return snapshot


class FallbackMarketProvider:
    """Try providers in order until one returns a snapshot."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("providers must be non-empty")
        self._providers = providers

    def get_snapshot(self, *, loan_term_years: int = 30) -> MarketSnapshot:
        errors: list[str] = []
        for provider in self._providers:
            try:
                return provider.get_snapshot(loan_term_years=loan_term_years)
            except Exception as exc:  # noqa: BLE001 — collect and try next provider
                errors.append(str(exc))
        raise MarketDataError(
            "all providers failed: " + "; ".join(errors) if errors else "no providers"
        )
