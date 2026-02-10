"""Shared metro home price trend loading and selection."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from homeafford.market.errors import MarketDataUnavailable

_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CSV_PATH = _DATA_DIR / "metro_home_price_trends.csv"


@dataclass(frozen=True)
class MetroPriceTrendRow:
    """One metro-year observation from a home price trends file."""

    metro_id: str
    metro_name: str
    year: int
    median_home_price: float
    yoy_change_pct: float


def load_metro_price_trends(path: Path = DEFAULT_CSV_PATH) -> list[MetroPriceTrendRow]:
    """Parse a metro home price trends CSV into typed rows."""
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


def index_metro_rows(rows: list[MetroPriceTrendRow]) -> dict[str, list[MetroPriceTrendRow]]:
    """Group price trend rows by metro ID, sorted by year within each metro."""
    grouped: dict[str, list[MetroPriceTrendRow]] = {}
    for row in rows:
        grouped.setdefault(row.metro_id, []).append(row)
    for metro_rows in grouped.values():
        metro_rows.sort(key=lambda row: row.year)
    return grouped


def select_metro_row(
    grouped: dict[str, list[MetroPriceTrendRow]],
    *,
    metro_id: str,
    reference_year: int | None,
) -> MetroPriceTrendRow:
    """Select a metro price row, optionally pinned to a reference year."""
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


def list_metro_ids(grouped: dict[str, list[MetroPriceTrendRow]]) -> tuple[str, ...]:
    """Return sorted metro IDs present in an indexed price table."""
    return tuple(sorted(grouped))


def metro_years(grouped: dict[str, list[MetroPriceTrendRow]], metro_id: str) -> tuple[int, ...]:
    """Return sorted calendar years available for a metro."""
    metro_rows = grouped.get(metro_id)
    if not metro_rows:
        raise MarketDataUnavailable(f"unknown metro_id {metro_id!r}")
    return tuple(row.year for row in metro_rows)
