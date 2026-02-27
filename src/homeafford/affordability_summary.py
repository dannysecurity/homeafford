"""Actionable purchase affordability summaries combining DTI and down payment checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseScenario,
    _validate_scenario,
    check_affordability,
)
from homeafford.dti_analysis import min_income_for_dti
from homeafford.dti_params import resolve_dti_params
from homeafford.dti_serialize import affordability_check_to_dict, dumps_dti_payload
from homeafford.model import min_down_payment_for_dti

BindingConstraint = Literal["front_end", "back_end", "down_payment", "pass"]


@dataclass(frozen=True)
class PurchaseAffordabilitySummary:
    """Forward affordability check enriched with remediation hints."""

    home_price: float
    check: AffordabilityCheckResult
    band_label: str | None
    front_end_cap: float
    back_end_cap: float
    min_down_payment_pct: float
    binding_constraint: BindingConstraint
    min_down_payment_for_dti: float | None
    min_down_payment_pct_for_dti: float | None
    down_payment_gap: float | None
    min_income_for_dti: float | None
    income_gap: float | None
    recommendations: tuple[str, ...]


def _binding_constraint(
    check: AffordabilityCheckResult,
    *,
    front_end_cap: float,
    back_end_cap: float,
    min_down_payment_pct: float,
) -> BindingConstraint:
    front_headroom = front_end_cap - check.front_end_dti
    back_headroom = back_end_cap - check.back_end_dti
    down_headroom = check.down_payment_pct - min_down_payment_pct

    if check.passes:
        return min(
            {
                "front_end": front_headroom,
                "back_end": back_headroom,
                "down_payment": down_headroom,
            },
            key=lambda key: {
                "front_end": front_headroom,
                "back_end": back_headroom,
                "down_payment": down_headroom,
            }[key],
        )

    failing: dict[str, float] = {}
    if not check.passes_front_end:
        failing["front_end"] = front_headroom
    if not check.passes_back_end:
        failing["back_end"] = back_headroom
    if not check.passes_down_payment:
        failing["down_payment"] = down_headroom
    return min(failing, key=failing.get)  # type: ignore[return-value]


def _build_recommendations(
    *,
    check: AffordabilityCheckResult,
    home_price: float,
    binding: BindingConstraint,
    min_down: float | None,
    min_down_pct: float | None,
    down_gap: float | None,
    min_income: float | None,
    income_gap: float | None,
    min_down_payment_pct: float,
) -> tuple[str, ...]:
    if check.passes:
        return (
            "Purchase passes front-end DTI, back-end DTI, and down payment rules.",
            f"Tightest constraint with headroom: {binding.replace('_', ' ')}.",
        )

    recs: list[str] = []
    passes_dti = check.passes_front_end and check.passes_back_end

    if not passes_dti:
        if min_down is None:
            recs.append(
                "Existing monthly debt exceeds the back-end DTI cap; "
                "no down payment level can fix affordability."
            )
        elif down_gap is not None and down_gap > 0:
            recs.append(
                f"Increase down payment by ${down_gap:,.0f} to ${min_down:,.0f} "
                f"({min_down_pct:.1%}) to meet DTI caps."
            )
        if min_income is not None and income_gap is not None and income_gap > 0:
            recs.append(
                f"Alternatively, raise gross annual income by ${income_gap:,.0f} "
                f"to ${min_income:,.0f} at the current down payment."
            )
        recs.append(f"Binding DTI constraint: {binding.replace('_', ' ')}.")

    if not check.passes_down_payment:
        min_floor_amount = home_price * min_down_payment_pct
        recs.append(
            f"Meet the {min_down_payment_pct:.1%} down payment floor "
            f"(${min_floor_amount:,.0f} on this home)."
        )

    if not recs:
        recs.append("Review DTI caps or purchase inputs; affordability check failed.")
    return tuple(recs)


def summarize_purchase_affordability(
    scenario: PurchaseScenario,
    *,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
    mortgage_insurance_always: bool = False,
    loan_program: str | None = None,
    band_label: str | None = None,
) -> PurchaseAffordabilitySummary:
    """Run a forward affordability check and attach down payment / income remediation hints."""
    _validate_scenario(scenario)
    (
        front_end_cap,
        back_end_cap,
        min_down_payment_pct,
        pmi_annual_rate,
        pmi_ltv_threshold,
        mortgage_insurance_always,
    ) = resolve_dti_params(
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        loan_program=loan_program,
        band_label=band_label,
        market=scenario.market,
    )

    check = check_affordability(
        scenario,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        band_label=band_label,
    )
    binding = _binding_constraint(
        check,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
    )

    min_down = min_down_payment_for_dti(
        scenario,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    )
    min_down_pct = min_down / scenario.home_price if min_down is not None else None
    passes_dti = check.passes_front_end and check.passes_back_end
    down_gap = (
        max(0.0, min_down - scenario.down_payment)
        if min_down is not None and not passes_dti
        else None
    )

    min_income: float | None = None
    income_gap: float | None = None
    if not passes_dti:
        min_income = min_income_for_dti(
            scenario,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
            mortgage_insurance_always=mortgage_insurance_always,
        )
        if min_income is not None:
            income_gap = max(0.0, min_income - scenario.gross_annual_income)

    recommendations = _build_recommendations(
        check=check,
        home_price=scenario.home_price,
        binding=binding,
        min_down=min_down,
        min_down_pct=min_down_pct,
        down_gap=down_gap,
        min_income=min_income,
        income_gap=income_gap,
        min_down_payment_pct=min_down_payment_pct,
    )

    return PurchaseAffordabilitySummary(
        home_price=scenario.home_price,
        check=check,
        band_label=band_label,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        binding_constraint=binding,
        min_down_payment_for_dti=min_down,
        min_down_payment_pct_for_dti=min_down_pct,
        down_payment_gap=down_gap,
        min_income_for_dti=min_income,
        income_gap=income_gap,
        recommendations=recommendations,
    )


def format_purchase_affordability_summary(summary: PurchaseAffordabilitySummary) -> str:
    """Render an actionable affordability summary for CLI or logging."""
    check = summary.check
    band = summary.band_label or "custom"
    lines = [
        f"Affordability summary (${summary.home_price:,.0f} home, {band} band)",
        f"Result: {'PASS' if check.passes else 'FAIL'}",
        f"  PITI: ${check.estimated_piti:,.0f}/mo  "
        f"Front: {check.front_end_dti:.1%}  Back: {check.back_end_dti:.1%}  "
        f"Down: {check.down_payment_pct:.1%}",
        f"  Binding constraint: {summary.binding_constraint.replace('_', ' ')}",
    ]
    if summary.min_down_payment_for_dti is not None:
        lines.append(
            f"  Min down for DTI: ${summary.min_down_payment_for_dti:,.0f} "
            f"({summary.min_down_payment_pct_for_dti:.1%})"
        )
    if summary.down_payment_gap is not None and summary.down_payment_gap > 0:
        lines.append(f"  Down payment gap: ${summary.down_payment_gap:,.0f}")
    if summary.min_income_for_dti is not None:
        lines.append(f"  Min income for DTI: ${summary.min_income_for_dti:,.0f}")
    if summary.income_gap is not None and summary.income_gap > 0:
        lines.append(f"  Income gap: ${summary.income_gap:,.0f}")
    lines.append("Recommendations:")
    for rec in summary.recommendations:
        lines.append(f"  - {rec}")
    for reason in check.reasons:
        if reason not in summary.recommendations:
            lines.append(f"  - {reason}")
    return "\n".join(lines)


def format_purchase_affordability_summary_json(summary: PurchaseAffordabilitySummary) -> str:
    """Serialize an affordability summary as JSON for scripting."""
    payload: dict[str, object] = {
        "home_price": summary.home_price,
        "band_label": summary.band_label,
        "front_end_cap": summary.front_end_cap,
        "back_end_cap": summary.back_end_cap,
        "min_down_payment_pct": summary.min_down_payment_pct,
        "binding_constraint": summary.binding_constraint,
        "min_down_payment_for_dti": summary.min_down_payment_for_dti,
        "min_down_payment_pct_for_dti": summary.min_down_payment_pct_for_dti,
        "down_payment_gap": summary.down_payment_gap,
        "min_income_for_dti": summary.min_income_for_dti,
        "income_gap": summary.income_gap,
        "recommendations": list(summary.recommendations),
        "check": affordability_check_to_dict(summary.check),
    }
    return dumps_dti_payload(payload)
