"""Edge-case coverage for mortgage, PITI, savings, purchase, and ARM calculators."""

import pytest

from homeafford.check import (
    check_affordability,
    check_purchase_readiness,
)
from homeafford.mortgage import (
    compare_fixed_vs_arm,
    mortgage_payment,
    remaining_balance,
    total_interest,
)
from homeafford.mortgage_scenario import analyze_fixed_arm_scenario, format_fixed_arm_scenario
from homeafford.piti import compute_dti_ratios, compute_piti
from homeafford.savings import savings_trajectory
from tests.helpers.edge_case_catalog import EdgeCaseCatalog, fixed_arm_inputs, purchase_scenario


def test_mortgage_payment_rejects_non_positive_principal():
    with pytest.raises(ValueError, match="principal must be positive"):
        mortgage_payment(principal=0, annual_rate=0.05, term_years=30)
    with pytest.raises(ValueError, match="principal must be positive"):
        mortgage_payment(principal=-1, annual_rate=0.05, term_years=30)


def test_mortgage_payment_rejects_non_positive_term():
    with pytest.raises(ValueError, match="term_years must be positive"):
        mortgage_payment(principal=100_000, annual_rate=0.05, term_years=0)


def test_remaining_balance_at_start_equals_principal():
    balance = remaining_balance(
        principal=250_000,
        annual_rate=0.06,
        term_years=30,
        months_paid=0,
    )
    assert balance == 250_000


def test_remaining_balance_zero_after_full_term():
    balance = remaining_balance(
        principal=200_000,
        annual_rate=0.05,
        term_years=15,
        months_paid=15 * 12,
    )
    assert balance == 0.0


def test_remaining_balance_zero_beyond_full_term():
    balance = remaining_balance(
        principal=200_000,
        annual_rate=0.05,
        term_years=15,
        months_paid=15 * 12 + 6,
    )
    assert balance == 0.0


def test_remaining_balance_rejects_negative_months_paid():
    with pytest.raises(ValueError, match="months_paid must be non-negative"):
        remaining_balance(
            principal=200_000,
            annual_rate=0.05,
            term_years=30,
            months_paid=-1,
        )


def test_total_interest_zero_for_zero_rate():
    assert total_interest(principal=150_000, annual_rate=0.0, term_years=30) == 0.0


def test_compare_fixed_vs_arm_rejects_non_positive_intro_years():
    with pytest.raises(ValueError, match="intro_years must be positive"):
        compare_fixed_vs_arm(
            principal=400_000,
            term_years=30,
            fixed_rate=0.065,
            arm_intro_rate=0.055,
            arm_adjusted_rate=0.075,
            intro_years=0,
        )


def test_savings_trajectory_empty_when_zero_months():
    assert savings_trajectory(
        starting_balance=5_000,
        monthly_contribution=100,
        annual_return=0.04,
        months=0,
    ) == []


def test_savings_trajectory_rejects_negative_months():
    with pytest.raises(ValueError, match="months must be non-negative"):
        savings_trajectory(
            starting_balance=5_000,
            monthly_contribution=100,
            annual_return=0.04,
            months=-1,
        )


def test_savings_trajectory_rejects_negative_inputs():
    with pytest.raises(
        ValueError,
        match="starting_balance and monthly_contribution must be non-negative",
    ):
        savings_trajectory(
            starting_balance=-1,
            monthly_contribution=100,
            annual_return=0.04,
            months=12,
        )


def test_compute_piti_zero_loan_has_no_principal_and_interest():
    breakdown = compute_piti(
        loan_amount=0,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=50,
        mortgage_rate=0.065,
        loan_term_years=30,
    )
    assert breakdown.principal_and_interest == 0.0
    assert breakdown.piti == breakdown.insurance_monthly + breakdown.hoa_monthly


