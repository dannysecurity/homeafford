"""Income-based home price targets using common DTI guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeafford.market.resolve import effective_market_fields, effective_pmi_fields
from homeafford.market.snapshot import DEFAULT_MARKET
from homeafford.mortgage import mortgage_payment
from homeafford.piti import compute_dti_ratios, compute_piti
from homeafford.pmi import compute_pmi_monthly

if TYPE_CHECKING:
    from homeafford.market.protocol import MarketDataProvider
    from homeafford.market.snapshot import MarketSnapshot


@dataclass(frozen=True)
class AffordabilityInputs:
    gross_annual_income: float
    monthly_debt_payments: float = 0.0
    down_payment: float = 0.0
    property_tax_rate: float = DEFAULT_MARKET.property_tax_rate
    insurance_annual: float = DEFAULT_MARKET.insurance_annual
    hoa_monthly: float = 0.0
    loan_term_years: int = 30
    mortgage_rate: float = DEFAULT_MARKET.mortgage_rate
    market: MarketSnapshot | None = None


@dataclass(frozen=True)
class AffordabilityBand:
    label: str
    max_home_price: float
    max_loan_amount: float
    estimated_piti: float
    front_end_dti: float
    back_end_dti: float


_BANDS: tuple[tuple[str, float, float], ...] = (
    ("conservative", 0.28, 0.36),
    ("moderate", 0.31, 0.43),
    ("stretch", 0.33, 0.45),
)


def affordability_bands(inputs: AffordabilityInputs) -> list[AffordabilityBand]:
    """Return price targets for standard front/back-end DTI bands."""
    if inputs.gross_annual_income <= 0:
        raise ValueError("gross_annual_income must be positive")

    mortgage_rate, property_tax_rate, insurance_annual = effective_market_fields(
        market=inputs.market,
        mortgage_rate=inputs.mortgage_rate,
        property_tax_rate=inputs.property_tax_rate,
        insurance_annual=inputs.insurance_annual,
    )
    pmi_annual_rate, pmi_ltv_threshold = effective_pmi_fields(market=inputs.market)

    monthly_income = inputs.gross_annual_income / 12
    results: list[AffordabilityBand] = []

    for label, front_cap, back_cap in _BANDS:
        max_housing = min(
            monthly_income * front_cap,
            monthly_income * back_cap - inputs.monthly_debt_payments,
        )
        max_housing = max(0.0, max_housing - inputs.hoa_monthly)

        fixed_costs = insurance_annual / 12
        max_loan = _max_loan_for_housing_budget(
            housing_budget=max_housing,
            property_tax_rate=property_tax_rate,
            insurance_monthly=fixed_costs,
            annual_rate=mortgage_rate,
            term_years=inputs.loan_term_years,
            down_payment=inputs.down_payment,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        max_price = max_loan + inputs.down_payment
        breakdown = compute_piti(
            loan_amount=max_loan,
            property_tax_rate=property_tax_rate,
            insurance_annual=insurance_annual,
            hoa_monthly=inputs.hoa_monthly,
            mortgage_rate=mortgage_rate,
            loan_term_years=inputs.loan_term_years,
            home_price=max_price,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        front_end, back_end = compute_dti_ratios(
            piti=breakdown.piti,
            gross_annual_income=inputs.gross_annual_income,
            monthly_debt_payments=inputs.monthly_debt_payments,
        )

        results.append(
            AffordabilityBand(
                label=label,
                max_home_price=max_price,
                max_loan_amount=max_loan,
                estimated_piti=breakdown.piti,
                front_end_dti=front_end,
                back_end_dti=back_end,
            )
        )

    return results


def affordability_bands_from_provider(
    inputs: AffordabilityInputs,
    provider: MarketDataProvider,
    *,
    overrides: dict[str, float | str] | None = None,
) -> list[AffordabilityBand]:
    """Resolve market assumptions from a provider, then compute affordability bands."""
    from homeafford.market.resolve import apply_market_to_affordability_inputs

    resolved = apply_market_to_affordability_inputs(
        inputs,
        provider,
        overrides=overrides,
    )
    return affordability_bands(resolved)


def _max_loan_for_housing_budget(
    *,
    housing_budget: float,
    property_tax_rate: float,
    insurance_monthly: float,
    annual_rate: float,
    term_years: int,
    down_payment: float = 0.0,
    pmi_annual_rate: float = 0.0,
    pmi_ltv_threshold: float = 0.80,
) -> float:
    """Binary search loan size whose PITI (including PMI) fits within housing_budget."""
    if housing_budget <= insurance_monthly:
        return 0.0

    low, high = 0.0, 5_000_000.0
    for _ in range(64):
        mid = (low + high) / 2
        tax_monthly = mid * property_tax_rate / 12
        payment = mortgage_payment(
            principal=mid, annual_rate=annual_rate, term_years=term_years
        )
        home_price = mid + down_payment
        pmi_monthly = compute_pmi_monthly(
            loan_amount=mid,
            home_price=home_price,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        piti = payment + tax_monthly + insurance_monthly + pmi_monthly
        if piti <= housing_budget:
            low = mid
        else:
            high = mid
    return low
