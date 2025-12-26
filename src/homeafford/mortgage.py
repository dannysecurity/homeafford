"""Fixed-rate and adjustable-rate mortgage calculations."""

from __future__ import annotations

from dataclasses import dataclass


def mortgage_payment(*, principal: float, annual_rate: float, term_years: int) -> float:
    """Monthly principal-and-interest payment for a fully amortizing loan."""
    if principal <= 0:
        raise ValueError("principal must be positive")
    if term_years <= 0:
        raise ValueError("term_years must be positive")

    n = term_years * 12
    if annual_rate == 0:
        return principal / n

    monthly_rate = annual_rate / 12
    factor = (1 + monthly_rate) ** n
    return principal * monthly_rate * factor / (factor - 1)


def remaining_balance(
    *,
    principal: float,
    annual_rate: float,
    term_years: int,
    months_paid: int,
) -> float:
    """Outstanding loan balance after a number of payments."""
    if months_paid < 0:
        raise ValueError("months_paid must be non-negative")

    n = term_years * 12
    if months_paid >= n:
        return 0.0

    payment = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    )
    if annual_rate == 0:
        return max(0.0, principal - payment * months_paid)

    monthly_rate = annual_rate / 12
    factor = (1 + monthly_rate) ** months_paid
    balance = principal * factor - payment * (factor - 1) / monthly_rate
    return max(0.0, balance)


def total_interest(*, principal: float, annual_rate: float, term_years: int) -> float:
    """Total interest paid over the full loan term."""
    payment = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    )
    return payment * term_years * 12 - principal


@dataclass(frozen=True)
class FixedVsArmComparison:
    """Side-by-side fixed-rate and ARM payment scenario."""

    fixed_payment: float
    arm_intro_payment: float
    arm_post_adjustment_payment: float
    arm_balance_at_adjustment: float
    intro_years: int


def compare_fixed_vs_arm(
    *,
    principal: float,
    term_years: int,
    fixed_rate: float,
    arm_intro_rate: float,
    arm_adjusted_rate: float,
    intro_years: int = 5,
) -> FixedVsArmComparison:
    """Compare a fixed-rate loan with a hybrid ARM (e.g. 5/1).

    During the intro period the ARM amortizes at ``arm_intro_rate`` over the
    full term. After ``intro_years``, the remaining balance is re-amortized at
    ``arm_adjusted_rate`` for the remaining term.
    """
    if intro_years <= 0:
        raise ValueError("intro_years must be positive")
    if intro_years >= term_years:
        raise ValueError("intro_years must be less than term_years")

    fixed_payment = mortgage_payment(
        principal=principal, annual_rate=fixed_rate, term_years=term_years
    )
    arm_intro_payment = mortgage_payment(
        principal=principal, annual_rate=arm_intro_rate, term_years=term_years
    )
    intro_months = intro_years * 12
    arm_balance_at_adjustment = remaining_balance(
        principal=principal,
        annual_rate=arm_intro_rate,
        term_years=term_years,
        months_paid=intro_months,
    )
    remaining_years = term_years - intro_years
    arm_post_adjustment_payment = mortgage_payment(
        principal=arm_balance_at_adjustment,
        annual_rate=arm_adjusted_rate,
        term_years=remaining_years,
    )
    return FixedVsArmComparison(
        fixed_payment=fixed_payment,
        arm_intro_payment=arm_intro_payment,
        arm_post_adjustment_payment=arm_post_adjustment_payment,
        arm_balance_at_adjustment=arm_balance_at_adjustment,
        intro_years=intro_years,
    )