def test_compute_piti_rejects_negative_loan_amount():
    with pytest.raises(ValueError, match="loan_amount must be non-negative"):
        compute_piti(
            loan_amount=-1,
            property_tax_rate=0.012,
            insurance_annual=1_200,
            hoa_monthly=0,
            mortgage_rate=0.065,
            loan_term_years=30,
        )


def test_compute_dti_ratios_zero_when_income_non_positive():
    assert compute_dti_ratios(
        piti=2_000,
        gross_annual_income=0,
        monthly_debt_payments=500,
    ) == (0.0, 0.0)


def test_compute_dti_ratios_zero_when_income_negative():
    assert compute_dti_ratios(
        piti=2_000,
        gross_annual_income=-50_000,
        monthly_debt_payments=500,
    ) == (0.0, 0.0)


def test_remaining_balance_zero_rate_linear_paydown():
    balance = remaining_balance(
        principal=120_000,
        annual_rate=0.0,
        term_years=10,
        months_paid=60,
    )
    assert balance == pytest.approx(60_000)


def test_mortgage_payment_zero_rate_divides_evenly():
    payment = mortgage_payment(principal=360_000, annual_rate=0.0, term_years=30)
    assert payment == pytest.approx(1_000)


def test_savings_trajectory_compounds_annual_return():
    snaps = savings_trajectory(
        starting_balance=1_000,
        monthly_contribution=0,
        annual_return=0.12,
        months=12,
    )
    assert snaps[-1].balance == pytest.approx(1_120, rel=1e-9)
    assert snaps[-1].growth > 0


def test_savings_trajectory_rejects_negative_contribution():
    with pytest.raises(
        ValueError,
        match="starting_balance and monthly_contribution must be non-negative",
    ):
        savings_trajectory(
            starting_balance=1_000,
            monthly_contribution=-50,
            annual_return=0.04,
            months=6,
        )


def test_compute_piti_zero_rate_on_nonzero_loan():
    breakdown = compute_piti(
        loan_amount=240_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.0,
        loan_term_years=30,
    )
    assert breakdown.principal_and_interest == pytest.approx(666.67, rel=1e-3)
    assert breakdown.piti == pytest.approx(
        breakdown.principal_and_interest
        + breakdown.tax_monthly
        + breakdown.insurance_monthly,
        rel=1e-9,
    )


def test_compare_fixed_vs_arm_equal_intro_and_fixed_rates():
    comparison = compare_fixed_vs_arm(
        principal=300_000,
        term_years=30,
        fixed_rate=0.06,
        arm_intro_rate=0.06,
        arm_adjusted_rate=0.07,
        intro_years=5,
    )
    assert comparison.fixed_payment == pytest.approx(comparison.arm_intro_payment)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("home_price", 0, "home_price must be positive"),
        ("down_payment", -1, "down_payment must be non-negative"),
        ("gross_annual_income", 0, "gross_annual_income must be positive"),
        ("closing_costs", -100, "closing_costs must be non-negative"),
    ],
)
def test_purchase_scenario_validation(field, value, message):
    overrides = {field: value}
    if field == "down_payment" and value < 0:
        overrides["home_price"] = 500_000
    with pytest.raises(ValueError, match=message):
        check_affordability(purchase_scenario(**overrides))


def test_purchase_scenario_rejects_down_payment_exceeding_price():
    with pytest.raises(ValueError, match="down_payment cannot exceed home_price"):
        check_affordability(
            purchase_scenario(home_price=300_000, down_payment=350_000)
        )


def test_check_fails_front_end_while_back_end_passes(edge_cases: EdgeCaseCatalog):
    result = check_affordability(
        edge_cases.front_end_failure,
        front_end_cap=0.28,
        back_end_cap=0.43,
    )
    assert not result.passes_front_end
    assert result.passes_back_end
    assert any("front-end DTI" in reason for reason in result.reasons)


