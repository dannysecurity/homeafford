"""Provider wrapper that adjusts mortgage rates by loan term."""

from __future__ import annotations

from homeafford.market.base import DelegatingMarketProvider, fetch_provider_snapshot
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.planner import QueryPolicy
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import MarketSnapshot

DEFAULT_TERM_SPREADS: dict[int, float] = {
    15: -0.005,
    20: -0.0025,
    30: 0.0,
}


class TermAdjustedMarketProvider(DelegatingMarketProvider):
    """Apply term-specific mortgage rate spreads on top of an inner provider."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        term_spreads: dict[int, float] | None = None,
    ) -> None:
        self._inner = inner
        self._term_spreads = dict(term_spreads or DEFAULT_TERM_SPREADS)

    @property
    def inner(self) -> MarketDataProvider:
        return self._inner

    @property
    def name(self) -> str:
        return f"term-adjusted:{self.inner.name}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self.inner.capabilities.merged_with(
            ProviderCapabilities(supports_term_rates=True),
        )

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        snapshot = fetch_provider_snapshot(self.inner, query, policy=QueryPolicy.DEGRADE)
        spread = self._term_spreads.get(query.loan_term_years, 0.0)
        if spread == 0.0:
            return snapshot
        adjusted_rate = snapshot.mortgage_rate + spread
        return snapshot.with_overrides(
            mortgage_rate=adjusted_rate,
            source=f"{snapshot.source}+{query.loan_term_years}yr",
        )
