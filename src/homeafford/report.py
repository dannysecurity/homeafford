"""Multi-year affordability projections driven by savings growth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeafford.affordability import AffordabilityBand, AffordabilityInputs, affordability_bands
from homeafford.market.resolve import resolve_snapshot
from homeafford.market.snapshot import DEFAULT_MARKET
from homeafford.savings import savings_trajectory

if TYPE_CHECKING:
    from homeafford.market.protocol import MarketDataProvider


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
    property_tax_rate: float = DEFAULT_MARKET.property_tax_rate,
    insurance_annual: float = DEFAULT_MARKET.insurance_annual,
    hoa_monthly: float = 0.0,
    loan_term_years: int = 30,
    mortgage_rate: float = DEFAULT_MARKET.mortgage_rate,
    provider: MarketDataProvider | None = None,
    market_overrides: dict[str, float | str] | None = None,
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

    if provider is not None:
        market = resolve_snapshot(
            provider,
            loan_term_years=loan_term_years,
            overrides=market_overrides,
        )
        effective_mortgage_rate = market.mortgage_rate
        effective_property_tax_rate = market.property_tax_rate
        effective_insurance_annual = market.insurance_annual
        effective_annual_return = market.savings_annual_return
    else:
        market = None
        effective_mortgage_rate = mortgage_rate
        effective_property_tax_rate = property_tax_rate
        effective_insurance_annual = insurance_annual
        effective_annual_return = annual_return

    trajectory = (
        savings_trajectory(
            starting_balance=starting_balance,
            monthly_contribution=monthly_contribution,
            annual_return=effective_annual_return,
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
                property_tax_rate=effective_property_tax_rate,
                insurance_annual=effective_insurance_annual,
                hoa_monthly=hoa_monthly,
                loan_term_years=loan_term_years,
                mortgage_rate=effective_mortgage_rate,
                market=market,
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


def format_affordability_report(rows: list[YearlyAffordabilityRow]) -> str:
    """Render a year-by-year affordability table for CLI or logging."""
    lines = [
        f"{'Year':>4}  {'Down $':>12}  {'Conservative':>14}  "
        f"{'Moderate':>14}  {'Stretch':>14}"
    ]
    for row in rows:
        by_label = {band.label: band for band in row.bands}
        lines.append(
            f"{row.year:4d}  ${row.down_payment:>10,.0f}  "
            f"${by_label['conservative'].max_home_price:>12,.0f}  "
            f"${by_label['moderate'].max_home_price:>12,.0f}  "
            f"${by_label['stretch'].max_home_price:>12,.0f}"
        )
    return "\n".join(lines)
