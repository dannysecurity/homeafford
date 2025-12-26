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
from homeafford.mortgage import (
    FixedVsArmComparison,
    compare_fixed_vs_arm,
    mortgage_payment,
    remaining_balance,
    total_interest,
)
from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    FixedArmScenarioResult,
    analyze_fixed_arm_scenario,
    format_fixed_arm_scenario,
)
from homeafford.piti import PitiBreakdown, compute_piti
from homeafford.report import (
    YearlyAffordabilityRow,
    affordability_report_by_year,
    format_affordability_report,
)
from homeafford.savings import SavingsSnapshot, savings_trajectory

__all__ = [
    "AffordabilityBand",
    "AffordabilityCheckResult",
    "AffordabilityInputs",
    "FixedArmScenarioInputs",
    "FixedArmScenarioResult",
    "FixedVsArmComparison",
    "PitiBreakdown",
    "PurchaseReadinessResult",
    "PurchaseScenario",
    "SavingsSnapshot",
    "YearlyAffordabilityRow",
    "affordability_bands",
    "affordability_report_by_year",
    "format_affordability_report",
    "analyze_fixed_arm_scenario",
    "compare_fixed_vs_arm",
    "format_fixed_arm_scenario",
    "check_affordability",
    "check_against_band",
    "check_purchase_readiness",
    "compute_piti",
    "mortgage_payment",
    "remaining_balance",
    "savings_trajectory",
    "total_interest",
]
