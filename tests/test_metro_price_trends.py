"""Tests for metro home price trend CSV fixtures."""

from __future__ import annotations

import pytest

from tests.helpers.metro_price_fixtures import (
    BUDGET_METRO_COUNT,
    BUDGET_ROW_COUNT,
    BUDGET_YEAR_END,
    DECLINING_METRO_COUNT,
    DECLINING_ROW_COUNT,
    DECLINING_YEAR_END,
    EXPECTED_METRO_COUNT,
    EXPECTED_ROW_COUNT,
    EXPECTED_YEAR_END,
    METRO_HOME_PRICE_TRENDS_PATH,
    METRO_HOME_PRICE_TRENDS_BUDGET_PATH,
    METRO_HOME_PRICE_TRENDS_DECLINING_PATH,
    METRO_HOME_PRICE_TRENDS_PREMIUM_PATH,
    METRO_HOME_PRICE_TRENDS_SAMPLE_PATH,
    METRO_HOME_PRICE_TRENDS_STABLE_PATH,
    METRO_HOME_PRICE_TRENDS_RECOVERING_PATH,
    PREMIUM_METRO_COUNT,
    PREMIUM_PRICE_FLOOR,
    PREMIUM_ROW_COUNT,
    PREMIUM_YEAR_END,
    SAMPLE_METRO_COUNT,
    SAMPLE_ROW_COUNT,
    RECOVERING_METRO_COUNT,
    RECOVERING_ROW_COUNT,
    RECOVERING_TROUGH_YEAR,
    RECOVERING_YEAR_END,
    STABLE_METRO_COUNT,
    STABLE_ROW_COUNT,
    STABLE_YEAR_END,
    STABLE_YOY_CEILING,
    fixture_matches_bundled_csv,
    fixture_row_count,
    load_metro_home_price_trends,
    load_metro_home_price_trends_budget,
    load_metro_home_price_trends_declining,
    load_metro_home_price_trends_premium,
    load_metro_home_price_trends_sample,
    load_metro_home_price_trends_stable,
    load_metro_home_price_trends_recovering,
    median_home_price_for,
    metros_with_median_above,
    metros_with_median_at_or_below,
    metros_with_yoy_at_or_below,
    metros_with_yoy_above,
    metro_ids_in,
    validate_metro_home_price_trends,
    year_range_for,
    yoy_change_for,
)
from homeafford.market.metro_prices import (
    MetroPriceTrendRow,
    MetroPriceTrendValidationError,
    validate_metro_price_trends,
    validate_yoy_price_consistency,
)


def test_metro_home_price_trends_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_PATH.is_file()


def test_metro_home_price_trends_sample_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_SAMPLE_PATH.is_file()


def test_metro_home_price_trends_budget_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_BUDGET_PATH.is_file()


def test_metro_home_price_trends_premium_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_PREMIUM_PATH.is_file()


def test_metro_home_price_trends_declining_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_DECLINING_PATH.is_file()


def test_metro_home_price_trends_stable_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_STABLE_PATH.is_file()


def test_metro_home_price_trends_recovering_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_RECOVERING_PATH.is_file()


def test_load_metro_home_price_trends_budget_parses_affordable_metros():
    rows = load_metro_home_price_trends_budget()
    assert len(rows) == BUDGET_ROW_COUNT
    assert metro_ids_in(rows) == ("13820", "17460", "26900", "32820", "38300")
    assert len(metro_ids_in(rows)) == BUDGET_METRO_COUNT
    validate_metro_price_trends(rows)


def test_metros_with_median_at_or_below_filters_budget_fixture():
    rows = load_metro_home_price_trends_budget()
    under_300k = metros_with_median_at_or_below(rows, year=BUDGET_YEAR_END, max_price=300_000)
    assert under_300k == ("13820", "17460", "38300")
    assert "32820" not in under_300k
    assert "26900" not in under_300k


def test_load_metro_home_price_trends_premium_parses_high_cost_metros():
    rows = load_metro_home_price_trends_premium()
    assert len(rows) == PREMIUM_ROW_COUNT
    assert metro_ids_in(rows) == ("14460", "31080", "41740", "41860", "42660")
    assert len(metro_ids_in(rows)) == PREMIUM_METRO_COUNT
    validate_metro_price_trends(rows)


def test_metros_with_median_above_filters_premium_fixture():
    rows = load_metro_home_price_trends_premium()
    expensive = metros_with_median_above(
        rows, year=PREMIUM_YEAR_END, threshold=PREMIUM_PRICE_FLOOR
    )
    assert expensive == ("14460", "31080", "41740", "41860", "42660")
    assert yoy_change_for(rows, metro_id="41860", year=PREMIUM_YEAR_END) == pytest.approx(-0.05)


