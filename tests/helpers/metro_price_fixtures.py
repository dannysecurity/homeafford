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
METRO_HOME_PRICE_TRENDS_BUDGET_PATH = FIXTURES_DIR / "metro_home_price_trends_budget.csv"
METRO_HOME_PRICE_TRENDS_PREMIUM_PATH = FIXTURES_DIR / "metro_home_price_trends_premium.csv"
METRO_HOME_PRICE_TRENDS_DECLINING_PATH = FIXTURES_DIR / "metro_home_price_trends_declining.csv"
METRO_HOME_PRICE_TRENDS_STABLE_PATH = FIXTURES_DIR / "metro_home_price_trends_stable.csv"
METRO_HOME_PRICE_TRENDS_RECOVERING_PATH = FIXTURES_DIR / "metro_home_price_trends_recovering.csv"
BUNDLED_METRO_HOME_PRICE_TRENDS_PATH = DEFAULT_CSV_PATH
EXPECTED_METRO_COUNT = 20
EXPECTED_ROW_COUNT = 100
EXPECTED_YEAR_START = 2022
EXPECTED_YEAR_END = 2026
SAMPLE_METRO_COUNT = 2
SAMPLE_ROW_COUNT = 8
BUDGET_METRO_COUNT = 5
BUDGET_ROW_COUNT = 25
BUDGET_YEAR_END = 2026
PREMIUM_METRO_COUNT = 5
PREMIUM_ROW_COUNT = 25
PREMIUM_YEAR_END = 2026
PREMIUM_PRICE_FLOOR = 700_000
DECLINING_METRO_COUNT = 3
DECLINING_ROW_COUNT = 15
DECLINING_YEAR_END = 2026
STABLE_METRO_COUNT = 3
STABLE_ROW_COUNT = 15
STABLE_YEAR_END = 2026
STABLE_YOY_CEILING = 0.01
RECOVERING_METRO_COUNT = 3
RECOVERING_ROW_COUNT = 15
RECOVERING_YEAR_END = 2026
RECOVERING_TROUGH_YEAR = 2024


def load_metro_home_price_trends(
    path: Path = METRO_HOME_PRICE_TRENDS_PATH,
) -> list[MetroPriceTrendRow]:
    """Parse ``metro_home_price_trends.csv`` into typed rows."""
    return load_metro_price_trends(path)


def load_metro_home_price_trends_sample() -> list[MetroPriceTrendRow]:
    """Parse the two-metro sample fixture for lightweight market tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_SAMPLE_PATH)


def load_metro_home_price_trends_budget() -> list[MetroPriceTrendRow]:
    """Parse the budget-metro fixture for affordability-focused market tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_BUDGET_PATH)


def load_metro_home_price_trends_premium() -> list[MetroPriceTrendRow]:
    """Parse the premium-metro fixture for high-cost market tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_PREMIUM_PATH)


def load_metro_home_price_trends_declining() -> list[MetroPriceTrendRow]:
    """Parse the declining-metro fixture for softening market tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_DECLINING_PATH)


def load_metro_home_price_trends_stable() -> list[MetroPriceTrendRow]:
    """Parse the stable-metro fixture for flat-market trend tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_STABLE_PATH)


def load_metro_home_price_trends_recovering() -> list[MetroPriceTrendRow]:
    """Parse the recovering-metro fixture for post-trough rebound tests."""
    return load_metro_price_trends(METRO_HOME_PRICE_TRENDS_RECOVERING_PATH)


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


def metros_with_median_at_or_below(
    rows: list[MetroPriceTrendRow],
    *,
    year: int,
    max_price: float,
) -> tuple[str, ...]:
    """Return metro IDs whose median price is at or below a ceiling in a given year."""
    matches = {
        row.metro_id
        for row in rows
        if row.year == year and row.median_home_price <= max_price
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


def metros_with_yoy_at_or_below(
    rows: list[MetroPriceTrendRow],
    *,
    year: int,
    max_yoy: float,
) -> tuple[str, ...]:
    """Return metro IDs whose YoY change is at or below a ceiling in a given year."""
    matches = {
        row.metro_id
        for row in rows
        if row.year == year and row.yoy_change_pct <= max_yoy
    }
    return tuple(sorted(matches))


def metros_with_yoy_above(
    rows: list[MetroPriceTrendRow],
    *,
    year: int,
    min_yoy: float,
) -> tuple[str, ...]:
    """Return metro IDs whose YoY change exceeds a floor in a given year."""
    matches = {
        row.metro_id
        for row in rows
        if row.year == year and row.yoy_change_pct > min_yoy
    }
    return tuple(sorted(matches))
