"""Tests for metro home price trend CSV fixtures."""

from __future__ import annotations

import pytest

from tests.helpers.metro_price_fixtures import (
    METRO_HOME_PRICE_TRENDS_PATH,
    load_metro_home_price_trends,
    median_home_price_for,
    yoy_change_for,
)


def test_metro_home_price_trends_fixture_exists():
    assert METRO_HOME_PRICE_TRENDS_PATH.is_file()


def test_load_metro_home_price_trends_parses_rows():
    rows = load_metro_home_price_trends()
    assert len(rows) == 12
    assert {row.metro_id for row in rows} == {"31080", "41860", "35620", "12420"}


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
