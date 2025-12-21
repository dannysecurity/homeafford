"""homeafford — savings, mortgage, and affordability planning."""

from homeafford.affordability import AffordabilityBand, AffordabilityInputs, affordability_bands
from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseReadinessResult,
    PurchaseScenario,
    check_affordability,
    check_against_band,
    check_purchase_readiness,
)
from homeafford.mortgage import mortgage_payment, remaining_balance, total_interest
from homeafford.piti import PitiBreakdown, compute_piti
from homeafford.report import YearlyAffordabilityRow, affordability_report_by_year
from homeafford.savings import SavingsSnapshot, savings_trajectory

__all__ = [
    "AffordabilityBand",
    "AffordabilityCheckResult",
    "AffordabilityInputs",
    "PitiBreakdown",
    "PurchaseReadinessResult",
    "PurchaseScenario",
    "SavingsSnapshot",
    "YearlyAffordabilityRow",
    "affordability_bands",
    "affordability_report_by_year",
    "check_affordability",
    "check_against_band",
    "check_purchase_readiness",
    "compute_piti",
    "mortgage_payment",
    "remaining_balance",
    "savings_trajectory",
    "total_interest",
]
