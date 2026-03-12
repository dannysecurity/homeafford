"""Tests for the metro home price trend catalog subsystem."""

from __future__ import annotations

import pytest

from homeafford.market.errors import MarketDataUnavailable
from homeafford.market.metro_trends import (
    MetroTrendCatalog,
    compound_annual_growth_rate,
    default_metro_trend_catalog,
    format_metro_trend_projection,
    format_metro_trends_ranked,
    format_metro_trends_table,
    project_median_price,
    rank_metros_by_total_change,
)
from tests.helpers.metro_price_fixtures import METRO_HOME_PRICE_TRENDS_PATH


def test_default_catalog_lists_twenty_metros():
    catalog = default_metro_trend_catalog()
    assert catalog.list_metros() == (
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


def test_catalog_loads_fixture_csv():
    catalog = MetroTrendCatalog.from_csv(METRO_HOME_PRICE_TRENDS_PATH)
    assert len(catalog.rows) == 100


def test_catalog_loads_fixture_via_pytest_fixture(metro_trend_catalog):
    assert len(metro_trend_catalog.rows) == 100
    assert metro_trend_catalog.latest("38900").median_home_price == pytest.approx(653_325)


def test_catalog_year_span_covers_fixture_range():
    catalog = default_metro_trend_catalog()
    assert catalog.year_span() == (2022, 2026)


def test_catalog_series_returns_chronological_rows():
    catalog = default_metro_trend_catalog()
    series = catalog.series("31080")
    assert [row.year for row in series] == [2022, 2023, 2024, 2025, 2026]
    assert series[-1].median_home_price == pytest.approx(1_152_376)


def test_catalog_latest_returns_most_recent_row():
    catalog = default_metro_trend_catalog()
    latest = catalog.latest("41860")
    assert latest.year == 2026
    assert latest.median_home_price == pytest.approx(977_408)


def test_catalog_summary_computes_total_change():
    catalog = default_metro_trend_catalog()
    summary = catalog.summary("12420")
    assert summary.start_year == 2022
    assert summary.end_year == 2026
    assert summary.start_price == pytest.approx(480_000)
    assert summary.end_price == pytest.approx(702_768)
    assert summary.total_change_pct == pytest.approx(702_768 / 480_000 - 1.0)
    assert summary.avg_yoy_pct == pytest.approx(0.10)
    assert summary.cagr_pct == pytest.approx(
        compound_annual_growth_rate(480_000, 702_768, years=4)
    )


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
    assert "2026" in rendered
    assert "866,751" in rendered


def test_csv_metro_provider_includes_new_miami_metro():
    from homeafford.market.csv_metro import CsvMetroMarketProvider
    from homeafford.market.query import MarketQuery

    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="33100", reference_year=2025))
    assert snapshot.metro_name == "Miami-Fort Lauderdale-West Palm Beach, FL"
    assert snapshot.median_home_price == pytest.approx(727_301)


def test_rank_metros_by_total_change_orders_summaries():
    catalog = default_metro_trend_catalog()
    ranked = rank_metros_by_total_change(catalog)
    assert ranked[0].total_change_pct >= ranked[-1].total_change_pct
    assert ranked[0].metro_id == "33100"


def test_format_metro_trend_projection_shows_forward_price():
    catalog = default_metro_trend_catalog()
    rendered = format_metro_trend_projection(
        catalog,
        metro_id="19100",
        years_forward=2,
    )
    latest = catalog.latest("19100")
    expected = project_median_price(latest, years_forward=2)
    assert "Dallas-Fort Worth-Arlington, TX (19100)" in rendered
    assert f"${expected:,.0f}" in rendered
    assert "2028" in rendered


def test_compound_annual_growth_rate_computes_cagr():
    cagr = compound_annual_growth_rate(480_000, 638_880, years=3)
    assert cagr == pytest.approx((638_880 / 480_000) ** (1 / 3) - 1.0)


def test_compound_annual_growth_rate_zero_years_returns_zero():
    assert compound_annual_growth_rate(500_000, 550_000, years=0) == 0.0


def test_format_metro_trends_ranked_shows_cagr_and_order():
    catalog = default_metro_trend_catalog()
    rendered = format_metro_trends_ranked(catalog)
    assert "Rank" in rendered
    assert "CAGR %" in rendered
    assert "Miami-Fort Lauderdale-West Palm Beach, FL" in rendered
    assert "Houston-The Woodlands-Sugar Land, TX" in rendered
    ranked = rank_metros_by_total_change(catalog)
    assert rendered.index(ranked[0].metro_name) < rendered.index(ranked[-1].metro_name)


def test_csv_metro_provider_includes_houston_metro():
    from homeafford.market.csv_metro import CsvMetroMarketProvider
    from homeafford.market.query import MarketQuery

    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="26420", reference_year=2025))
    assert snapshot.metro_name == "Houston-The Woodlands-Sugar Land, TX"
    assert snapshot.median_home_price == pytest.approx(376_465)


def test_csv_metro_provider_includes_san_diego_metro():
    from homeafford.market.csv_metro import CsvMetroMarketProvider
    from homeafford.market.query import MarketQuery

    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="41740", reference_year=2025))
    assert snapshot.metro_name == "San Diego-Carlsbad, CA"
    assert snapshot.median_home_price == pytest.approx(1_071_889)


def test_csv_metro_provider_includes_charlotte_metro():
    from homeafford.market.csv_metro import CsvMetroMarketProvider
    from homeafford.market.query import MarketQuery

    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="16740", reference_year=2025))
    assert snapshot.metro_name == "Charlotte-Concord-Gastonia, NC-SC"
    assert snapshot.median_home_price == pytest.approx(428_756)


def test_catalog_summary_for_tampa_metro():
    catalog = default_metro_trend_catalog()
    summary = catalog.summary("45300")
    assert summary.start_price == pytest.approx(340_000)
    assert summary.end_price == pytest.approx(466_839)
    assert summary.total_change_pct == pytest.approx(466_839 / 340_000 - 1.0)


def test_budget_catalog_lists_five_affordable_metros(metro_trend_budget_catalog):
    assert metro_trend_budget_catalog.list_metros() == (
        "13820",
        "17460",
        "26900",
        "32820",
        "38300",
    )


def test_rank_metros_by_total_change_filters_by_max_price():
    catalog = default_metro_trend_catalog()
    ranked = rank_metros_by_total_change(catalog, max_price=400_000, year=2025)
    assert all(
        catalog.row_for_year(item.metro_id, 2025).median_home_price <= 400_000
        for item in ranked
    )
    assert "31080" not in {item.metro_id for item in ranked}
    assert "16980" in {item.metro_id for item in ranked}


def test_format_metro_trends_table_filters_by_max_price():
    catalog = default_metro_trend_catalog()
    rendered = format_metro_trends_table(catalog, max_price=400_000, year=2025)
    assert "Chicago-Naperville-Elgin, IL-IN-WI" in rendered
    assert "Houston-The Woodlands-Sugar Land, TX" in rendered
    assert "Los Angeles-Long Beach-Anaheim, CA" not in rendered
