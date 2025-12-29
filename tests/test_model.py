from homeafford.check import PurchaseScenario, check_against_band
from homeafford.model import (
    min_down_payment_for_dti,
    model_down_payment_dti,
)


def _scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=500_000,
        down_payment=50_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_model_sweep_marks_low_down_as_failing():
    model = model_down_payment_dti(
        _scenario(),
        down_payment_pcts=(0.03, 0.20),
        band_label="conservative",
    )
    assert len(model.rows) == 2
    low, high = model.rows
    assert low.down_payment_pct == 0.03
    assert high.down_payment_pct == 0.20
    assert not low.check.passes or high.check.passes
    assert model.band_label == "conservative"


def test_model_reports_min_down_payment():
    model = model_down_payment_dti(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        band_label="conservative",
    )
    assert model.min_down_payment is not None
    assert model.min_down_payment_pct is not None
    assert model.min_down_payment >= 600_000 * 0.03
    verify = check_against_band(
        PurchaseScenario(
            home_price=600_000,
            down_payment=model.min_down_payment,
            gross_annual_income=120_000,
            monthly_debt_payments=450,
        ),
        band_label="conservative",
    )
    assert verify.passes_front_end
    assert verify.passes_back_end


def test_min_down_payment_at_band_boundary():
    scenario = _scenario(
        home_price=600_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
    )
    min_down = min_down_payment_for_dti(scenario, band_label="conservative")
    assert min_down is not None
    just_below = min_down - 500
    result_below = check_against_band(
        PurchaseScenario(
            home_price=scenario.home_price,
            down_payment=just_below,
            gross_annual_income=scenario.gross_annual_income,
            monthly_debt_payments=scenario.monthly_debt_payments,
        ),
        band_label="conservative",
    )
    assert not result_below.passes_front_end or not result_below.passes_back_end


def test_min_down_payment_none_when_debt_exceeds_back_end_cap():
    scenario = _scenario(
        gross_annual_income=60_000,
        monthly_debt_payments=2_500,
    )
    assert min_down_payment_for_dti(scenario, band_label="conservative") is None


def test_model_rows_include_dti_and_pmi_details():
    model = model_down_payment_dti(_scenario(), down_payment_pcts=(0.05,))
    row = model.rows[0]
    assert row.check.estimated_piti > 0
    assert row.check.front_end_dti > 0
    assert row.check.back_end_dti > 0
    assert row.check.ltv == 0.95
    assert row.check.pmi_required
