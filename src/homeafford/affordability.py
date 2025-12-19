"""Income-based home price targets using common DTI guardrails."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.mortgage import mortgage_payment


@dataclass(frozen=True)
class AffordabilityInputs:
    gross_annual_income: float
    monthly_debt_payments: float = 0.0
    down_payment: float = 0.0
    property_tax_rate: float = 0.012
    insurance_annual: float = 1_200.0
    hoa_monthly: float = 0.0
    loan_term_years: int = 30
    mortgage_rate: float = 0.065


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

    monthly_income = inputs.gross_annual_income / 12
    results: list[AffordabilityBand] = []

    for label, front_cap, back_cap in _BANDS:
        max_housing = min(
            monthly_income * front_cap,
            monthly_income * back_cap - inputs.monthly_debt_payments,
        )
        max_housing = max(0.0, max_housing - inputs.hoa_monthly)

        fixed_costs = inputs.insurance_annual / 12
        # Solve for max loan where P&I + tax + insurance + HOA fits budget.
        max_loan = _max_loan_for_housing_budget(
            housing_budget=max_housing,
            property_tax_rate=inputs.property_tax_rate,
            insurance_monthly=fixed_costs,
            annual_rate=inputs.mortgage_rate,
            term_years=inputs.loan_term_years,
        )
        max_price = max_loan + inputs.down_payment
        tax_monthly = max_loan * inputs.property_tax_rate / 12
        payment = mortgage_payment(
            principal=max_loan,
            annual_rate=inputs.mortgage_rate,
            term_years=inputs.loan_term_years,
        )
        piti = payment + tax_monthly + fixed_costs + inputs.hoa_monthly

        results.append(
            AffordabilityBand(
                label=label,
                max_home_price=max_price,
                max_loan_amount=max_loan,
                estimated_piti=piti,
                front_end_dti=(piti / monthly_income) if monthly_income else 0.0,
                back_end_dti=(
                    (piti + inputs.monthly_debt_payments) / monthly_income
                    if monthly_income
                    else 0.0
                ),
            )
        )

    return results


def _max_loan_for_housing_budget(
    *,
    housing_budget: float,
    property_tax_rate: float,
    insurance_monthly: float,
    annual_rate: float,
    term_years: int,
) -> float:
    """Binary search loan size whose PITI fits within housing_budget."""
    if housing_budget <= insurance_monthly:
        return 0.0

    low, high = 0.0, 5_000_000.0
    for _ in range(64):
        mid = (low + high) / 2
        tax_monthly = mid * property_tax_rate / 12
        payment = mortgage_payment(
            principal=mid, annual_rate=annual_rate, term_years=term_years
        )
        piti = payment + tax_monthly + insurance_monthly
        if piti <= housing_budget:
            low = mid
        else:
            high = mid
    return low
