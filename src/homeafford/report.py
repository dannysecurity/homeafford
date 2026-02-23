"""Multi-year affordability projections driven by savings growth."""

from __future__ import annotations

import json
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


def affordability_price_range(row: YearlyAffordabilityRow) -> tuple[float, float]:
    """Return conservative (low) and stretch (high) max home prices for one year."""
    by_label = {band.label: band for band in row.bands}
    return (
        by_label["conservative"].max_home_price,
        by_label["stretch"].max_home_price,
    )


@dataclass(frozen=True)
class AffordabilityRangeRow:
    """Conservative–stretch price range for one projection year."""

    year: int
    gross_annual_income: float
    down_payment: float
    conservative_max_price: float
    moderate_max_price: float
    stretch_max_price: float
    calendar_year: int | None = None

    @property
    def spread(self) -> float:
        return self.stretch_max_price - self.conservative_max_price


def affordability_range_rows(
    rows: list[YearlyAffordabilityRow],
    *,
    base_year: int | None = None,
) -> list[AffordabilityRangeRow]:
    """Extract structured affordable-range rows from yearly band projections."""
    range_rows: list[AffordabilityRangeRow] = []
    for row in rows:
        low, high = affordability_price_range(row)
        by_label = {band.label: band for band in row.bands}
        range_rows.append(
            AffordabilityRangeRow(
                year=row.year,
                gross_annual_income=row.gross_annual_income,
                down_payment=row.down_payment,
                conservative_max_price=low,
                moderate_max_price=by_label["moderate"].max_home_price,
                stretch_max_price=high,
                calendar_year=base_year + row.year if base_year is not None else None,
            )
        )
    return range_rows


def _format_range_delta(amount: float) -> str:
    sign = "+" if amount >= 0 else "-"
    return f"{sign}${abs(amount):,.0f}"


def affordability_range_summary(
    rows: list[YearlyAffordabilityRow],
    *,
    base_year: int | None = None,
) -> str | None:
    """One-line summary of affordable-range growth from the first to last projection year."""
    range_rows = affordability_range_rows(rows, base_year=base_year)
    if len(range_rows) < 2:
        return None

    first, last = range_rows[0], range_rows[-1]
    if base_year is not None:
        start_label = str(first.calendar_year)
        end_label = str(last.calendar_year)
    else:
        start_label = str(first.year)
        end_label = str(last.year)

    cons_delta = last.conservative_max_price - first.conservative_max_price
    stretch_delta = last.stretch_max_price - first.stretch_max_price
    spread_delta = last.spread - first.spread
    return (
        f"Range growth ({start_label} → {end_label}): "
        f"conservative {_format_range_delta(cons_delta)}, "
        f"stretch {_format_range_delta(stretch_delta)}, "
        f"spread {_format_range_delta(spread_delta)}"
    )


def format_affordability_range_report(
    rows: list[YearlyAffordabilityRow],
    *,
    base_year: int | None = None,
) -> str:
    """Render a year-by-year affordable price range (conservative through stretch)."""
    range_rows = affordability_range_rows(rows, base_year=base_year)
    year_label = "Calendar" if base_year is not None else "Year"
    lines = [
        f"{year_label:>8}  {'Income $':>12}  {'Down $':>12}  "
        f"{'Affordable range $':>28}  {'Spread $':>12}"
    ]
    for range_row in range_rows:
        year_display = (
            range_row.calendar_year if range_row.calendar_year is not None else range_row.year
        )
        lines.append(
            f"{year_display:8d}  ${range_row.gross_annual_income:>10,.0f}  "
            f"${range_row.down_payment:>10,.0f}  "
            f"${range_row.conservative_max_price:>12,.0f} – "
            f"${range_row.stretch_max_price:,.0f}  "
            f"${range_row.spread:>10,.0f}"
        )
    body = "\n".join(lines)
    summary = affordability_range_summary(rows, base_year=base_year)
    if summary is not None:
        return f"{body}\n\n{summary}"
    return body


def format_affordability_range_report_json(
    rows: list[YearlyAffordabilityRow],
    *,
    base_year: int | None = None,
) -> str:
    """Serialize the affordable range report as JSON for scripting."""
    payload = []
    for range_row in affordability_range_rows(rows, base_year=base_year):
        entry = {
            "year": range_row.year,
            "gross_annual_income": range_row.gross_annual_income,
            "down_payment": range_row.down_payment,
            "conservative_max_price": range_row.conservative_max_price,
            "moderate_max_price": range_row.moderate_max_price,
            "stretch_max_price": range_row.stretch_max_price,
            "spread": range_row.spread,
        }
        if range_row.calendar_year is not None:
            entry["calendar_year"] = range_row.calendar_year
        payload.append(entry)
    return json.dumps(payload, indent=2)


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
                dti_passes=check.passes_front_end and check.passes_back_end,
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
