from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.report import (
    affordability_price_range,
    affordability_report_by_year,
    format_affordability_range_report,
    format_affordability_report,
    format_target_home_report,
    target_home_report_by_year,
)


def test_report_year_zero_matches_bands():
    rows = affordability_report_by_year(
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        starting_balance=60_000,
        years=0,
    )
    expected = affordability_bands(
        AffordabilityInputs(
            gross_annual_income=120_000,
            monthly_debt_payments=450,
            down_payment=60_000,
        )
    )
    assert len(rows) == 1
    assert rows[0].year == 0
    assert rows[0].down_payment == 60_000
    assert rows[0].bands[0].max_home_price == expected[0].max_home_price


def test_report_down_payment_grows_with_contributions():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=10_000,
        monthly_contribution=500,
        annual_return=0.0,
        years=3,
    )
    down_payments = [row.down_payment for row in rows]
    assert down_payments == sorted(down_payments)
    assert down_payments[0] == 10_000
    assert down_payments[-1] == 10_000 + 500 * 12 * 3


def test_report_max_prices_increase_with_savings():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=0,
        monthly_contribution=1_000,
        annual_return=0.0,
        years=2,
    )
    conservative_prices = [row.bands[0].max_home_price for row in rows]
    assert conservative_prices[0] <= conservative_prices[1] <= conservative_prices[2]


def test_report_flat_when_no_savings_or_growth():
    rows = affordability_report_by_year(
        gross_annual_income=90_000,
        starting_balance=20_000,
        annual_return=0.0,
        years=2,
    )
    assert rows[0].down_payment == rows[1].down_payment == rows[2].down_payment == 20_000
    assert (
        rows[0].bands[1].max_home_price
        == rows[1].bands[1].max_home_price
        == rows[2].bands[1].max_home_price
    )


def test_report_income_growth_raises_bands():
    base = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=25_000,
        years=2,
    )
    growing = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=25_000,
        income_growth_rate=0.03,
        years=2,
    )
    assert growing[2].bands[0].max_home_price > base[2].bands[0].max_home_price


def test_format_affordability_report_includes_headers_and_prices():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=10_000,
        monthly_contribution=500,
        years=1,
    )
    text = format_affordability_report(rows)
    assert "Year" in text
    assert "Income $" in text
    assert "Conservative" in text
    assert "Moderate" in text
    assert "Stretch" in text
    assert f"{rows[0].bands[0].max_home_price:,.0f}" in text
    assert f"{rows[-1].down_payment:,.0f}" in text
    assert f"{rows[0].gross_annual_income:,.0f}" in text


def test_format_affordability_report_shows_income_growth():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        income_growth_rate=0.05,
        years=2,
    )
    text = format_affordability_report(rows)
    assert f"{rows[0].gross_annual_income:,.0f}" in text
    assert f"{rows[2].gross_annual_income:,.0f}" in text
    assert rows[2].gross_annual_income > rows[0].gross_annual_income


def test_affordability_price_range_orders_conservative_below_stretch():
    rows = affordability_report_by_year(
        gross_annual_income=110_000,
        starting_balance=30_000,
        years=1,
    )
    for row in rows:
        low, high = affordability_price_range(row)
        assert low <= high
        assert low == row.bands[0].max_home_price
        assert high == row.bands[2].max_home_price


def test_range_report_widens_with_savings_and_income():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=5_000,
        monthly_contribution=1_000,
        income_growth_rate=0.03,
        years=3,
    )
    spreads = [affordability_price_range(row)[1] - affordability_price_range(row)[0] for row in rows]
    assert spreads[0] <= spreads[-1]
    assert spreads[-1] > 0


def test_format_affordability_range_report_includes_range_and_spread():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=10_000,
        monthly_contribution=500,
        years=2,
    )
    text = format_affordability_range_report(rows)
    low, high = affordability_price_range(rows[0])
    assert "Affordable range $" in text
    assert "Spread $" in text
    assert f"{low:,.0f}" in text
    assert f"{high:,.0f}" in text
    assert "–" in text
    assert f"{rows[0].gross_annual_income:,.0f}" in text
    assert f"{rows[-1].down_payment:,.0f}" in text


def test_target_home_report_becomes_ready_as_savings_grow():
    rows = target_home_report_by_year(
        home_price=400_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        starting_balance=10_000,
        monthly_contribution=3_000,
        annual_return=0.0,
        years=5,
        band_label="conservative",
    )
    assert len(rows) == 6
    assert not rows[0].ready
    assert rows[-1].savings_balance > rows[0].savings_balance
    assert any(row.ready for row in rows)


def test_target_home_report_min_down_tracks_income_growth():
    flat = target_home_report_by_year(
        home_price=500_000,
        gross_annual_income=100_000,
        starting_balance=50_000,
        years=3,
        band_label="conservative",
    )
    growing = target_home_report_by_year(
        home_price=500_000,
        gross_annual_income=100_000,
        starting_balance=50_000,
        income_growth_rate=0.05,
        years=3,
        band_label="conservative",
    )
    assert growing[3].min_down_for_dti is not None
    assert flat[3].min_down_for_dti is not None
    assert growing[3].min_down_for_dti <= flat[3].min_down_for_dti


def test_format_target_home_report_includes_headers():
    rows = target_home_report_by_year(
        home_price=450_000,
        gross_annual_income=110_000,
        starting_balance=25_000,
        years=2,
    )
    text = format_target_home_report(rows, home_price=450_000, band_label="conservative")
    assert "Target home $450,000" in text
    assert "Min DTI" in text
    assert "Ready" in text
