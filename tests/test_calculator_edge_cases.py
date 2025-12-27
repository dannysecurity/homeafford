"""Edge-case coverage for mortgage, PITI, and savings calculators."""

import pytest

from homeafford.mortgage import (
    compare_fixed_vs_arm,
    mortgage_payment,
    remaining_balance,
    total_interest,
)
from homeafford.piti import compute_dti_ratios, compute_piti
from homeafford.savings import savings_trajectory


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
