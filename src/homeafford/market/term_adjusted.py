"""Loan-term mortgage rate spreads as a composable rate source and provider wrapper."""

from __future__ import annotations

from homeafford.market.base import DelegatingMarketProvider, fetch_provider_snapshot
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.planner import QueryPolicy
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import MarketSnapshot
from homeafford.market.sources import RateAssumptions, RateDataSource

DEFAULT_TERM_SPREADS: dict[int, float] = {
    15: -0.005,
    20: -0.0025,
    30: 0.0,
}


def term_spread_for_query(
    query: MarketQuery,
    term_spreads: dict[int, float],
) -> float:
    """Return the mortgage rate spread for the query's loan term, if any."""
    return term_spreads.get(query.loan_term_years, 0.0)


def apply_term_spread_to_rates(
    rates: RateAssumptions,
    *,
    query: MarketQuery,
    term_spreads: dict[int, float],
) -> RateAssumptions:
    """Apply a loan-term spread to rate assumptions when the term is configured."""
    spread = term_spread_for_query(query, term_spreads)
    if spread == 0.0:
        return rates
    return RateAssumptions(
        mortgage_rate=rates.mortgage_rate + spread,
        property_tax_rate=rates.property_tax_rate,
        insurance_annual=rates.insurance_annual,
        pmi_annual_rate=rates.pmi_annual_rate,
        pmi_ltv_threshold=rates.pmi_ltv_threshold,
        source=f"{rates.source}+{query.loan_term_years}yr",
    )


class TermAdjustedRateSource:
    """Rate source that applies loan-term spreads on top of an inner source."""

    name = "term-adjusted-rate"
    supports_term_rates = True

    def __init__(
        self,
        inner: RateDataSource,
        *,
        term_spreads: dict[int, float] | None = None,
    ) -> None:
        self._inner = inner
        self._term_spreads = dict(term_spreads or DEFAULT_TERM_SPREADS)

    @property
    def inner(self) -> RateDataSource:
        """Wrapped rate source receiving delegated fetches."""
        return self._inner

    @property
    def term_spreads(self) -> dict[int, float]:
        """Configured loan-term mortgage rate spreads."""
        return dict(self._term_spreads)

    def fetch_rates(self, *, query: MarketQuery) -> RateAssumptions:
        rates = self._inner.fetch_rates(query=query)
        return apply_term_spread_to_rates(
            rates,
            query=query,
            term_spreads=self._term_spreads,
        )


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
    def term_spreads(self) -> dict[int, float]:
        """Configured loan-term mortgage rate spreads."""
        return dict(self._term_spreads)

    @property
    def name(self) -> str:
        return self.wrapper_name("term-adjusted")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self.inner.capabilities.merged_with(
            ProviderCapabilities(supports_term_rates=True),
        )

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        snapshot = fetch_provider_snapshot(self.inner, query, policy=QueryPolicy.DEGRADE)
        spread = term_spread_for_query(query, self._term_spreads)
        if spread == 0.0:
            return snapshot
        return snapshot.with_overrides(
            mortgage_rate=snapshot.mortgage_rate + spread,
            source=f"{snapshot.source}+{query.loan_term_years}yr",
        )
