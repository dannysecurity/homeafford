"""Parametrized edge-case matrix for mortgage, PITI, savings, and ARM calculators.

Centralizes boundary inputs with shared invariant checks so calculator pytest
suites can sweep many configurations through one parametrized table instead of
duplicating near-identical assertions across files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from homeafford.mortgage import (
    compare_fixed_vs_arm,
    mortgage_payment,
    remaining_balance,
    total_interest,
)
from homeafford.mortgage_scenario import FixedArmScenarioInputs, analyze_fixed_arm_scenario
from homeafford.piti import compute_dti_ratios, compute_piti
from homeafford.savings import savings_trajectory


@dataclass(frozen=True)
class MortgageInvariantCase:
    """Loan configuration whose amortization math must satisfy core identities."""

    label: str
    principal: float
    annual_rate: float
    term_years: int


@dataclass(frozen=True)
class PitiBoundaryCase:
    """PITI inputs with expected monthly component totals."""

    label: str
    loan_amount: float
    property_tax_rate: float
    insurance_annual: float
    hoa_monthly: float
    mortgage_rate: float
    loan_term_years: int
    home_price: float | None
    pmi_annual_rate: float
    expected_pmi_monthly: float
    expected_piti_min: float


@dataclass(frozen=True)
class SavingsBoundaryCase:
    """Savings projection inputs with expected terminal balance."""

    label: str
    starting_balance: float
    monthly_contribution: float
    annual_return: float
    months: int
    expected_balance: float


@dataclass(frozen=True)
class ArmBoundaryCase:
    """Hybrid ARM configuration with expected cost ordering."""

    label: str
    principal: float
    term_years: int
    fixed_rate: float
    arm_intro_rate: float
    arm_adjusted_rate: float
    intro_years: int
    expected_cheaper: str
    expect_break_even: bool


MORTGAGE_INVARIANT_CASES: tuple[MortgageInvariantCase, ...] = (
    MortgageInvariantCase("standard_30yr", 320_000, 0.065, 30),
    MortgageInvariantCase("zero_rate_15yr", 180_000, 0.0, 15),
    MortgageInvariantCase("high_rate_jumbo", 1_200_000, 0.085, 30),
    MortgageInvariantCase("short_term_5yr", 95_000, 0.0475, 5),
    MortgageInvariantCase("one_year_balloon_style", 60_000, 0.06, 1),
    MortgageInvariantCase("micro_loan", 25_000, 0.055, 10),
)

PITI_BOUNDARY_CASES: tuple[PitiBoundaryCase, ...] = (
    PitiBoundaryCase(
        label="zero_loan_hoa_only",
        loan_amount=0,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=275,
        mortgage_rate=0.065,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.005,
        expected_pmi_monthly=0.0,
        expected_piti_min=375.0,
    ),
    PitiBoundaryCase(
        label="high_ltv_with_pmi",
        loan_amount=475_000,
        property_tax_rate=0.011,
        insurance_annual=1_800,
        hoa_monthly=0,
        mortgage_rate=0.0625,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.005,
        expected_pmi_monthly=475_000 * 0.005 / 12,
        expected_piti_min=3_000,
    ),
    PitiBoundaryCase(
        label="exact_eighty_ltv_no_pmi",
        loan_amount=400_000,
        property_tax_rate=0.01,
        insurance_annual=1_200,
        hoa_monthly=50,
        mortgage_rate=0.06,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.005,
        expected_pmi_monthly=0.0,
        expected_piti_min=2_500,
    ),
)

SAVINGS_BOUNDARY_CASES: tuple[SavingsBoundaryCase, ...] = (
    SavingsBoundaryCase(
        label="single_month_contribution",
        starting_balance=1_000,
        monthly_contribution=500,
        annual_return=0.0,
        months=1,
        expected_balance=1_500,
    ),
    SavingsBoundaryCase(
        label="twelve_month_zero_return",
        starting_balance=2_000,
        monthly_contribution=250,
        annual_return=0.0,
        months=12,
        expected_balance=5_000,
    ),
    SavingsBoundaryCase(
        label="growth_only_no_contributions",
        starting_balance=10_000,
        monthly_contribution=0,
        annual_return=0.06,
        months=24,
        expected_balance=11_236.0,
    ),
    SavingsBoundaryCase(
        label="steep_negative_return",
        starting_balance=8_000,
        monthly_contribution=100,
        annual_return=-0.24,
        months=6,
        expected_balance=7_541.33,
    ),
)

ARM_BOUNDARY_CASES: tuple[ArmBoundaryCase, ...] = (
    ArmBoundaryCase(
        label="one_year_intro_before_adjustment",
        principal=250_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.08,
        intro_years=1,
        expected_cheaper="fixed",
        expect_break_even=True,
    ),
    ArmBoundaryCase(
        label="ten_six_hybrid_low_post_rate",
        principal=500_000,
        term_years=30,
        fixed_rate=0.07,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.06,
        intro_years=10,
        expected_cheaper="arm",
        expect_break_even=False,
    ),
    ArmBoundaryCase(
        label="max_intro_window",
        principal=350_000,
        term_years=15,
        fixed_rate=0.06,
        arm_intro_rate=0.05,
        arm_adjusted_rate=0.075,
        intro_years=14,
        expected_cheaper="arm",
        expect_break_even=False,
    ),
)


def assert_mortgage_amortization_invariants(case: MortgageInvariantCase) -> None:
    """Verify standard amortization identities for one loan configuration."""
    payment = mortgage_payment(
        principal=case.principal,
        annual_rate=case.annual_rate,
        term_years=case.term_years,
    )
    n = case.term_years * 12
    interest = total_interest(
        principal=case.principal,
        annual_rate=case.annual_rate,
        term_years=case.term_years,
    )

    assert payment > 0
    assert payment * n >= case.principal
    assert interest == pytest.approx(payment * n - case.principal)
    assert remaining_balance(
        principal=case.principal,
        annual_rate=case.annual_rate,
        term_years=case.term_years,
        months_paid=0,
    ) == case.principal
    assert remaining_balance(
        principal=case.principal,
        annual_rate=case.annual_rate,
        term_years=case.term_years,
        months_paid=n,
    ) == 0.0

    prior = case.principal
    for months_paid in range(1, n):
        balance = remaining_balance(
            principal=case.principal,
            annual_rate=case.annual_rate,
            term_years=case.term_years,
            months_paid=months_paid,
        )
        assert 0 <= balance <= prior
        prior = balance


def assert_piti_boundary(case: PitiBoundaryCase) -> None:
    """Verify PITI component totals for one boundary configuration."""
    breakdown = compute_piti(
        loan_amount=case.loan_amount,
        property_tax_rate=case.property_tax_rate,
        insurance_annual=case.insurance_annual,
        hoa_monthly=case.hoa_monthly,
        mortgage_rate=case.mortgage_rate,
        loan_term_years=case.loan_term_years,
        home_price=case.home_price,
        pmi_annual_rate=case.pmi_annual_rate,
    )
    assert breakdown.pmi_monthly == pytest.approx(case.expected_pmi_monthly)
    assert breakdown.piti == pytest.approx(
        breakdown.principal_and_interest
        + breakdown.tax_monthly
        + breakdown.insurance_monthly
        + breakdown.pmi_monthly
        + breakdown.hoa_monthly,
        rel=1e-9,
    )
    assert breakdown.piti >= case.expected_piti_min


def assert_savings_boundary(case: SavingsBoundaryCase) -> None:
    """Verify terminal savings balance for one boundary configuration."""
    snaps = savings_trajectory(
        starting_balance=case.starting_balance,
        monthly_contribution=case.monthly_contribution,
        annual_return=case.annual_return,
        months=case.months,
    )
    assert len(snaps) == case.months
    assert snaps[-1].balance == pytest.approx(case.expected_balance, rel=1e-2)
    assert snaps[-1].month == case.months


def assert_arm_boundary(case: ArmBoundaryCase) -> None:
    """Verify ARM cost ordering and break-even expectations."""
    inputs = FixedArmScenarioInputs(
        principal=case.principal,
        term_years=case.term_years,
        fixed_rate=case.fixed_rate,
        arm_intro_rate=case.arm_intro_rate,
        arm_adjusted_rate=case.arm_adjusted_rate,
        intro_years=case.intro_years,
    )
    result = analyze_fixed_arm_scenario(inputs)
    comparison = compare_fixed_vs_arm(
        principal=case.principal,
        term_years=case.term_years,
        fixed_rate=case.fixed_rate,
        arm_intro_rate=case.arm_intro_rate,
        arm_adjusted_rate=case.arm_adjusted_rate,
        intro_years=case.intro_years,
    )

    assert result.cheaper_over_full_term == case.expected_cheaper
    if case.expect_break_even:
        assert result.break_even_month is not None
        assert result.break_even_month > case.intro_years * 12
    else:
        assert result.break_even_month is None

    assert comparison.arm_balance_at_adjustment < case.principal
    assert comparison.arm_balance_at_adjustment > 0


def dti_back_end_increases_with_debt() -> None:
    """Back-end DTI rises monotonically as non-housing debt increases."""
    piti = 2_100
    income = 96_000
    prior = 0.0
    for debt in (0, 200, 450, 900):
        _, back_end = compute_dti_ratios(
            piti=piti,
            gross_annual_income=income,
            monthly_debt_payments=debt,
        )
        assert back_end >= prior
        prior = back_end


def matrix_case_ids(cases: tuple[object, ...], attr: str = "label") -> Callable[[object], str]:
    """Build pytest ids from a matrix row's label field."""

    def _case_id(case: object) -> str:
        return getattr(case, attr)

    return _case_id
