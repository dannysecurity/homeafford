"""Forward affordability checks for a specific home purchase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeafford.affordability import _BANDS
from homeafford.market.resolve import effective_market_fields, effective_pmi_fields
from homeafford.market.snapshot import DEFAULT_MARKET
from homeafford.piti import compute_dti_ratios, compute_piti
from homeafford.pmi import pmi_required
from homeafford.savings import savings_trajectory

if TYPE_CHECKING:
    from homeafford.market.snapshot import MarketSnapshot


@dataclass(frozen=True)
class PurchaseScenario:
    """Inputs for evaluating one concrete purchase."""

    home_price: float
    down_payment: float
    gross_annual_income: float
    monthly_debt_payments: float = 0.0
    property_tax_rate: float = DEFAULT_MARKET.property_tax_rate
    insurance_annual: float = DEFAULT_MARKET.insurance_annual
    hoa_monthly: float = 0.0
    loan_term_years: int = 30
    mortgage_rate: float = DEFAULT_MARKET.mortgage_rate
    closing_costs: float = 0.0
    market: MarketSnapshot | None = None


@dataclass(frozen=True)
class AffordabilityCheckResult:
    """Pass/fail outcome for DTI and down-payment rules on a purchase."""

    passes: bool
    passes_front_end: bool
    passes_back_end: bool
    passes_down_payment: bool
    front_end_dti: float
    back_end_dti: float
    ltv: float
    down_payment_pct: float
    loan_amount: float
    estimated_piti: float
    estimated_pmi_monthly: float
    pmi_required: bool
    reasons: tuple[str, ...]
    band_label: str | None = None


@dataclass(frozen=True)
class PurchaseReadinessResult:
    """Whether savings and DTI both support buying by a target date."""

    passes: bool
    passes_dti: bool
    passes_savings: bool
    months_until_ready: int | None
    cash_required: float
    projected_balance: float | None
    affordability: AffordabilityCheckResult


def _validate_scenario(scenario: PurchaseScenario) -> None:
    if scenario.home_price <= 0:
        raise ValueError("home_price must be positive")
    if scenario.down_payment < 0:
        raise ValueError("down_payment must be non-negative")
    if scenario.down_payment > scenario.home_price:
        raise ValueError("down_payment cannot exceed home_price")
    if scenario.gross_annual_income <= 0:
        raise ValueError("gross_annual_income must be positive")
    if scenario.closing_costs < 0:
        raise ValueError("closing_costs must be non-negative")


def _band_caps(label: str) -> tuple[float, float]:
    for band_label, front_cap, back_cap in _BANDS:
        if band_label == label:
            return front_cap, back_cap
    valid = ", ".join(b[0] for b in _BANDS)
    raise ValueError(f"unknown band {label!r}; expected one of: {valid}")


def check_affordability(
    scenario: PurchaseScenario,
    *,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    pmi_ltv_threshold: float | None = None,
    pmi_annual_rate: float | None = None,
    mortgage_insurance_always: bool = False,
    loan_program: str | None = None,
    band_label: str | None = None,
) -> AffordabilityCheckResult:
    """Evaluate whether a purchase fits front/back DTI and down-payment rules."""
    _validate_scenario(scenario)

    if loan_program is not None:
        from homeafford.loan_programs import resolve_program_dti_params

        program_params = resolve_program_dti_params(
            loan_program,
            market=scenario.market,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        min_down_payment_pct = program_params.min_down_payment_pct
        pmi_annual_rate = program_params.pmi_annual_rate
        pmi_ltv_threshold = program_params.pmi_ltv_threshold
        mortgage_insurance_always = program_params.mortgage_insurance_always

    mortgage_rate, property_tax_rate, insurance_annual = effective_market_fields(
        market=scenario.market,
        mortgage_rate=scenario.mortgage_rate,
        property_tax_rate=scenario.property_tax_rate,
        insurance_annual=scenario.insurance_annual,
    )
    resolved_pmi_rate, resolved_pmi_threshold = effective_pmi_fields(
        market=scenario.market,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
    )

    loan_amount = scenario.home_price - scenario.down_payment
    breakdown = compute_piti(
        loan_amount=loan_amount,
        property_tax_rate=property_tax_rate,
        insurance_annual=insurance_annual,
        hoa_monthly=scenario.hoa_monthly,
        mortgage_rate=mortgage_rate,
        loan_term_years=scenario.loan_term_years,
        home_price=scenario.home_price,
        pmi_annual_rate=resolved_pmi_rate,
        pmi_ltv_threshold=resolved_pmi_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    )
    front_end, back_end = compute_dti_ratios(
        piti=breakdown.piti,
        gross_annual_income=scenario.gross_annual_income,
        monthly_debt_payments=scenario.monthly_debt_payments,
    )

    down_pct = scenario.down_payment / scenario.home_price
    ltv = loan_amount / scenario.home_price if scenario.home_price else 0.0

    passes_front = front_end <= front_end_cap
    passes_back = back_end <= back_end_cap
    passes_down = down_pct >= min_down_payment_pct
    needs_pmi = pmi_required(
        loan_amount=loan_amount,
        home_price=scenario.home_price,
        pmi_ltv_threshold=resolved_pmi_threshold,
    )

    reasons: list[str] = []
    if not passes_front:
        reasons.append(
            f"front-end DTI {front_end:.1%} exceeds cap {front_end_cap:.1%}"
        )
    if not passes_back:
        reasons.append(
            f"back-end DTI {back_end:.1%} exceeds cap {back_end_cap:.1%}"
        )
    if not passes_down:
        reasons.append(
            f"down payment {down_pct:.1%} below minimum {min_down_payment_pct:.1%}"
        )

    return AffordabilityCheckResult(
        passes=passes_front and passes_back and passes_down,
        passes_front_end=passes_front,
        passes_back_end=passes_back,
        passes_down_payment=passes_down,
        front_end_dti=front_end,
        back_end_dti=back_end,
        ltv=ltv,
        down_payment_pct=down_pct,
        loan_amount=loan_amount,
        estimated_piti=breakdown.piti,
        estimated_pmi_monthly=breakdown.pmi_monthly,
        pmi_required=needs_pmi,
        reasons=tuple(reasons),
        band_label=band_label,
    )


def check_against_band(
    scenario: PurchaseScenario,
    band_label: str = "conservative",
) -> AffordabilityCheckResult:
    """Run ``check_affordability`` using a preset band's DTI caps."""
    front_cap, back_cap = _band_caps(band_label)
    return check_affordability(
        scenario,
        front_end_cap=front_cap,
        back_end_cap=back_cap,
        band_label=band_label,
    )


