"""Fixed-rate mortgage calculations."""

from __future__ import annotations

import math


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
