"""Load metro home price trend CSV fixtures for report and market tests."""

from __future__ import annotations

from pathlib import Path

from homeafford.market.metro_prices import MetroPriceTrendRow, load_metro_price_trends

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
METRO_HOME_PRICE_TRENDS_PATH = FIXTURES_DIR / "metro_home_price_trends.csv"


def load_metro_home_price_trends(
    path: Path = METRO_HOME_PRICE_TRENDS_PATH,
) -> list[MetroPriceTrendRow]:
    """Parse ``metro_home_price_trends.csv`` into typed rows."""
    return load_metro_price_trends(path)


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
