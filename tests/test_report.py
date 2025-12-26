from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.report import affordability_report_by_year, format_affordability_report


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
    assert "Conservative" in text
    assert "Moderate" in text
    assert "Stretch" in text
    assert f"{rows[0].bands[0].max_home_price:,.0f}" in text
    assert f"{rows[-1].down_payment:,.0f}" in text
