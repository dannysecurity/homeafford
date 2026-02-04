from homeafford.check import PurchaseScenario, check_against_band
from homeafford.model import (
    format_down_payment_dti_model,
    format_purchase_affordability_plan,
    min_down_payment_for_dti,
    model_down_payment_dti,
    plan_purchase_affordability,
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


def test_format_down_payment_dti_model_includes_sweep_and_min_down():
    model = model_down_payment_dti(_scenario(), down_payment_pcts=(0.05, 0.20))
    text = format_down_payment_dti_model(model)
    assert "Down payment vs DTI model" in text
    assert "Minimum down for DTI pass" in text
    assert "5.0%" in text
    assert "20.0%" in text
    assert "DTI" in text
    assert "All" in text


def test_format_down_payment_dti_model_separates_dti_from_down_floor():
    """DTI column reflects front/back caps only, not lender down minimums."""
    model = model_down_payment_dti(
        _scenario(
            home_price=400_000,
            gross_annual_income=200_000,
            monthly_debt_payments=0,
        ),
        down_payment_pcts=(0.02, 0.20),
        band_label="conservative",
    )
    low, high = model.rows
    assert low.check.passes_front_end and low.check.passes_back_end
    assert not low.check.passes
    assert high.check.passes
    text = format_down_payment_dti_model(model)
    lines = text.splitlines()
    low_line = next(line for line in lines if line.strip().startswith("2.0%"))
    high_line = next(line for line in lines if line.strip().startswith("20.0%"))
    assert low_line.rstrip().endswith("yes  no")
    assert high_line.rstrip().endswith("yes  yes")


def test_plan_purchase_affordability_ready_when_savings_cover_min_down():
    scenario = _scenario(
        home_price=500_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
        closing_costs=10_000,
    )
    plan = plan_purchase_affordability(
        scenario,
        starting_balance=200_000,
        monthly_contribution=0,
        band_label="conservative",
    )
    assert plan.min_down_payment is not None
    assert plan.passes_dti_at_min_down
    assert plan.passes_savings
    assert plan.ready_to_buy
    assert plan.cash_required == plan.min_down_payment + 10_000
    assert plan.months_until_ready is None


def test_plan_purchase_affordability_projects_months_until_ready():
    scenario = _scenario(
        home_price=600_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        closing_costs=12_000,
    )
    plan = plan_purchase_affordability(
        scenario,
        starting_balance=20_000,
        monthly_contribution=2_500,
        annual_return=0.0,
        band_label="conservative",
    )
    assert plan.min_down_payment is not None
    assert not plan.ready_to_buy
    assert not plan.passes_savings
    assert plan.months_until_ready is not None
    assert plan.months_until_ready > 0


def test_plan_purchase_affordability_unreachable_when_debt_too_high():
    scenario = _scenario(
        gross_annual_income=60_000,
        monthly_debt_payments=2_500,
    )
    plan = plan_purchase_affordability(
        scenario,
        starting_balance=100_000,
        monthly_contribution=1_000,
        band_label="conservative",
    )
    assert plan.min_down_payment is None
    assert not plan.ready_to_buy
    text = format_purchase_affordability_plan(plan)
    assert "cannot be met" in text


def test_plan_dti_model_matches_standalone_model():
    scenario = _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450)
    standalone = model_down_payment_dti(scenario, band_label="conservative")
    plan = plan_purchase_affordability(
        scenario,
        starting_balance=0,
        monthly_contribution=0,
        band_label="conservative",
    )
    assert plan.dti_model.min_down_payment == standalone.min_down_payment
    assert len(plan.dti_model.rows) == len(standalone.rows)
