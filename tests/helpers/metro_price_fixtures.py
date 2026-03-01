"""Load metro home price trend CSV fixtures for report and market tests."""

from __future__ import annotations

from pathlib import Path

from homeafford.market.metro_prices import (
    DEFAULT_CSV_PATH,
    MetroPriceTrendRow,
    load_metro_price_trends,
    validate_metro_price_trends,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
METRO_HOME_PRICE_TRENDS_PATH = FIXTURES_DIR / "metro_home_price_trends.csv"
METRO_HOME_PRICE_TRENDS_SAMPLE_PATH = FIXTURES_DIR / "metro_home_price_trends_sample.csv"
BUNDLED_METRO_HOME_PRICE_TRENDS_PATH = DEFAULT_CSV_PATH
EXPECTED_METRO_COUNT = 20
EXPECTED_ROW_COUNT = 80
SAMPLE_METRO_COUNT = 2
SAMPLE_ROW_COUNT = 8


def load_metro_home_price_trends(
    path: Path = METRO_HOME_PRICE_TRENDS_PATH,
) -> list[MetroPriceTrendRow]:
    """Parse ``metro_home_price_trends.csv`` into typed rows."""
    return load_metro_price_trends(path)


def load_metro_home_price_trends_sample() -> list[MetroPriceTrendRow]:
    """Parse the two-metro sample fixture for lightweight market tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_SAMPLE_PATH)


def metro_ids_in(rows: list[MetroPriceTrendRow]) -> tuple[str, ...]:
    """Return sorted metro IDs present in parsed trend rows."""
    return tuple(sorted({row.metro_id for row in rows}))


def fixture_matches_bundled_csv() -> bool:
    """Return whether the test fixture CSV matches the bundled package data."""
    return METRO_HOME_PRICE_TRENDS_PATH.read_text() == BUNDLED_METRO_HOME_PRICE_TRENDS_PATH.read_text()


def validate_metro_home_price_trends(
    path: Path = METRO_HOME_PRICE_TRENDS_PATH,
) -> None:
    """Run integrity checks on a metro home price trends CSV fixture."""
    validate_metro_price_trends(load_metro_home_price_trends(path))


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


def fixture_row_count(rows: list[MetroPriceTrendRow]) -> int:
    """Return the number of metro-year observations in parsed fixture rows."""
    return len(rows)


def metros_with_median_above(
    rows: list[MetroPriceTrendRow],
    *,
    year: int,
    threshold: float,
) -> tuple[str, ...]:
    """Return metro IDs whose median price exceeds a threshold in a given year."""
    matches = {
        row.metro_id
        for row in rows
        if row.year == year and row.median_home_price > threshold
    }
    return tuple(sorted(matches))


def year_range_for(
    rows: list[MetroPriceTrendRow],
    *,
    metro_id: str,
) -> tuple[int, int]:
    """Return the first and last calendar years available for a metro."""
    years = [row.year for row in rows if row.metro_id == metro_id]
    if not years:
        raise KeyError(f"no rows for metro_id={metro_id!r}")
    return min(years), max(years)
