"""Parametrized edge-case matrix coverage for core calculator subsystems."""

from __future__ import annotations

import json

import pytest

from homeafford.check import (
    cash_required_for_purchase,
    check_affordability,
    check_purchase_readiness,
)
from homeafford.mortgage_scenario import (
    fixed_arm_decision_report,
    format_fixed_arm_decision_report_json,
    format_fixed_arm_purchase_comparison,
)
from tests.helpers.calculator_edge_matrix import (
    ARM_BOUNDARY_CASES,
    MORTGAGE_INVARIANT_CASES,
    PITI_BOUNDARY_CASES,
    SAVINGS_BOUNDARY_CASES,
    assert_arm_boundary,
    assert_mortgage_amortization_invariants,
    assert_piti_boundary,
    assert_savings_boundary,
    dti_back_end_increases_with_debt,
    matrix_case_ids,
)
from tests.helpers.edge_case_catalog import EdgeCaseCatalog, purchase_scenario


@pytest.mark.parametrize(
    "case",
    MORTGAGE_INVARIANT_CASES,
    ids=matrix_case_ids(MORTGAGE_INVARIANT_CASES),
)
def test_mortgage_invariant_matrix(case):
    assert_mortgage_amortization_invariants(case)


@pytest.mark.parametrize(
    "case",
    PITI_BOUNDARY_CASES,
    ids=matrix_case_ids(PITI_BOUNDARY_CASES),
)
def test_piti_boundary_matrix(case):
    assert_piti_boundary(case)


@pytest.mark.parametrize(
    "case",
    SAVINGS_BOUNDARY_CASES,
    ids=matrix_case_ids(SAVINGS_BOUNDARY_CASES),
)
def test_savings_boundary_matrix(case):
    assert_savings_boundary(case)


@pytest.mark.parametrize(
    "case",
    ARM_BOUNDARY_CASES,
    ids=matrix_case_ids(ARM_BOUNDARY_CASES),
)
def test_arm_boundary_matrix(case):
    assert_arm_boundary(case)


def test_dti_back_end_monotonic_with_debt():
    dti_back_end_increases_with_debt()


def test_cash_required_for_purchase_sums_down_payment_and_closing():
    scenario = purchase_scenario(down_payment=75_000, closing_costs=12_500)
    assert cash_required_for_purchase(scenario) == 87_500


def test_cash_required_for_purchase_rejects_invalid_down_payment():
    with pytest.raises(ValueError, match="down_payment cannot exceed home_price"):
        cash_required_for_purchase(
            purchase_scenario(home_price=300_000, down_payment=350_000)
        )


def test_check_affordability_fha_program_applies_lifetime_mip(edge_cases: EdgeCaseCatalog):
    result = check_affordability(
        edge_cases.fha_low_down,
        loan_program="fha",
        band_label="conservative",
    )
    assert result.down_payment_pct == pytest.approx(0.035)
    assert result.estimated_pmi_monthly > 0


def test_check_affordability_va_program_allows_zero_down(edge_cases: EdgeCaseCatalog):
    result = check_affordability(
        edge_cases.va_zero_down,
        loan_program="va",
        band_label="conservative",
    )
    assert result.loan_amount == edge_cases.va_zero_down.home_price
    assert result.down_payment_pct == 0.0
    assert result.passes_down_payment
    assert result.estimated_pmi_monthly == 0.0


def test_purchase_readiness_fails_dti_while_savings_funded(edge_cases: EdgeCaseCatalog):
    readiness = check_purchase_readiness(
        edge_cases.back_end_failure,
        starting_balance=200_000,
        monthly_contribution=0,
        annual_return=0.0,
    )
    assert readiness.passes_savings
    assert not readiness.passes_dti
    assert not readiness.passes


def test_purchase_readiness_band_label_overrides_caps(edge_cases: EdgeCaseCatalog):
    custom = check_purchase_readiness(
        edge_cases.exact_front_end_cap,
        starting_balance=100_000,
        monthly_contribution=0,
        front_end_cap=0.10,
        back_end_cap=0.10,
    )
    conservative = check_purchase_readiness(
        edge_cases.exact_front_end_cap,
        starting_balance=100_000,
        monthly_contribution=0,
        band_label="conservative",
    )
    assert custom.affordability.front_end_dti == conservative.affordability.front_end_dti
    assert custom.passes != conservative.passes


def test_high_rate_purchase_inflates_piti(edge_cases: EdgeCaseCatalog):
    baseline = check_affordability(
        purchase_scenario(
            home_price=edge_cases.high_rate_purchase.home_price,
            down_payment=edge_cases.high_rate_purchase.down_payment,
            gross_annual_income=edge_cases.high_rate_purchase.gross_annual_income,
            mortgage_rate=0.065,
        )
    )
    high_rate = check_affordability(edge_cases.high_rate_purchase)
    assert high_rate.loan_amount == baseline.loan_amount
    assert high_rate.estimated_piti > baseline.estimated_piti


def test_short_term_loan_raises_payment_and_lowers_total_interest(edge_cases: EdgeCaseCatalog):
    thirty_year = check_affordability(
        purchase_scenario(
            home_price=edge_cases.short_term_loan.home_price,
            down_payment=edge_cases.short_term_loan.down_payment,
            gross_annual_income=edge_cases.short_term_loan.gross_annual_income,
            loan_term_years=30,
        )
    )
    short_term = check_affordability(edge_cases.short_term_loan)
    assert short_term.estimated_piti > thirty_year.estimated_piti
    assert short_term.loan_amount == thirty_year.loan_amount


def test_fixed_arm_purchase_comparison_warns_on_post_adjustment_dti(
    edge_cases: EdgeCaseCatalog,
):
    from homeafford.mortgage_scenario import compare_fixed_arm_purchase

    comparison = compare_fixed_arm_purchase(
        edge_cases.arm_post_dti_failure,
        arm_intro_rate=0.0525,
        arm_adjusted_rate=0.095,
        intro_years=5,
        band_label="conservative",
    )
    text = format_fixed_arm_purchase_comparison(comparison)
    assert comparison.post_adjustment_fails_band
    assert "post-adjustment ARM payment exceeds DTI caps" in text


def test_fixed_arm_decision_report_json_round_trip(edge_cases: EdgeCaseCatalog):
    report = fixed_arm_decision_report(
        edge_cases.arm_rate_spike_purchase,
        arm_intro_rate=0.05,
        arm_adjusted_rate=0.10,
        intro_years=5,
        band_label="conservative",
    )
    payload = json.loads(format_fixed_arm_decision_report_json(report))
    assert payload["recommendation"] in {
        "fixed",
        "arm",
        "arm_with_caution",
        "inconclusive",
    }
    assert payload["purchase"]["loan"]["break_even_month"] is not None
    assert payload["purchase"]["dti"]["arm_post"]["passes_front_end"] is False
