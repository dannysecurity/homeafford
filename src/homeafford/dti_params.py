"""Shared DTI cap resolution and purchase-scenario helpers."""

from __future__ import annotations

from dataclasses import replace

from homeafford.check import PurchaseScenario, _band_caps


def scenario_at_down(scenario: PurchaseScenario, down_payment: float) -> PurchaseScenario:
    return replace(scenario, down_payment=down_payment)


def scenario_at_income(scenario: PurchaseScenario, gross_annual_income: float) -> PurchaseScenario:
    return replace(scenario, gross_annual_income=gross_annual_income)


def resolve_dti_params(
    *,
    front_end_cap: float,
    back_end_cap: float,
    min_down_payment_pct: float,
    pmi_annual_rate: float | None,
    pmi_ltv_threshold: float | None,
    mortgage_insurance_always: bool,
    loan_program: str | None,
    band_label: str | None,
    market,
) -> tuple[float, float, float, float | None, float | None, bool]:
    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    if loan_program is not None:
        from homeafford.loan_programs import resolve_program_dti_params

        program_params = resolve_program_dti_params(
            loan_program,
            market=market,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        min_down_payment_pct = program_params.min_down_payment_pct
        pmi_annual_rate = program_params.pmi_annual_rate
        pmi_ltv_threshold = program_params.pmi_ltv_threshold
        mortgage_insurance_always = program_params.mortgage_insurance_always

    return (
        front_end_cap,
        back_end_cap,
        min_down_payment_pct,
        pmi_annual_rate,
        pmi_ltv_threshold,
        mortgage_insurance_always,
    )
