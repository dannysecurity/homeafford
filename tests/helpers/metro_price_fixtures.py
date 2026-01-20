"""Load metro home price trend CSV fixtures for report and market tests."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
METRO_HOME_PRICE_TRENDS_PATH = FIXTURES_DIR / "metro_home_price_trends.csv"


@dataclass(frozen=True)
class MetroPriceTrendRow:
    """One metro-year observation from the home price trends fixture."""

    metro_id: str
    metro_name: str
    year: int
    median_home_price: float
    yoy_change_pct: float


def load_metro_home_price_trends(
    path: Path = METRO_HOME_PRICE_TRENDS_PATH,
) -> list[MetroPriceTrendRow]:
    """Parse ``metro_home_price_trends.csv`` into typed rows."""
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


def median_home_price_for(
    rows: list[MetroPriceTrendRow],
    *,
    metro_id: str,
    year: int,
) -> float:
    """Return the fixture median price for a metro and year."""
    for row in rows:
        if row.metro_id == metro_id and row.year == year:
            return row.median_home_price
    raise KeyError(f"no price for metro_id={metro_id!r} year={year}")


def yoy_change_for(
    rows: list[MetroPriceTrendRow],
    *,
    metro_id: str,
    year: int,
) -> float:
    """Return the year-over-year price change for a metro and year."""
    for row in rows:
        if row.metro_id == metro_id and row.year == year:
            return row.yoy_change_pct
    raise KeyError(f"no yoy change for metro_id={metro_id!r} year={year}")
