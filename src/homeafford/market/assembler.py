"""Assemble full market snapshots from dimension-specific data sources."""

from __future__ import annotations

from homeafford.market.base import BaseMarketProvider
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.errors import MarketDataUnavailable
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot
from homeafford.market.sources import (
    MetroPriceDataSource,
    RateDataSource,
    SavingsReturnDataSource,
    StaticSavingsReturnSource,
    describe_sources,
    rate_assumptions_from_snapshot,
    savings_assumptions_from_snapshot,
)


class SnapshotAssembler:
    """Merge partial assumptions from dimension sources into one snapshot."""

    def __init__(
        self,
        *,
        rates: RateDataSource | None = None,
        metro: MetroPriceDataSource | None = None,
        savings: SavingsReturnDataSource | None = None,
        fallback: MarketSnapshot = DEFAULT_MARKET,
    ) -> None:
        self._rates = rates
        self._metro = metro
        self._savings = savings
        self._fallback = fallback

    @property
    def rates(self) -> RateDataSource | None:
        """Configured rate source, if any."""
        return self._rates

    @property
    def metro(self) -> MetroPriceDataSource | None:
        """Configured metro price source, if any."""
        return self._metro

    @property
    def savings(self) -> SavingsReturnDataSource | None:
        """Configured savings return source, if any."""
        return self._savings

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Capabilities implied by the configured dimension sources."""
        supports_metro = self._metro is not None
        return ProviderCapabilities(
            supports_metro_pricing=supports_metro,
            supports_reference_year=supports_metro,
        )

    def assemble(self, *, query: MarketQuery) -> MarketSnapshot:
        """Build a snapshot by fetching each configured dimension."""
        rates = self._resolve_rates(query)
        savings = self._resolve_savings(query)
        metro_fields = self._resolve_metro_fields(query)

        source = self._compose_source(rates.source, metro_fields, savings.source)
        return MarketSnapshot(
            mortgage_rate=rates.mortgage_rate,
            property_tax_rate=rates.property_tax_rate,
            insurance_annual=rates.insurance_annual,
            savings_annual_return=savings.savings_annual_return,
            pmi_annual_rate=rates.pmi_annual_rate,
            pmi_ltv_threshold=rates.pmi_ltv_threshold,
            metro_id=metro_fields.get("metro_id"),
            metro_name=metro_fields.get("metro_name"),
            median_home_price=metro_fields.get("median_home_price"),
            source=source,
        )

    def _resolve_rates(self, query: MarketQuery):
        if self._rates is not None:
            return self._rates.fetch_rates(query=query)
        return rate_assumptions_from_snapshot(self._fallback)

    def _resolve_savings(self, query: MarketQuery):
        if self._savings is not None:
            return self._savings.fetch_savings_return(query=query)
        return savings_assumptions_from_snapshot(self._fallback)

    def _resolve_metro_fields(self, query: MarketQuery) -> dict[str, object]:
        if query.metro_id is None:
            return {}
        if self._metro is None:
            raise MarketDataUnavailable(
                f"metro_id {query.metro_id!r} requested but no metro price source configured",
            )
        metro = self._metro.fetch_metro_price(
            metro_id=query.metro_id,
            reference_year=query.reference_year,
        )
        return {
            "metro_id": metro.metro_id,
            "metro_name": metro.metro_name,
            "median_home_price": metro.median_home_price,
            "source": metro.source,
        }

    def _compose_source(
        self,
        rate_source: str,
        metro_fields: dict[str, object],
        savings_source: str,
    ) -> str:
        parts = [rate_source]
        metro_source = metro_fields.get("source")
        if metro_source is not None:
            parts.append(str(metro_source))
        if savings_source != rate_source:
            parts.append(f"savings:{savings_source}")
        return "+".join(parts)


class AssembledMarketProvider(BaseMarketProvider):
    """MarketDataProvider backed by a SnapshotAssembler."""

    def __init__(
        self,
        assembler: SnapshotAssembler,
        *,
        name: str | None = None,
    ) -> None:
        self._assembler = assembler
        self._name = name or f"assembled:{describe_sources(
            rates=assembler.rates,
            metro=assembler.metro,
            savings=assembler.savings,
        )}"

    @property
    def name(self) -> str:
        return self._name

    @property
    def assembler(self) -> SnapshotAssembler:
        """Underlying assembler composing dimension sources."""
        return self._assembler

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._assembler.capabilities

    def list_metros(self) -> tuple[str, ...] | None:
        if self._assembler.metro is None:
            return None
        return self._assembler.metro.list_metros()

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        return self._assembler.assemble(query=query)


def assembled_csv_metro_provider() -> AssembledMarketProvider:
    """Return a metro-aware provider composed from static rates and CSV prices."""
    from homeafford.market.sources import CsvMetroPriceSource, StaticRateSource

    return AssembledMarketProvider(
        SnapshotAssembler(
            rates=StaticRateSource(),
            metro=CsvMetroPriceSource(),
            savings=StaticSavingsReturnSource(),
        ),
        name="assembled-csv-metro",
    )