def test_load_metro_home_price_trends_declining_parses_softening_metros():
    rows = load_metro_home_price_trends_declining()
    assert len(rows) == DECLINING_ROW_COUNT
    assert metro_ids_in(rows) == ("19820", "38900", "41860")
    assert len(metro_ids_in(rows)) == DECLINING_METRO_COUNT
    validate_metro_price_trends(rows)


def test_declining_fixture_prices_fall_for_every_metro():
    rows = load_metro_home_price_trends_declining()
    for metro_id in metro_ids_in(rows):
        start_price = median_home_price_for(rows, metro_id=metro_id, year=2022)
        end_price = median_home_price_for(rows, metro_id=metro_id, year=DECLINING_YEAR_END)
        assert end_price < start_price
        assert yoy_change_for(rows, metro_id=metro_id, year=DECLINING_YEAR_END) < 0


def test_load_metro_home_price_trends_stable_parses_flat_metros():
    rows = load_metro_home_price_trends_stable()
    assert len(rows) == STABLE_ROW_COUNT
    assert metro_ids_in(rows) == ("14260", "33340", "39540")
    assert len(metro_ids_in(rows)) == STABLE_METRO_COUNT
    validate_metro_price_trends(rows)


def test_stable_fixture_yoy_growth_stays_within_ceiling():
    rows = load_metro_home_price_trends_stable()
    flat_metros = metros_with_yoy_at_or_below(
        rows, year=STABLE_YEAR_END, max_yoy=STABLE_YOY_CEILING
    )
    assert flat_metros == ("14260", "33340", "39540")
    boise_price = median_home_price_for(rows, metro_id="14260", year=STABLE_YEAR_END)
    assert boise_price == median_home_price_for(rows, metro_id="14260", year=2022)


def test_load_metro_home_price_trends_recovering_parses_rebound_metros():
    rows = load_metro_home_price_trends_recovering()
    assert len(rows) == RECOVERING_ROW_COUNT
    assert metro_ids_in(rows) == ("29820", "34980", "38060")
    assert len(metro_ids_in(rows)) == RECOVERING_METRO_COUNT
    validate_metro_price_trends(rows)


def test_recovering_fixture_prices_rebound_after_trough():
    rows = load_metro_home_price_trends_recovering()
    softening = metros_with_yoy_at_or_below(
        rows, year=RECOVERING_TROUGH_YEAR, max_yoy=0.0
    )
    assert softening == ("29820", "34980", "38060")
    rebounding = metros_with_yoy_above(
        rows, year=RECOVERING_YEAR_END, min_yoy=0.0
    )
    assert rebounding == ("29820", "34980", "38060")
    for metro_id in metro_ids_in(rows):
        trough_price = median_home_price_for(
            rows, metro_id=metro_id, year=RECOVERING_TROUGH_YEAR
        )
        end_price = median_home_price_for(
            rows, metro_id=metro_id, year=RECOVERING_YEAR_END
        )
        assert end_price > trough_price


def test_load_metro_home_price_trends_sample_parses_subset():
    rows = load_metro_home_price_trends_sample()
    assert len(rows) == SAMPLE_ROW_COUNT
    assert metro_ids_in(rows) == ("12420", "45300")
    assert len(metro_ids_in(rows)) == SAMPLE_METRO_COUNT
    validate_metro_price_trends(rows)


def test_fixture_csv_matches_bundled_data():
    assert fixture_matches_bundled_csv()


def test_load_metro_home_price_trends_parses_rows():
    rows = load_metro_home_price_trends()
    assert len(rows) == EXPECTED_ROW_COUNT
    assert metro_ids_in(rows) == (
        "12060",
        "12420",
        "14460",
        "16740",
        "16980",
        "19100",
        "19740",
        "26420",
        "29820",
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
        "45300",
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
    assert fixture_row_count(rows) == EXPECTED_ROW_COUNT
    assert len(metro_ids_in(rows)) == EXPECTED_METRO_COUNT


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


def test_year_range_for_returns_first_and_last_years():
    rows = load_metro_home_price_trends()
    assert year_range_for(rows, metro_id="45300") == (2022, EXPECTED_YEAR_END)


def test_median_home_price_for_returns_2026_fixture_value():
    rows = load_metro_home_price_trends()
    price = median_home_price_for(rows, metro_id="12420", year=2026)
    assert price == pytest.approx(702_768)


def test_validate_yoy_price_consistency_rejects_mismatched_price():
    rows = [
        MetroPriceTrendRow("45300", "Tampa, FL", 2022, 340_000, 0.09),
        MetroPriceTrendRow("45300", "Tampa, FL", 2023, 400_000, 0.085),
    ]
    with pytest.raises(MetroPriceTrendValidationError, match="yoy price inconsistency"):
        validate_yoy_price_consistency(rows, tolerance=0.01)
