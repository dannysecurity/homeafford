"""Tests for the metro home price trend catalog subsystem."""

from __future__ import annotations

import pytest

from homeafford.market.errors import MarketDataUnavailable
from homeafford.market.metro_trends import (
    MetroTrendCatalog,
    default_metro_trend_catalog,
    format_metro_trends_table,
    project_median_price,
)
from tests.helpers.metro_price_fixtures import METRO_HOME_PRICE_TRENDS_PATH


def test_default_catalog_lists_eight_metros():
    catalog = default_metro_trend_catalog()
    assert catalog.list_metros() == (
        "12420",
        "19740",
        "31080",
        "33100",
        "35620",
        "38060",
        "41860",
        "42660",
    )


def test_catalog_loads_fixture_csv():
    catalog = MetroTrendCatalog.from_csv(METRO_HOME_PRICE_TRENDS_PATH)
    assert len(catalog.rows) == 32


def test_catalog_series_returns_chronological_rows():
    catalog = default_metro_trend_catalog()
    series = catalog.series("31080")
    assert [row.year for row in series] == [2022, 2023, 2024, 2025]
    assert series[-1].median_home_price == pytest.approx(1_068_301)


def test_catalog_latest_returns_most_recent_row():
    catalog = default_metro_trend_catalog()
    latest = catalog.latest("41860")
    assert latest.year == 2025
    assert latest.median_home_price == pytest.approx(1_028_850)


def test_catalog_summary_computes_total_change():
    catalog = default_metro_trend_catalog()
    summary = catalog.summary("12420")
    assert summary.start_year == 2022
    assert summary.end_year == 2025
    assert summary.start_price == pytest.approx(480_000)
    assert summary.end_price == pytest.approx(638_880)
    assert summary.total_change_pct == pytest.approx(638_880 / 480_000 - 1.0)
    assert summary.avg_yoy_pct == pytest.approx(0.10)


def test_catalog_unknown_metro_raises():
    catalog = default_metro_trend_catalog()
    with pytest.raises(MarketDataUnavailable, match="unknown metro_id"):
        catalog.series("99999")


def test_catalog_missing_year_raises():
    catalog = default_metro_trend_catalog()
    with pytest.raises(MarketDataUnavailable, match="year 2019"):
        catalog.row_for_year("31080", 2019)


def test_project_median_price_uses_yoy_rate():
    catalog = default_metro_trend_catalog()
    row = catalog.latest("35620")
    projected = project_median_price(row, years_forward=2)
    expected = row.median_home_price * (1.04**2)
    assert projected == pytest.approx(expected)


def test_project_median_price_rejects_negative_horizon():
    catalog = default_metro_trend_catalog()
    row = catalog.latest("35620")
    with pytest.raises(ValueError, match="years_forward"):
        project_median_price(row, years_forward=-1)


def test_format_metro_trends_table_lists_all_metros():
    catalog = default_metro_trend_catalog()
    rendered = format_metro_trends_table(catalog)
    assert "Miami-Fort Lauderdale-West Palm Beach, FL" in rendered
    assert "Denver-Aurora-Lakewood, CO" in rendered
    assert "33100" in rendered


def test_format_metro_trends_table_shows_single_metro_series():
    catalog = default_metro_trend_catalog()
    rendered = format_metro_trends_table(catalog, metro_id="42660")
    assert "Seattle-Tacoma-Bellevue, WA (42660)" in rendered
    assert "2025" in rendered
    assert "833,414" in rendered


def test_csv_metro_provider_includes_new_miami_metro():
    from homeafford.market.csv_metro import CsvMetroMarketProvider
    from homeafford.market.query import MarketQuery

    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="33100", reference_year=2025))
    assert snapshot.metro_name == "Miami-Fort Lauderdale-West Palm Beach, FL"
    assert snapshot.median_home_price == pytest.approx(727_301)
