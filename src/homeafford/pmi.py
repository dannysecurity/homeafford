"""Private mortgage insurance (PMI) estimates for high-LTV loans.

PMI is modeled as a simple annual rate applied to the outstanding loan balance
when loan-to-value exceeds a threshold (typically 80%). This module feeds PMI
dollars into PITI so down-payment and DTI affordability checks reflect the
true cost of low-down purchases.
"""

from __future__ import annotations


def compute_pmi_monthly(
    *,
    loan_amount: float,
    home_price: float,
    pmi_annual_rate: float,
    pmi_ltv_threshold: float = 0.80,
    always_apply: bool = False,
) -> float:
    """Return monthly PMI when LTV exceeds ``pmi_ltv_threshold``, else 0.

    PMI is computed as ``loan_amount * pmi_annual_rate / 12``. Returns 0 when
    the loan is fully paid off, the home price is non-positive, or LTV is at
    or below the threshold (no PMI required). When ``always_apply`` is True
    (e.g. FHA MIP), the rate applies whenever there is an outstanding loan.
    """
    if loan_amount <= 0 or home_price <= 0 or pmi_annual_rate <= 0:
        return 0.0
    if always_apply:
        return loan_amount * pmi_annual_rate / 12
    ltv = loan_amount / home_price
    if ltv <= pmi_ltv_threshold:
        return 0.0
    return loan_amount * pmi_annual_rate / 12


def pmi_required(
    *,
    loan_amount: float,
    home_price: float,
    pmi_ltv_threshold: float = 0.80,
) -> bool:
    """Return whether PMI applies at the given LTV."""
    if loan_amount <= 0 or home_price <= 0:
        return False
    return loan_amount / home_price > pmi_ltv_threshold
