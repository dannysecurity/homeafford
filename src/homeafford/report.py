"""Multi-year affordability projections driven by savings growth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeafford.affordability import AffordabilityBand, AffordabilityInputs, affordability_bands
from homeafford.check import PurchaseScenario, _band_caps, check_affordability
from homeafford.market.resolve import resolve_market
from homeafford.market.snapshot import DEFAULT_MARKET
from homeafford.model import min_down_payment_for_dti
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
    metro_id: str | None = None,
    reference_year: int | None = None,
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
        market = resolve_market(
            provider,
            loan_term_years=loan_term_years,
            metro_id=metro_id,
            reference_year=reference_year,
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
        f"{'Year':>4}  {'Income $':>12}  {'Down $':>12}  {'Conservative':>14}  "
        f"{'Moderate':>14}  {'Stretch':>14}"
    ]
    for row in rows:
        by_label = {band.label: band for band in row.bands}
        lines.append(
            f"{row.year:4d}  ${row.gross_annual_income:>10,.0f}  "
            f"${row.down_payment:>10,.0f}  "
            f"${by_label['conservative'].max_home_price:>12,.0f}  "
            f"${by_label['moderate'].max_home_price:>12,.0f}  "
            f"${by_label['stretch'].max_home_price:>12,.0f}"
        )
    return "\n".join(lines)


@dataclass(frozen=True)
class TargetHomeYearlyRow:
    """Progress toward affording one target home price in a given year."""

    year: int
    gross_annual_income: float
    savings_balance: float
    down_payment: float
    min_down_for_dti: float | None
    dti_passes: bool
    savings_meets_cash_required: bool
    ready: bool


def target_home_report_by_year(
    *,
    home_price: float,
    gross_annual_income: float,
    monthly_debt_payments: float = 0.0,
    starting_balance: float = 0.0,
    monthly_contribution: float = 0.0,
    annual_return: float = 0.04,
    years: int = 5,
    income_growth_rate: float = 0.0,
    closing_costs: float = 0.0,
    band_label: str = "conservative",
    min_down_payment_pct: float = 0.03,
    property_tax_rate: float = DEFAULT_MARKET.property_tax_rate,
    insurance_annual: float = DEFAULT_MARKET.insurance_annual,
    hoa_monthly: float = 0.0,
    loan_term_years: int = 30,
    mortgage_rate: float = DEFAULT_MARKET.mortgage_rate,
    provider: MarketDataProvider | None = None,
    metro_id: str | None = None,
    reference_year: int | None = None,
    market_overrides: dict[str, float | str] | None = None,
) -> list[TargetHomeYearlyRow]:
    """Project year-by-year readiness for a fixed target home price.

    Each year uses projected savings (minus closing costs) as the down payment,
    evaluates DTI at that level, and compares against the minimum down payment
    required to satisfy DTI caps at the year's income.
    """
    if home_price <= 0:
        raise ValueError("home_price must be positive")
    if years < 0:
        raise ValueError("years must be non-negative")
    if starting_balance < 0 or monthly_contribution < 0:
        raise ValueError("starting_balance and monthly_contribution must be non-negative")
    if closing_costs < 0:
        raise ValueError("closing_costs must be non-negative")

    front_cap, back_cap = _band_caps(band_label)

    if provider is not None:
        market = resolve_market(
            provider,
            loan_term_years=loan_term_years,
            metro_id=metro_id,
            reference_year=reference_year,
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

    rows: list[TargetHomeYearlyRow] = []
    for year in range(years + 1):
        savings_balance = (
            starting_balance if year == 0 else trajectory[year * 12 - 1].balance
        )
        income = gross_annual_income * (1 + income_growth_rate) ** year
        down_payment = max(0.0, min(savings_balance - closing_costs, home_price))

        base_scenario = PurchaseScenario(
            home_price=home_price,
            down_payment=0.0,
            gross_annual_income=income,
            monthly_debt_payments=monthly_debt_payments,
            property_tax_rate=effective_property_tax_rate,
            insurance_annual=effective_insurance_annual,
            hoa_monthly=hoa_monthly,
            loan_term_years=loan_term_years,
            mortgage_rate=effective_mortgage_rate,
            closing_costs=closing_costs,
            market=market,
        )
        min_down = min_down_payment_for_dti(
            base_scenario,
            front_end_cap=front_cap,
            back_end_cap=back_cap,
            min_down_payment_pct=min_down_payment_pct,
        )

        scenario_at_down = PurchaseScenario(
            home_price=home_price,
            down_payment=down_payment,
            gross_annual_income=income,
            monthly_debt_payments=monthly_debt_payments,
            property_tax_rate=effective_property_tax_rate,
            insurance_annual=effective_insurance_annual,
            hoa_monthly=hoa_monthly,
            loan_term_years=loan_term_years,
            mortgage_rate=effective_mortgage_rate,
            closing_costs=closing_costs,
            market=market,
        )
        check = check_affordability(
            scenario_at_down,
            front_end_cap=front_cap,
            back_end_cap=back_cap,
            min_down_payment_pct=min_down_payment_pct,
            band_label=band_label,
        )
        cash_required = down_payment + closing_costs
        savings_meets = savings_balance >= cash_required
        ready = check.passes and (min_down is None or down_payment >= min_down) and savings_meets

        rows.append(
            TargetHomeYearlyRow(
                year=year,
                gross_annual_income=income,
                savings_balance=savings_balance,
                down_payment=down_payment,
                min_down_for_dti=min_down,
                dti_passes=check.passes,
                savings_meets_cash_required=savings_meets,
                ready=ready,
            )
        )

    return rows


def format_target_home_report(
    rows: list[TargetHomeYearlyRow],
    *,
    home_price: float,
    band_label: str = "conservative",
) -> str:
    """Render a year-by-year target-home readiness table."""
    lines = [
        f"Target home ${home_price:,.0f} ({band_label} band)",
        f"{'Year':>4}  {'Savings $':>12}  {'Down $':>12}  "
        f"{'Min DTI $':>12}  {'DTI':>5}  {'Save':>5}  Ready",
    ]
    for row in rows:
        min_down = (
            f"${row.min_down_for_dti:>11,.0f}"
            if row.min_down_for_dti is not None
            else "     n/a   "
        )
        lines.append(
            f"{row.year:4d}  ${row.savings_balance:>10,.0f}  "
            f"${row.down_payment:>10,.0f}  "
            f"{min_down}  "
            f"{'yes' if row.dti_passes else 'no':>5}  "
            f"{'yes' if row.savings_meets_cash_required else 'no':>5}  "
            f"{'yes' if row.ready else 'no'}"
        )
    return "\n".join(lines)
