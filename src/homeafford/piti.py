"""Principal, interest, taxes, and insurance (PITI) helpers."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.mortgage import mortgage_payment
from homeafford.pmi import compute_pmi_monthly


@dataclass(frozen=True)
class PitiBreakdown:
    """Monthly housing cost components for a financed purchase."""

    loan_amount: float
    principal_and_interest: float
    tax_monthly: float
    insurance_monthly: float
    pmi_monthly: float
    hoa_monthly: float
    piti: float


def compute_piti(
    *,
    loan_amount: float,
    property_tax_rate: float,
    insurance_annual: float,
    hoa_monthly: float,
    mortgage_rate: float,
    loan_term_years: int,
    home_price: float | None = None,
    pmi_annual_rate: float = 0.0,
    pmi_ltv_threshold: float = 0.80,
) -> PitiBreakdown:
    """Return monthly P&I, tax, insurance, PMI, HOA, and total PITI for a loan."""
    if loan_amount < 0:
        raise ValueError("loan_amount must be non-negative")

    tax_monthly = loan_amount * property_tax_rate / 12
    insurance_monthly = insurance_annual / 12
    if loan_amount == 0:
        payment = 0.0
    else:
        payment = mortgage_payment(
            principal=loan_amount,
            annual_rate=mortgage_rate,
            term_years=loan_term_years,
        )
    pmi_monthly = 0.0
    if home_price is not None and pmi_annual_rate > 0:
        pmi_monthly = compute_pmi_monthly(
            loan_amount=loan_amount,
            home_price=home_price,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
    piti = payment + tax_monthly + insurance_monthly + pmi_monthly + hoa_monthly
    return PitiBreakdown(
        loan_amount=loan_amount,
        principal_and_interest=payment,
        tax_monthly=tax_monthly,
        insurance_monthly=insurance_monthly,
        pmi_monthly=pmi_monthly,
        hoa_monthly=hoa_monthly,
        piti=piti,
    )


def compute_dti_ratios(
    *,
    piti: float,
    gross_annual_income: float,
    monthly_debt_payments: float,
) -> tuple[float, float]:
    """Return front-end and back-end DTI ratios as fractions of gross income."""
    monthly_income = gross_annual_income / 12
    if monthly_income <= 0:
        return 0.0, 0.0
    front_end = piti / monthly_income
    back_end = (piti + monthly_debt_payments) / monthly_income
    return front_end, back_end
