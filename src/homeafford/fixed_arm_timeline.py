"""Year-by-year fixed vs ARM mortgage payment timeline analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass

from homeafford.mortgage import format_arm_label
from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    FixedArmScenarioResult,
    analyze_fixed_arm_scenario,
)


@dataclass(frozen=True)
class FixedArmYearlyRow:
    """One loan year in a fixed vs ARM cost timeline."""

    year: int
    fixed_monthly_payment: float
    arm_monthly_payment: float
    fixed_annual_cost: float
    arm_annual_cost: float
    fixed_cumulative_cost: float
    arm_cumulative_cost: float
    cumulative_arm_savings: float
    arm_phase: str
    arm_still_leads: bool


@dataclass(frozen=True)
class FixedArmTimelineResult:
    """Year-by-year fixed vs ARM payment and cumulative cost comparison."""

    inputs: FixedArmScenarioInputs
    scenario: FixedArmScenarioResult
    yearly_rows: tuple[FixedArmYearlyRow, ...]
    adjustment_year: int
    break_even_year: int | None
    years_arm_leads: int
    peak_arm_savings_year: int | None
    peak_arm_savings_amount: float


def build_fixed_arm_timeline(
    inputs: FixedArmScenarioInputs,
) -> FixedArmTimelineResult:
    """Build a year-by-year timeline comparing fixed and hybrid ARM payments.

    Each row tracks monthly payments, annual P&I spend, cumulative totals, and
    whether the ARM still leads on cumulative cost. The adjustment year marks the
    first year where the post-adjustment ARM payment applies.
    """
    if inputs.principal <= 0:
        raise ValueError("principal must be positive")
    if inputs.term_years <= 0:
        raise ValueError("term_years must be positive")
    if inputs.intro_years <= 0:
        raise ValueError("intro_years must be positive")
    if inputs.intro_years >= inputs.term_years:
        raise ValueError("intro_years must be less than term_years")

    scenario = analyze_fixed_arm_scenario(inputs)
    comparison = scenario.comparison
    adjustment_year = inputs.intro_years + 1

    rows: list[FixedArmYearlyRow] = []
    fixed_cumulative = 0.0
    arm_cumulative = 0.0
    years_arm_leads = 0
    peak_arm_savings_amount = 0.0
    peak_arm_savings_year: int | None = None

    for year in range(1, inputs.term_years + 1):
        arm_payment = (
            comparison.arm_intro_payment
            if year <= inputs.intro_years
            else comparison.arm_post_adjustment_payment
        )
        arm_phase = "intro" if year <= inputs.intro_years else "post_adjustment"
        fixed_annual = comparison.fixed_payment * 12
        arm_annual = arm_payment * 12
        fixed_cumulative += fixed_annual
        arm_cumulative += arm_annual
        cumulative_arm_savings = fixed_cumulative - arm_cumulative
        arm_still_leads = arm_cumulative < fixed_cumulative

        if arm_still_leads:
            years_arm_leads += 1
        if cumulative_arm_savings > peak_arm_savings_amount:
            peak_arm_savings_amount = cumulative_arm_savings
            peak_arm_savings_year = year

        rows.append(
            FixedArmYearlyRow(
                year=year,
                fixed_monthly_payment=comparison.fixed_payment,
                arm_monthly_payment=arm_payment,
                fixed_annual_cost=fixed_annual,
                arm_annual_cost=arm_annual,
                fixed_cumulative_cost=fixed_cumulative,
                arm_cumulative_cost=arm_cumulative,
                cumulative_arm_savings=cumulative_arm_savings,
                arm_phase=arm_phase,
                arm_still_leads=arm_still_leads,
            )
        )

    break_even_year = _break_even_year(rows, scenario.break_even_month)
    return FixedArmTimelineResult(
        inputs=inputs,
        scenario=scenario,
        yearly_rows=tuple(rows),
        adjustment_year=adjustment_year,
        break_even_year=break_even_year,
        years_arm_leads=years_arm_leads,
        peak_arm_savings_year=peak_arm_savings_year,
        peak_arm_savings_amount=peak_arm_savings_amount,
    )


def format_fixed_arm_timeline(result: FixedArmTimelineResult) -> str:
    """Render a human-readable year-by-year fixed vs ARM timeline."""
    inputs = result.inputs
    lines = [
        (
            f"Fixed vs ARM timeline: ${inputs.principal:,.0f} over "
            f"{inputs.term_years} years ({format_arm_label(inputs.intro_years)})"
        ),
        (
            f"Adjustment year: {result.adjustment_year}  |  "
            f"Years ARM leads: {result.years_arm_leads}  |  "
            f"Full-term winner: {result.scenario.cheaper_over_full_term.upper()}"
        ),
    ]
    if result.peak_arm_savings_year is not None:
        lines.append(
            f"Peak ARM savings: ${result.peak_arm_savings_amount:,.0f} "
            f"at year {result.peak_arm_savings_year}"
        )
    if result.break_even_year is not None:
        lines.append(f"Break-even year: {result.break_even_year}")
    else:
        lines.append("Break-even year: ARM never exceeds fixed cumulative cost")

    lines.extend(
        [
            "",
            f"{'Year':>4}  {'Phase':>16}  {'Fixed P&I':>10}  {'ARM P&I':>10}  "
            f"{'ARM save YTD':>12}  {'Cum save':>10}  Lead",
        ]
    )
    for row in result.yearly_rows:
        year_save = row.fixed_annual_cost - row.arm_annual_cost
        lead = "ARM" if row.arm_still_leads else "fixed"
        marker = ""
        if row.year == result.adjustment_year:
            marker = " *"
        elif row.year == result.break_even_year:
            marker = " †"
        lines.append(
            f"{row.year:>4}  "
            f"{row.arm_phase:>16}  "
            f"${row.fixed_monthly_payment:>9,.0f}  "
            f"${row.arm_monthly_payment:>9,.0f}  "
            f"${year_save:>11,.0f}  "
            f"${row.cumulative_arm_savings:>9,.0f}  "
            f"{lead}{marker}"
        )

    lines.extend(
        [
            "",
            "* adjustment year  † break-even year (ARM cumulative cost exceeds fixed)",
        ]
    )
    return "\n".join(lines)


def format_fixed_arm_timeline_json(result: FixedArmTimelineResult) -> str:
    """Serialize a fixed vs ARM timeline as JSON for scripting."""
    inputs = result.inputs
    scenario = result.scenario
    comp = scenario.comparison
    payload: dict[str, object] = {
        "inputs": {
            "principal": inputs.principal,
            "term_years": inputs.term_years,
            "intro_years": inputs.intro_years,
            "fixed_rate": inputs.fixed_rate,
            "arm_intro_rate": inputs.arm_intro_rate,
            "arm_adjusted_rate": inputs.arm_adjusted_rate,
        },
        "summary": {
            "adjustment_year": result.adjustment_year,
            "break_even_year": result.break_even_year,
            "break_even_month": scenario.break_even_month,
            "years_arm_leads": result.years_arm_leads,
            "peak_arm_savings_year": result.peak_arm_savings_year,
            "peak_arm_savings_amount": result.peak_arm_savings_amount,
            "cheaper_over_full_term": scenario.cheaper_over_full_term,
            "fixed_total_cost": scenario.fixed_total_cost,
            "arm_total_cost": scenario.arm_total_cost,
            "arm_payment_shock_dollars": scenario.arm_payment_shock_dollars,
            "fixed_payment": comp.fixed_payment,
            "arm_intro_payment": comp.arm_intro_payment,
            "arm_post_adjustment_payment": comp.arm_post_adjustment_payment,
        },
        "yearly_rows": [
            {
                "year": row.year,
                "arm_phase": row.arm_phase,
                "fixed_monthly_payment": row.fixed_monthly_payment,
                "arm_monthly_payment": row.arm_monthly_payment,
                "fixed_annual_cost": row.fixed_annual_cost,
                "arm_annual_cost": row.arm_annual_cost,
                "fixed_cumulative_cost": row.fixed_cumulative_cost,
                "arm_cumulative_cost": row.arm_cumulative_cost,
                "cumulative_arm_savings": row.cumulative_arm_savings,
                "arm_still_leads": row.arm_still_leads,
            }
            for row in result.yearly_rows
        ],
    }
    return json.dumps(payload, indent=2)


def _break_even_year(
    rows: list[FixedArmYearlyRow],
    break_even_month: int | None,
) -> int | None:
    if break_even_month is None:
        return None
    for row in rows:
        year_start_month = (row.year - 1) * 12 + 1
        year_end_month = row.year * 12
        if year_start_month <= break_even_month <= year_end_month:
            return row.year
    return None
