"""Metro-aware market provider backed by bundled CSV price trends."""

from __future__ import annotations

from pathlib import Path

from homeafford.market.base import BaseMarketProvider
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.metro_prices import (
    DEFAULT_CSV_PATH,
    index_metro_rows,
    list_metro_ids,
    load_metro_price_trends,
    select_metro_row,
)
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot


class CsvMetroMarketProvider(BaseMarketProvider):
    """Resolve metro-specific snapshots from bundled CSV price trends."""

    def __init__(
        self,
        *,
        path: Path = DEFAULT_CSV_PATH,
        base: MarketSnapshot = DEFAULT_MARKET,
    ) -> None:
        self._base = base
        self._grouped = index_metro_rows(load_metro_price_trends(path))

    @property
    def name(self) -> str:
        return "csv-metro"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_metro_pricing=True,
            supports_reference_year=True,
        )

    def list_metros(self) -> tuple[str, ...]:
        return list_metro_ids(self._grouped)

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        if query.metro_id is None:
            return self._base

        row = select_metro_row(
            self._grouped,
            metro_id=query.metro_id,
            reference_year=query.reference_year,
        )
        return MarketSnapshot(
            mortgage_rate=self._base.mortgage_rate,
            property_tax_rate=self._base.property_tax_rate,
            insurance_annual=self._base.insurance_annual,
            savings_annual_return=self._base.savings_annual_return,
            pmi_annual_rate=self._base.pmi_annual_rate,
            pmi_ltv_threshold=self._base.pmi_ltv_threshold,
            metro_id=row.metro_id,
            metro_name=row.metro_name,
            median_home_price=row.median_home_price,
            source=f"csv-metro:{row.metro_id}:{row.year}",
        )


def csv_metro_provider() -> MarketDataProvider:
    """Return a cached CSV metro provider suitable for registry use."""
    from homeafford.market.composite import build_provider_stack

    return build_provider_stack(CsvMetroMarketProvider())
