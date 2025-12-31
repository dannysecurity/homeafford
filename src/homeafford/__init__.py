"""homeafford — savings, mortgage, and affordability planning."""

from homeafford.affordability import (
    AffordabilityBand,
    AffordabilityInputs,
    affordability_bands,
    affordability_bands_from_provider,
)
from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseReadinessResult,
    PurchaseScenario,
    check_affordability,
    check_against_band,
    check_purchase_readiness,
)
from homeafford.model import (
    DownPaymentDtiModelResult,
    DownPaymentScenarioRow,
    PurchaseAffordabilityPlan,
    format_down_payment_dti_model,
    format_purchase_affordability_plan,
    min_down_payment_for_dti,
    model_down_payment_dti,
    plan_purchase_affordability,
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
    fixed_arm_inputs_from_purchase,
    format_fixed_arm_scenario,
)
from homeafford.piti import PitiBreakdown, compute_piti
from homeafford.pmi import compute_pmi_monthly, pmi_required
from homeafford.report import (
    TargetHomeYearlyRow,
    YearlyAffordabilityRow,
    affordability_report_by_year,
    format_affordability_report,
    format_target_home_report,
    target_home_report_by_year,
)
from homeafford.market import (
    DEFAULT_MARKET,
    MarketDataProvider,
    MarketSnapshot,
    StaticMarketProvider,
    get_provider,
)

from homeafford.savings import SavingsSnapshot, savings_trajectory

__all__ = [
    "AffordabilityBand",
    "AffordabilityCheckResult",
    "AffordabilityInputs",
    "DEFAULT_MARKET",
    "FixedArmScenarioInputs",
    "FixedArmScenarioResult",
    "FixedVsArmComparison",
    "MarketDataProvider",
    "MarketSnapshot",
    "PitiBreakdown",
    "PurchaseAffordabilityPlan",
    "PurchaseReadinessResult",
    "PurchaseScenario",
    "SavingsSnapshot",
    "StaticMarketProvider",
    "TargetHomeYearlyRow",
    "YearlyAffordabilityRow",
    "affordability_bands",
    "affordability_bands_from_provider",
    "affordability_report_by_year",
    "compute_pmi_monthly",
    "format_affordability_report",
    "format_down_payment_dti_model",
    "format_purchase_affordability_plan",
    "format_target_home_report",
    "target_home_report_by_year",
    "analyze_fixed_arm_scenario",
    "compare_fixed_vs_arm",
    "fixed_arm_inputs_from_purchase",
    "format_fixed_arm_scenario",
    "check_affordability",
    "check_against_band",
    "check_purchase_readiness",
    "compute_piti",
    "DownPaymentDtiModelResult",
    "DownPaymentScenarioRow",
    "min_down_payment_for_dti",
    "model_down_payment_dti",
    "plan_purchase_affordability",
    "pmi_required",
    "get_provider",
    "mortgage_payment",
    "remaining_balance",
    "savings_trajectory",
    "total_interest",
]
