"""Metro-aware market provider backed by bundled CSV price trends."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from homeafford.market.composite import MarketDataUnavailable
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot

_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CSV_PATH = _DATA_DIR / "metro_home_price_trends.csv"


@dataclass(frozen=True)
class MetroPriceTrendRow:
    """One metro-year observation from the bundled price trends file."""

    metro_id: str
    metro_name: str
    year: int
    median_home_price: float
    yoy_change_pct: float


def load_metro_price_trends(path: Path = DEFAULT_CSV_PATH) -> list[MetroPriceTrendRow]:
    """Parse the bundled metro home price trends CSV into typed rows."""
    rows: list[MetroPriceTrendRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows.append(
                MetroPriceTrendRow(
                    metro_id=record["metro_id"],
                    metro_name=record["metro_name"],
                    year=int(record["year"]),
                    median_home_price=float(record["median_home_price"]),
                    yoy_change_pct=float(record["yoy_change_pct"]),
                )
            )
    return rows


def _index_metro_rows(rows: list[MetroPriceTrendRow]) -> dict[str, list[MetroPriceTrendRow]]:
    grouped: dict[str, list[MetroPriceTrendRow]] = {}
    for row in rows:
        grouped.setdefault(row.metro_id, []).append(row)
    for metro_rows in grouped.values():
        metro_rows.sort(key=lambda row: row.year)
    return grouped


def _select_metro_row(
    grouped: dict[str, list[MetroPriceTrendRow]],
    *,
    metro_id: str,
    reference_year: int | None,
) -> MetroPriceTrendRow:
    metro_rows = grouped.get(metro_id)
    if not metro_rows:
        raise MarketDataUnavailable(f"unknown metro_id {metro_id!r}")

    if reference_year is not None:
        for row in metro_rows:
            if row.year == reference_year:
                return row
        raise MarketDataUnavailable(
            f"no price data for metro_id {metro_id!r} in year {reference_year}"
        )

    return metro_rows[-1]


class CsvMetroMarketProvider:
    """Resolve metro-specific snapshots from bundled CSV price trends."""

    def __init__(
        self,
        *,
        path: Path = DEFAULT_CSV_PATH,
        base: MarketSnapshot = DEFAULT_MARKET,
    ) -> None:
        self._base = base
        self._grouped = _index_metro_rows(load_metro_price_trends(path))

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        normalized = normalize_query(query)
        if normalized.metro_id is None:
            return self._base

        row = _select_metro_row(
            self._grouped,
            metro_id=normalized.metro_id,
            reference_year=normalized.reference_year,
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
    from homeafford.market.composite import CachedMarketProvider

    return CachedMarketProvider(CsvMetroMarketProvider())