def test_check_all_cash_purchase_has_zero_loan(edge_cases: EdgeCaseCatalog):
    result = check_affordability(edge_cases.all_cash_purchase)
    assert result.loan_amount == 0.0
    assert result.estimated_piti == pytest.approx(
        edge_cases.all_cash_purchase.insurance_annual / 12
        + edge_cases.all_cash_purchase.hoa_monthly,
        rel=1e-6,
    )


def test_check_pmi_not_required_at_exactly_eighty_percent_ltv(edge_cases: EdgeCaseCatalog):
    result = check_affordability(edge_cases.pmi_threshold_ltv)
    assert result.ltv == pytest.approx(0.8)
    assert not result.pmi_required


def test_purchase_readiness_already_funded_returns_zero_months():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=50_000, closing_costs=5_000),
        starting_balance=60_000,
        monthly_contribution=0,
    )
    assert readiness.passes_savings
    assert readiness.months_until_ready is None


def test_purchase_readiness_unreachable_goal_returns_none():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=200_000, closing_costs=20_000),
        starting_balance=1_000,
        monthly_contribution=100,
        annual_return=0.0,
    )
    assert not readiness.passes_savings
    assert readiness.months_until_ready is None


def test_purchase_readiness_with_target_months():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=60_000, closing_costs=10_000),
        starting_balance=20_000,
        monthly_contribution=5_000,
        annual_return=0.0,
        target_months=12,
    )
    assert readiness.projected_balance == pytest.approx(80_000)
    assert readiness.passes_savings
    assert readiness.cash_required == 70_000
    assert readiness.months_until_ready is None


def test_purchase_readiness_rejects_negative_savings_inputs():
    with pytest.raises(
        ValueError,
        match="starting_balance and monthly_contribution must be non-negative",
    ):
        check_purchase_readiness(
            purchase_scenario(),
            starting_balance=-1,
            monthly_contribution=500,
        )


def test_arm_scenario_no_break_even_when_arm_always_cheaper(edge_cases: EdgeCaseCatalog):
    result = analyze_fixed_arm_scenario(edge_cases.arm_always_cheaper)
    assert result.break_even_month is None
    assert result.cheaper_over_full_term == "arm"


def test_arm_scenario_tie_when_total_costs_equal(edge_cases: EdgeCaseCatalog):
    result = analyze_fixed_arm_scenario(edge_cases.flat_arm_rates)
    assert result.cheaper_over_full_term == "tie"
    assert result.arm_savings_during_intro == pytest.approx(0.0)


def test_arm_scenario_rejects_non_positive_term():
    with pytest.raises(ValueError, match="term_years must be positive"):
        analyze_fixed_arm_scenario(fixed_arm_inputs(term_years=0))


def test_arm_scenario_rejects_intro_years_not_shorter_than_term():
    with pytest.raises(ValueError, match="intro_years must be less than term_years"):
        analyze_fixed_arm_scenario(fixed_arm_inputs(intro_years=30, term_years=30))


def test_arm_seven_one_longer_intro_accumulates_more_savings(edge_cases: EdgeCaseCatalog):
    seven_one = analyze_fixed_arm_scenario(edge_cases.arm_seven_one)
    five_one = analyze_fixed_arm_scenario(
        fixed_arm_inputs(
            fixed_rate=0.0625,
            arm_intro_rate=0.0525,
            arm_adjusted_rate=0.0725,
            intro_years=5,
        )
    )
    assert seven_one.inputs.intro_years == 7
    assert seven_one.arm_savings_during_intro > five_one.arm_savings_during_intro
    assert seven_one.break_even_month is not None
    assert seven_one.break_even_month > five_one.break_even_month


def test_format_arm_scenario_without_break_even():
    result = analyze_fixed_arm_scenario(
        fixed_arm_inputs(
            fixed_rate=0.07,
            arm_intro_rate=0.05,
            arm_adjusted_rate=0.055,
        )
    )
    text = format_fixed_arm_scenario(result)
    assert "ARM never exceeds fixed cumulative cost" in text
