"""Metro home price trend catalog: time-series queries and projections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeafford.market.errors import MarketDataUnavailable
from homeafford.market.metro_prices import (
    DEFAULT_CSV_PATH,
    MetroPriceTrendRow,
    index_metro_rows,
    load_metro_price_trends,
)


@dataclass(frozen=True)
class MetroTrendSummary:
    """Aggregate price trend statistics for one metro area."""

    metro_id: str
    metro_name: str
    start_year: int
    end_year: int
    start_price: float
    end_price: float
    total_change_pct: float
    avg_yoy_pct: float
    row_count: int


@dataclass(frozen=True)
class MetroTrendCatalog:
    """Indexed view over bundled metro home price trend CSV data."""

    rows: tuple[MetroPriceTrendRow, ...]
    grouped: dict[str, tuple[MetroPriceTrendRow, ...]]

    @classmethod
    def from_csv(cls, path: Path = DEFAULT_CSV_PATH) -> MetroTrendCatalog:
        """Load and index metro price trends from a CSV file."""
        loaded = load_metro_price_trends(path)
        indexed = index_metro_rows(loaded)
        grouped = {metro_id: tuple(metro_rows) for metro_id, metro_rows in indexed.items()}
        return cls(rows=tuple(loaded), grouped=grouped)

    def list_metros(self) -> tuple[str, ...]:
        """Return sorted metro IDs present in the catalog."""
        return tuple(sorted(self.grouped))

    def metro_name(self, metro_id: str) -> str:
        """Return the display name for a metro ID."""
        series = self.series(metro_id)
        return series[0].metro_name

    def series(self, metro_id: str) -> tuple[MetroPriceTrendRow, ...]:
        """Return chronological price rows for one metro."""
        metro_rows = self.grouped.get(metro_id)
        if not metro_rows:
            raise MarketDataUnavailable(f"unknown metro_id {metro_id!r}")
        return metro_rows

    def row_for_year(self, metro_id: str, year: int) -> MetroPriceTrendRow:
        """Return the observation for a metro and calendar year."""
        for row in self.series(metro_id):
            if row.year == year:
                return row
        raise MarketDataUnavailable(
            f"no price data for metro_id {metro_id!r} in year {year}"
        )

    def latest(self, metro_id: str) -> MetroPriceTrendRow:
        """Return the most recent observation for a metro."""
        return self.series(metro_id)[-1]

    def summary(self, metro_id: str) -> MetroTrendSummary:
        """Compute aggregate trend statistics for one metro."""
        metro_rows = self.series(metro_id)
        first = metro_rows[0]
        last = metro_rows[-1]
        total_change = (last.median_home_price / first.median_home_price) - 1.0
        avg_yoy = sum(row.yoy_change_pct for row in metro_rows) / len(metro_rows)
        return MetroTrendSummary(
            metro_id=metro_id,
            metro_name=first.metro_name,
            start_year=first.year,
            end_year=last.year,
            start_price=first.median_home_price,
            end_price=last.median_home_price,
            total_change_pct=total_change,
            avg_yoy_pct=avg_yoy,
            row_count=len(metro_rows),
        )

    def summaries(self) -> tuple[MetroTrendSummary, ...]:
        """Return trend summaries for every metro, sorted by metro ID."""
        return tuple(self.summary(metro_id) for metro_id in self.list_metros())


def project_median_price(
    row: MetroPriceTrendRow,
    *,
    years_forward: int,
) -> float:
    """Project median home price forward using the row's YoY change rate."""
    if years_forward < 0:
        raise ValueError("years_forward must be non-negative")
    return row.median_home_price * (1.0 + row.yoy_change_pct) ** years_forward


def format_metro_trends_table(
    catalog: MetroTrendCatalog,
    *,
    metro_id: str | None = None,
) -> str:
    """Render metro price trends as a fixed-width table."""
    if metro_id is not None:
        rows = catalog.series(metro_id)
        header = f"{rows[0].metro_name} ({metro_id})"
        lines = [
            header,
            f"{'Year':>6}  {'Median $':>14}  {'YoY %':>8}",
        ]
        for row in rows:
            lines.append(
                f"{row.year:6d}  ${row.median_home_price:>12,.0f}  "
                f"{row.yoy_change_pct * 100:>7.2f}%"
            )
        return "\n".join(lines)

    summaries = catalog.summaries()
    lines = [
        f"{'Metro ID':>8}  {'Metro':<42}  {'Years':>9}  "
        f"{'Start $':>12}  {'End $':>12}  {'Total %':>8}  {'Avg YoY %':>9}",
    ]
    for item in summaries:
        year_span = f"{item.start_year}-{item.end_year}"
        lines.append(
            f"{item.metro_id:>8}  {item.metro_name:<42}  {year_span:>9}  "
            f"${item.start_price:>10,.0f}  ${item.end_price:>10,.0f}  "
            f"{item.total_change_pct * 100:>7.2f}%  {item.avg_yoy_pct * 100:>8.2f}%"
        )
    return "\n".join(lines)


def default_metro_trend_catalog() -> MetroTrendCatalog:
    """Return the bundled metro home price trend catalog."""
    return MetroTrendCatalog.from_csv()
