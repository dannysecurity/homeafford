"""Tests for metro home price trend CSV fixtures."""

from __future__ import annotations

import pytest

from tests.helpers.metro_price_fixtures import (
    METRO_HOME_PRICE_TRENDS_PATH,
    fixture_matches_bundled_csv,
    fixture_row_count,
    load_metro_home_price_trends,
    median_home_price_for,
    metros_with_median_above,
    metro_ids_in,
    validate_metro_home_price_trends,
    yoy_change_for,
)
from homeafford.market.metro_prices import (
    MetroPriceTrendRow,
    MetroPriceTrendValidationError,
    validate_metro_price_trends,
)


def test_metro_home_price_trends_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_PATH.is_file()


def test_fixture_csv_matches_bundled_data():
    assert fixture_matches_bundled_csv()


def test_load_metro_home_price_trends_parses_rows():
    rows = load_metro_home_price_trends()
    assert len(rows) == 68
    assert metro_ids_in(rows) == (
        "12060",
        "12420",
        "14460",
        "16980",
        "19100",
        "19740",
        "26420",
        "31080",
        "33100",
        "33460",
        "34980",
        "35620",
        "38060",
        "38900",
        "41740",
        "41860",
        "42660",
    )


def test_median_home_price_for_returns_fixture_value():
    rows = load_metro_home_price_trends()
    price = median_home_price_for(rows, metro_id="31080", year=2023)
    assert price == pytest.approx(918_000)


def test_median_home_price_for_missing_year_raises():
    rows = load_metro_home_price_trends()
    with pytest.raises(KeyError, match="metro_id='31080' year=2019"):
        median_home_price_for(rows, metro_id="31080", year=2019)


def test_yoy_change_for_returns_fixture_value():
    rows = load_metro_home_price_trends()
    change = yoy_change_for(rows, metro_id="12420", year=2023)
    assert change == pytest.approx(0.10)


def test_fixture_row_count_matches_parsed_rows():
    rows = load_metro_home_price_trends()
    assert fixture_row_count(rows) == 68


def test_validate_metro_home_price_trends_passes_for_fixture():
    validate_metro_home_price_trends()


def test_validate_metro_price_trends_rejects_duplicate_metro_year():
    rows = [
        MetroPriceTrendRow("31080", "Los Angeles, CA", 2023, 900_000, 0.05),
        MetroPriceTrendRow("31080", "Los Angeles, CA", 2023, 910_000, 0.04),
    ]
    with pytest.raises(MetroPriceTrendValidationError, match="duplicate metro_id/year"):
        validate_metro_price_trends(rows)


def test_validate_metro_price_trends_rejects_non_positive_price():
    rows = [MetroPriceTrendRow("31080", "Los Angeles, CA", 2023, 0, 0.05)]
    with pytest.raises(MetroPriceTrendValidationError, match="median_home_price must be positive"):
        validate_metro_price_trends(rows)


def test_validate_metro_price_trends_rejects_inconsistent_metro_name():
    rows = [
        MetroPriceTrendRow("31080", "Los Angeles, CA", 2022, 850_000, 0.05),
        MetroPriceTrendRow("31080", "LA Metro", 2023, 900_000, 0.05),
    ]
    with pytest.raises(MetroPriceTrendValidationError, match="inconsistent metro_name"):
        validate_metro_price_trends(rows)


def test_metros_with_median_above_filters_by_year():
    rows = load_metro_home_price_trends()
    expensive = metros_with_median_above(rows, year=2025, threshold=700_000)
    assert "31080" in expensive
    assert "41860" in expensive
    assert "16980" not in expensive
