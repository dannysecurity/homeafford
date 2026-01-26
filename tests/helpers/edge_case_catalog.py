"""Reusable edge-case scenario builders for calculator pytest suites.

Centralizes boundary inputs so mortgage, affordability, PITI, savings, and
purchase-check tests share consistent fixtures instead of duplicating magic
numbers across files.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from homeafford.affordability import AffordabilityInputs
from homeafford.check import PurchaseScenario
from homeafford.mortgage_scenario import FixedArmScenarioInputs


def affordability_inputs(**overrides: Any) -> AffordabilityInputs:
    """Return ``AffordabilityInputs`` with sensible defaults and optional overrides."""
    defaults: dict[str, Any] = dict(
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        down_payment=60_000,
    )
    defaults.update(overrides)
    return AffordabilityInputs(**defaults)


def purchase_scenario(**overrides: Any) -> PurchaseScenario:
    """Return ``PurchaseScenario`` with sensible defaults and optional overrides."""
    defaults: dict[str, Any] = dict(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def fixed_arm_inputs(**overrides: Any) -> FixedArmScenarioInputs:
    """Return ``FixedArmScenarioInputs`` with sensible defaults and optional overrides."""
    defaults: dict[str, Any] = dict(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        intro_years=5,
    )
    defaults.update(overrides)
    return FixedArmScenarioInputs(**defaults)


@dataclass(frozen=True)
class EdgeCaseCatalog:
    """Named boundary scenarios grouped by calculator domain."""

    # Affordability — debt consumes the entire back-end housing allowance.
    debt_overwhelms_budget: AffordabilityInputs = affordability_inputs(
        gross_annual_income=120_000,
        monthly_debt_payments=5_000,
    )

    # Affordability — HOA reduces the loan ceiling without changing income caps.
    high_hoa: AffordabilityInputs = affordability_inputs(hoa_monthly=350)

    no_hoa: AffordabilityInputs = affordability_inputs(hoa_monthly=0)

    # Purchase check — front-end DTI fails while back-end still passes.
    front_end_failure: PurchaseScenario = purchase_scenario(
        home_price=650_000,
        down_payment=130_000,
        gross_annual_income=120_000,
        monthly_debt_payments=0,
    )

    # Purchase check — 100% down, zero loan balance.
    all_cash_purchase: PurchaseScenario = purchase_scenario(
        home_price=400_000,
        down_payment=400_000,
        gross_annual_income=200_000,
    )

    # Purchase check — LTV exactly at the conventional PMI threshold.
    pmi_threshold_ltv: PurchaseScenario = purchase_scenario(
        home_price=500_000,
        down_payment=100_000,
    )

    # ARM scenario — intro and fixed rates equal (no intro savings).
    flat_arm_rates: FixedArmScenarioInputs = fixed_arm_inputs(
        fixed_rate=0.06,
        arm_intro_rate=0.06,
        arm_adjusted_rate=0.06,
    )

    # ARM scenario — adjusted rate stays low; ARM never exceeds fixed cumulatively.
    arm_always_cheaper: FixedArmScenarioInputs = fixed_arm_inputs(
        fixed_rate=0.07,
        arm_intro_rate=0.05,
        arm_adjusted_rate=0.055,
    )

    # ARM scenario — typical 7/1 hybrid with a longer intro window before adjustment.
    arm_seven_one: FixedArmScenarioInputs = fixed_arm_inputs(
        intro_years=7,
        fixed_rate=0.0625,
        arm_intro_rate=0.0525,
        arm_adjusted_rate=0.0725,
    )

    def with_affordability(self, scenario: AffordabilityInputs, **changes: Any) -> AffordabilityInputs:
        return replace(scenario, **changes)

    def with_purchase(self, scenario: PurchaseScenario, **changes: Any) -> PurchaseScenario:
        return replace(scenario, **changes)

    def with_fixed_arm(
        self, scenario: FixedArmScenarioInputs, **changes: Any
    ) -> FixedArmScenarioInputs:
        return replace(scenario, **changes)
