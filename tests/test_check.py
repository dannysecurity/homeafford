from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.check import (
    PurchaseScenario,
    check_affordability,
    check_against_band,
    check_purchase_readiness,
)
from homeafford.piti import compute_piti


def _scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_check_passes_at_conservative_band_ceiling():
    inputs = AffordabilityInputs(
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        down_payment=60_000,
    )
    ceiling = affordability_bands(inputs)[0].max_home_price
    result = check_against_band(
        PurchaseScenario(
            home_price=ceiling,
            down_payment=60_000,
            gross_annual_income=120_000,
            monthly_debt_payments=450,
        ),
        band_label="conservative",
    )
    assert result.passes
    assert result.passes_front_end
    assert result.passes_back_end


def test_check_fails_when_back_end_dti_exceeded():
    result = check_affordability(
        _scenario(home_price=700_000, down_payment=50_000, monthly_debt_payments=1_500),
        front_end_cap=0.28,
        back_end_cap=0.36,
    )
    assert not result.passes
    assert not result.passes_back_end
    assert any("back-end DTI" in reason for reason in result.reasons)


def test_check_fails_insufficient_down_payment():
    result = check_affordability(
        _scenario(home_price=400_000, down_payment=8_000),
        min_down_payment_pct=0.20,
    )
    assert not result.passes_down_payment
    assert result.down_payment_pct == 0.02
    assert any("down payment" in reason for reason in result.reasons)


def test_check_fails_below_default_three_percent_down():
    result = check_affordability(_scenario(home_price=500_000, down_payment=10_000))
    assert not result.passes
    assert not result.passes_down_payment
    assert result.down_payment_pct == 0.02
    assert any("down payment" in reason for reason in result.reasons)


def test_check_ltv_and_pmi_flag():
    result = check_affordability(_scenario(home_price=500_000, down_payment=50_000))
    assert result.ltv == 0.9
    assert result.pmi_required

    result_no_pmi = check_affordability(_scenario(home_price=500_000, down_payment=100_000))
    assert result_no_pmi.ltv == 0.8
    assert not result_no_pmi.pmi_required


def test_compute_piti_matches_affordability_assumptions():
    breakdown = compute_piti(
        loan_amount=300_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=150,
        mortgage_rate=0.065,
        loan_term_years=30,
    )
    assert breakdown.piti == (
        breakdown.principal_and_interest
        + breakdown.tax_monthly
        + breakdown.insurance_monthly
        + breakdown.hoa_monthly
    )
    assert breakdown.tax_monthly == 300


def test_purchase_readiness_passes_with_enough_savings():
    readiness = check_purchase_readiness(
        _scenario(down_payment=80_000, closing_costs=15_000),
        starting_balance=100_000,
        monthly_contribution=0,
    )
    assert readiness.passes_savings
    assert readiness.cash_required == 95_000
    assert readiness.months_until_ready is None


def test_purchase_readiness_projects_months_until_down_payment():
    readiness = check_purchase_readiness(
        _scenario(down_payment=60_000, closing_costs=10_000),
        starting_balance=20_000,
        monthly_contribution=2_000,
        annual_return=0.0,
    )
    assert not readiness.passes_savings
    assert readiness.months_until_ready == 25


def test_check_against_band_unknown_label_raises():
    try:
        check_against_band(_scenario(), band_label="aggressive")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "aggressive" in str(exc)