def check_purchase_readiness(
    scenario: PurchaseScenario,
    *,
    starting_balance: float,
    monthly_contribution: float,
    annual_return: float = 0.04,
    target_months: int | None = None,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    loan_program: str | None = None,
    band_label: str | None = None,
) -> PurchaseReadinessResult:
    """Combine DTI checks with a savings projection for down payment + closing."""
    _validate_scenario(scenario)
    if starting_balance < 0 or monthly_contribution < 0:
        raise ValueError("starting_balance and monthly_contribution must be non-negative")
    if target_months is not None and target_months < 0:
        raise ValueError("target_months must be non-negative")

    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    affordability = check_affordability(
        scenario,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        loan_program=loan_program,
        band_label=band_label,
    )
    cash_required = scenario.down_payment + scenario.closing_costs

    if target_months is not None:
        snaps = savings_trajectory(
            starting_balance=starting_balance,
            monthly_contribution=monthly_contribution,
            annual_return=annual_return,
            months=target_months,
        )
        projected = snaps[-1].balance if snaps else starting_balance
        passes_savings = projected >= cash_required
        months_until = None
    else:
        projected = None
        passes_savings = starting_balance >= cash_required
        months_until = None
        if not passes_savings:
            months_until = _months_until_balance(
                cash_required=cash_required,
                starting_balance=starting_balance,
                monthly_contribution=monthly_contribution,
                annual_return=annual_return,
            )

    return PurchaseReadinessResult(
        passes=affordability.passes and passes_savings,
        passes_dti=affordability.passes,
        passes_savings=passes_savings,
        months_until_ready=months_until,
        cash_required=cash_required,
        projected_balance=projected,
        affordability=affordability,
    )


def _months_until_balance(
    *,
    cash_required: float,
    starting_balance: float,
    monthly_contribution: float,
    annual_return: float,
    max_months: int = 600,
) -> int | None:
    """Return months until savings reach ``cash_required``, or None if not within max."""
    if starting_balance >= cash_required:
        return 0
    snaps = savings_trajectory(
        starting_balance=starting_balance,
        monthly_contribution=monthly_contribution,
        annual_return=annual_return,
        months=max_months,
    )
    for snap in snaps:
        if snap.balance >= cash_required:
            return snap.month
    return None
