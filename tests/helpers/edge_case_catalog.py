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

    # Purchase check — elevated non-housing debt fails back-end while PITI stays modest.
    back_end_failure: PurchaseScenario = purchase_scenario(
        home_price=400_000,
        down_payment=80_000,
        gross_annual_income=120_000,
        monthly_debt_payments=2_800,
    )

    # Purchase check — exactly at the conventional 3% minimum down payment.
    minimum_down_payment: PurchaseScenario = purchase_scenario(
        home_price=500_000,
        down_payment=15_000,
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

    # ARM scenario — post-adjustment rate spike yields break-even and fixed wins long term.
    arm_rate_spike: FixedArmScenarioInputs = fixed_arm_inputs(
        fixed_rate=0.065,
        arm_intro_rate=0.05,
        arm_adjusted_rate=0.10,
    )

    # Savings — reachable down-payment goal with modest contributions and zero return.
    savings_reachable: PurchaseScenario = purchase_scenario(
        home_price=350_000,
        down_payment=35_000,
        closing_costs=8_000,
    )

    # Purchase check — LTV barely above the conventional PMI threshold (80.01%).
    borderline_pmi_ltv: PurchaseScenario = purchase_scenario(
        home_price=500_000,
        down_payment=99_950,
    )

    # Purchase check — high HOA pushes PITI without changing loan principal.
    high_hoa_purchase: PurchaseScenario = purchase_scenario(
        home_price=450_000,
        down_payment=90_000,
        hoa_monthly=450,
    )

    # Purchase check — stretched budget where post-adjustment ARM payment fails DTI.
    arm_post_dti_failure: PurchaseScenario = purchase_scenario(
        home_price=400_000,
        down_payment=80_000,
        gross_annual_income=120_000,
        monthly_debt_payments=350,
    )

    # Purchase check — front-end DTI lands exactly on the conservative cap.
    exact_front_end_cap: PurchaseScenario = purchase_scenario(
        home_price=380_000,
        down_payment=76_000,
        gross_annual_income=110_000,
        monthly_debt_payments=0,
    )

    # Purchase check — FHA minimum 3.5% down with lifetime MIP.
    fha_low_down: PurchaseScenario = purchase_scenario(
        home_price=400_000,
        down_payment=14_000,
        gross_annual_income=120_000,
    )

    # Purchase check — VA zero-down conventional-style LTV at 100%.
    va_zero_down: PurchaseScenario = purchase_scenario(
        home_price=450_000,
        down_payment=0,
        gross_annual_income=130_000,
    )

    # Purchase check — elevated mortgage rate inflates PITI on the same loan size.
    high_rate_purchase: PurchaseScenario = purchase_scenario(
        home_price=520_000,
        down_payment=104_000,
        gross_annual_income=160_000,
        mortgage_rate=0.085,
    )

    # Purchase check — 15-year term raises monthly payment on the same principal.
    short_term_loan: PurchaseScenario = purchase_scenario(
        home_price=420_000,
        down_payment=84_000,
        gross_annual_income=140_000,
        loan_term_years=15,
    )

    # Purchase check — ARM rate spike scenario for decision-report JSON coverage.
    arm_rate_spike_purchase: PurchaseScenario = purchase_scenario(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
        mortgage_rate=0.065,
    )

    def with_affordability(self, scenario: AffordabilityInputs, **changes: Any) -> AffordabilityInputs:
        return replace(scenario, **changes)

    def with_purchase(self, scenario: PurchaseScenario, **changes: Any) -> PurchaseScenario:
        return replace(scenario, **changes)

    def with_fixed_arm(
        self, scenario: FixedArmScenarioInputs, **changes: Any
    ) -> FixedArmScenarioInputs:
        return replace(scenario, **changes)
