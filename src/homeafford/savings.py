"""Monthly savings projection with compound growth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SavingsSnapshot:
    """Account state at the end of a month."""

    month: int
    balance: float
    contributions: float
    growth: float


def savings_trajectory(
    *,
    starting_balance: float,
    monthly_contribution: float,
    annual_return: float,
    months: int,
) -> list[SavingsSnapshot]:
    """Project savings month-by-month with monthly compounding."""
    if months < 0:
        raise ValueError("months must be non-negative")
    if starting_balance < 0 or monthly_contribution < 0:
        raise ValueError("starting_balance and monthly_contribution must be non-negative")

    monthly_rate = (1 + annual_return) ** (1 / 12) - 1
    balance = starting_balance
    snapshots: list[SavingsSnapshot] = []

    for month in range(1, months + 1):
        growth = balance * monthly_rate
        balance = balance + growth + monthly_contribution
        snapshots.append(
            SavingsSnapshot(
                month=month,
                balance=balance,
                contributions=monthly_contribution,
                growth=growth,
            )
        )

    return snapshots
