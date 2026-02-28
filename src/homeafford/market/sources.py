"""Dimension-specific data source protocols for market assumptions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.metro_prices import (
    DEFAULT_CSV_PATH,
    index_metro_rows,
    list_metro_ids,
    load_metro_price_trends,
    select_metro_row,
)
from homeafford.market.planner import QueryPolicy
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot


@dataclass(frozen=True)
class RateAssumptions:
    """Mortgage, tax, insurance, and PMI assumptions."""

    mortgage_rate: float
    property_tax_rate: float
    insurance_annual: float
    pmi_annual_rate: float = 0.005
    pmi_ltv_threshold: float = 0.80
    source: str = "static"


@dataclass(frozen=True)
class MetroPriceAssumptions:
    """Metro-specific home price data."""

    metro_id: str
    metro_name: str
    median_home_price: float
    source: str


@dataclass(frozen=True)
class SavingsReturnAssumptions:
    """Investment return assumptions used by savings projections."""

    savings_annual_return: float
    source: str = "static"


@runtime_checkable
class RateDataSource(Protocol):
    """Source for mortgage, tax, insurance, and PMI assumptions."""

    def fetch_rates(self, *, query: MarketQuery) -> RateAssumptions:
        """Return rate assumptions for the given query context."""
        ...


@runtime_checkable
class MetroPriceDataSource(Protocol):
    """Source for metro-specific median home prices."""

    def list_metros(self) -> tuple[str, ...]:
        """Return supported metro IDs."""
        ...

    def fetch_metro_price(
        self,
        *,
        metro_id: str,
        reference_year: int | None,
    ) -> MetroPriceAssumptions:
        """Return price data for one metro and optional reference year."""
        ...


@runtime_checkable
class SavingsReturnDataSource(Protocol):
    """Source for savings/investment return assumptions."""

    def fetch_savings_return(self, *, query: MarketQuery) -> SavingsReturnAssumptions:
        """Return savings return assumptions for the given query context."""
        ...


def rate_source_capabilities(source: RateDataSource) -> ProviderCapabilities:
    """Return query capabilities implied by a rate data source."""
    supports_term = getattr(source, "supports_term_rates", False)
    return ProviderCapabilities(supports_term_rates=supports_term)


def metro_source_capabilities(_source: MetroPriceDataSource) -> ProviderCapabilities:
    """Return query capabilities implied by a metro price data source."""
    return ProviderCapabilities(
        supports_metro_pricing=True,
        supports_reference_year=True,
    )


def savings_source_capabilities(_source: SavingsReturnDataSource) -> ProviderCapabilities:
    """Return query capabilities implied by a savings return data source."""
    return ProviderCapabilities()


def merge_source_capabilities(*sources: object | None) -> ProviderCapabilities:
    """Merge capabilities from configured dimension sources."""
    caps = ProviderCapabilities()
    for source in sources:
        if source is None:
            continue
        if isinstance(source, RateDataSource):
            caps = caps.merged_with(rate_source_capabilities(source))
        elif isinstance(source, MetroPriceDataSource):
            caps = caps.merged_with(metro_source_capabilities(source))
        elif isinstance(source, SavingsReturnDataSource):
            caps = caps.merged_with(savings_source_capabilities(source))
    return caps


def rate_assumptions_from_snapshot(snapshot: MarketSnapshot) -> RateAssumptions:
    """Extract rate assumptions from a full market snapshot."""
    return RateAssumptions(
        mortgage_rate=snapshot.mortgage_rate,
        property_tax_rate=snapshot.property_tax_rate,
        insurance_annual=snapshot.insurance_annual,
        pmi_annual_rate=snapshot.pmi_annual_rate,
        pmi_ltv_threshold=snapshot.pmi_ltv_threshold,
        source=snapshot.source,
    )


def savings_assumptions_from_snapshot(snapshot: MarketSnapshot) -> SavingsReturnAssumptions:
    """Extract savings return assumptions from a full market snapshot."""
    return SavingsReturnAssumptions(
        savings_annual_return=snapshot.savings_annual_return,
        source=snapshot.source,
    )


class StaticRateSource:
    """Return fixed rate assumptions regardless of query context."""

    def __init__(self, snapshot: MarketSnapshot = DEFAULT_MARKET) -> None:
        self._snapshot = snapshot

    def fetch_rates(self, *, query: MarketQuery) -> RateAssumptions:
        return rate_assumptions_from_snapshot(self._snapshot)


class StaticSavingsReturnSource:
    """Return fixed savings return assumptions regardless of query context."""

    def __init__(self, snapshot: MarketSnapshot = DEFAULT_MARKET) -> None:
        self._snapshot = snapshot

    def fetch_savings_return(self, *, query: MarketQuery) -> SavingsReturnAssumptions:
        return savings_assumptions_from_snapshot(self._snapshot)


class CsvMetroPriceSource:
    """Resolve metro prices from bundled CSV price trends."""

    def __init__(self, *, path: Path = DEFAULT_CSV_PATH) -> None:
        self._grouped = index_metro_rows(load_metro_price_trends(path))

    def list_metros(self) -> tuple[str, ...]:
        return list_metro_ids(self._grouped)

    def fetch_metro_price(
        self,
        *,
        metro_id: str,
        reference_year: int | None,
    ) -> MetroPriceAssumptions:
        row = select_metro_row(
            self._grouped,
            metro_id=metro_id,
            reference_year=reference_year,
        )
        return MetroPriceAssumptions(
            metro_id=row.metro_id,
            metro_name=row.metro_name,
            median_home_price=row.median_home_price,
            source=f"csv-metro:{row.metro_id}:{row.year}",
        )


class ProviderRateAdapter:
    """Wrap a full provider as a rate source, degrading unsupported query dimensions."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def fetch_rates(self, *, query: MarketQuery) -> RateAssumptions:
        from homeafford.market.base import fetch_provider_snapshot

        snapshot = fetch_provider_snapshot(
            self._provider,
            query,
            policy=QueryPolicy.DEGRADE,
        )
        return rate_assumptions_from_snapshot(snapshot)


class ProviderSavingsReturnAdapter:
    """Wrap a full provider as a savings return source."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def fetch_savings_return(self, *, query: MarketQuery) -> SavingsReturnAssumptions:
        from homeafford.market.base import fetch_provider_snapshot

        snapshot = fetch_provider_snapshot(
            self._provider,
            query,
            policy=QueryPolicy.DEGRADE,
        )
        return savings_assumptions_from_snapshot(snapshot)


def rate_source_from_provider(provider: MarketDataProvider) -> RateDataSource:
    """Adapt any market provider into a rate data source."""
    return ProviderRateAdapter(provider)


def savings_source_from_provider(provider: MarketDataProvider) -> SavingsReturnDataSource:
    """Adapt any market provider into a savings return data source."""
    return ProviderSavingsReturnAdapter(provider)


def describe_sources(
    *,
    rates: RateDataSource | None = None,
    metro: MetroPriceDataSource | None = None,
    savings: SavingsReturnDataSource | None = None,
) -> str:
    """Return a stable label describing the configured dimension sources."""
    parts: list[str] = []
    if rates is not None:
        parts.append(getattr(rates, "name", type(rates).__name__))
    if metro is not None:
        parts.append(getattr(metro, "name", type(metro).__name__))
    if savings is not None:
        parts.append(getattr(savings, "name", type(savings).__name__))
    return "+".join(parts) if parts else "empty"
