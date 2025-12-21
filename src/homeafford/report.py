"""Multi-year affordability projections driven by savings growth."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.affordability import AffordabilityBand, AffordabilityInputs, affordability_bands
from homeafford.savings import savings_trajectory


@dataclass(frozen=True)
class YearlyAffordabilityRow:
    """Affordability bands for a single year in a savings projection."""

    year: int
    down_payment: float
    gross_annual_income: float
    bands: tuple[AffordabilityBand, ...]


def affordability_report_by_year(
    *,
    gross_annual_income: float,
    monthly_debt_payments: float = 0.0,
    starting_balance: float = 0.0,
    monthly_contribution: float = 0.0,
    annual_return: float = 0.04,
    years: int = 5,
    income_growth_rate: float = 0.0,
    property_tax_rate: float = 0.012,
    insurance_annual: float = 1_200.0,
    hoa_monthly: float = 0.0,
    loan_term_years: int = 30,
    mortgage_rate: float = 0.065,
) -> list[YearlyAffordabilityRow]:
    """Project affordability bands year-by-year as savings accumulate.

    Year 0 uses ``starting_balance`` as the down payment. Each subsequent year
    uses the projected savings balance after 12 additional months of contributions
    and compound growth. Income compounds annually when ``income_growth_rate`` is
    set.
    """
    if years < 0:
        raise ValueError("years must be non-negative")
    if starting_balance < 0 or monthly_contribution < 0:
        raise ValueError("starting_balance and monthly_contribution must be non-negative")

    trajectory = (
        savings_trajectory(
            starting_balance=starting_balance,
            monthly_contribution=monthly_contribution,
            annual_return=annual_return,
            months=years * 12,
        )
        if years > 0
        else []
    )

    rows: list[YearlyAffordabilityRow] = []
    for year in range(years + 1):
        down_payment = starting_balance if year == 0 else trajectory[year * 12 - 1].balance
        income = gross_annual_income * (1 + income_growth_rate) ** year
        bands = affordability_bands(
            AffordabilityInputs(
                gross_annual_income=income,
                monthly_debt_payments=monthly_debt_payments,
                down_payment=down_payment,
                property_tax_rate=property_tax_rate,
                insurance_annual=insurance_annual,
                hoa_monthly=hoa_monthly,
                loan_term_years=loan_term_years,
                mortgage_rate=mortgage_rate,
            )
        )
        rows.append(
            YearlyAffordabilityRow(
                year=year,
                down_payment=down_payment,
                gross_annual_income=income,
                bands=tuple(bands),
            )
        )

    return rows
