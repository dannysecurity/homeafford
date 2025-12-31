"""Fixed-rate vs ARM mortgage scenario analysis."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.mortgage import FixedVsArmComparison, compare_fixed_vs_arm


@dataclass(frozen=True)
class FixedArmScenarioInputs:
    """Inputs for comparing a fixed-rate loan with a hybrid ARM."""

    principal: float
    term_years: int
    fixed_rate: float
    arm_intro_rate: float
    arm_adjusted_rate: float
    intro_years: int = 5


@dataclass(frozen=True)
class FixedArmScenarioResult:
    """Outcome of a fixed vs ARM side-by-side scenario."""

    inputs: FixedArmScenarioInputs
    comparison: FixedVsArmComparison
    arm_payment_shock_dollars: float
    arm_payment_shock_pct: float
    fixed_total_cost: float
    arm_total_cost: float
    fixed_cost_during_intro: float
    arm_cost_during_intro: float
    arm_savings_during_intro: float
    break_even_month: int | None
    cheaper_over_full_term: str


def analyze_fixed_arm_scenario(inputs: FixedArmScenarioInputs) -> FixedArmScenarioResult:
    """Compare cumulative cost and payment shock for fixed vs hybrid ARM loans."""
    if inputs.principal <= 0:
        raise ValueError("principal must be positive")
    if inputs.term_years <= 0:
        raise ValueError("term_years must be positive")

    comparison = compare_fixed_vs_arm(
        principal=inputs.principal,
        term_years=inputs.term_years,
        fixed_rate=inputs.fixed_rate,
        arm_intro_rate=inputs.arm_intro_rate,
        arm_adjusted_rate=inputs.arm_adjusted_rate,
        intro_years=inputs.intro_years,
    )

    intro_months = inputs.intro_years * 12
    total_months = inputs.term_years * 12
    remaining_months = total_months - intro_months

    fixed_cost_during_intro = comparison.fixed_payment * intro_months
    arm_cost_during_intro = comparison.arm_intro_payment * intro_months
    arm_savings_during_intro = fixed_cost_during_intro - arm_cost_during_intro

    fixed_total_cost = comparison.fixed_payment * total_months
    arm_total_cost = (
        comparison.arm_intro_payment * intro_months
        + comparison.arm_post_adjustment_payment * remaining_months
    )

    shock_dollars = comparison.arm_post_adjustment_payment - comparison.arm_intro_payment
    shock_pct = (
        shock_dollars / comparison.arm_intro_payment
        if comparison.arm_intro_payment
        else 0.0
    )

    break_even_month = _break_even_month(
        fixed_payment=comparison.fixed_payment,
        arm_intro_payment=comparison.arm_intro_payment,
        arm_post_payment=comparison.arm_post_adjustment_payment,
        intro_months=intro_months,
        total_months=total_months,
    )

    if arm_total_cost < fixed_total_cost:
        cheaper = "arm"
    elif arm_total_cost > fixed_total_cost:
        cheaper = "fixed"
    else:
        cheaper = "tie"

    return FixedArmScenarioResult(
        inputs=inputs,
        comparison=comparison,
        arm_payment_shock_dollars=shock_dollars,
        arm_payment_shock_pct=shock_pct,
        fixed_total_cost=fixed_total_cost,
        arm_total_cost=arm_total_cost,
        fixed_cost_during_intro=fixed_cost_during_intro,
        arm_cost_during_intro=arm_cost_during_intro,
        arm_savings_during_intro=arm_savings_during_intro,
        break_even_month=break_even_month,
        cheaper_over_full_term=cheaper,
    )


def format_fixed_arm_scenario(result: FixedArmScenarioResult) -> str:
    """Render a human-readable summary for CLI or logging."""
    inputs = result.inputs
    comp = result.comparison
    lines = [
        f"Loan: ${inputs.principal:,.0f} over {inputs.term_years} years "
        f"({inputs.intro_years}/{inputs.term_years - inputs.intro_years} ARM)",
        "",
        "Monthly P&I",
        f"  Fixed ({inputs.fixed_rate:.2%}):     ${comp.fixed_payment:,.2f}",
        f"  ARM intro ({inputs.arm_intro_rate:.2%}): ${comp.arm_intro_payment:,.2f}",
        f"  ARM after adj ({inputs.arm_adjusted_rate:.2%}): "
        f"${comp.arm_post_adjustment_payment:,.2f}  "
        f"(+${result.arm_payment_shock_dollars:,.2f}, "
        f"+{result.arm_payment_shock_pct:.1%} shock)",
        "",
        f"Balance at adjustment (month {inputs.intro_years * 12}): "
        f"${comp.arm_balance_at_adjustment:,.0f}",
        "",
        f"Cost during intro period ({inputs.intro_years} yr)",
        f"  Fixed: ${result.fixed_cost_during_intro:,.0f}",
        f"  ARM:   ${result.arm_cost_during_intro:,.0f}",
        f"  ARM saves: ${result.arm_savings_during_intro:,.0f}",
        "",
        f"Total P&I over {inputs.term_years} years",
        f"  Fixed: ${result.fixed_total_cost:,.0f}",
        f"  ARM:   ${result.arm_total_cost:,.0f}",
        f"  Cheaper over full term: {result.cheaper_over_full_term.upper()}",
    ]

    if result.break_even_month is not None:
        year_num = (result.break_even_month - 1) // 12 + 1
        month_num = (result.break_even_month - 1) % 12 + 1
        lines.append(
            f"  Break-even (cumulative ARM exceeds fixed): month {result.break_even_month} "
            f"(year {year_num}, month {month_num})"
        )
    else:
        lines.append("  Break-even: ARM never exceeds fixed cumulative cost")

    return "\n".join(lines)


def _break_even_month(
    *,
    fixed_payment: float,
    arm_intro_payment: float,
    arm_post_payment: float,
    intro_months: int,
    total_months: int,
) -> int | None:
    """First month where cumulative ARM payments exceed cumulative fixed payments."""
    cum_fixed = 0.0
    cum_arm = 0.0
    for month in range(1, total_months + 1):
        cum_fixed += fixed_payment
        cum_arm += arm_intro_payment if month <= intro_months else arm_post_payment
        if cum_arm > cum_fixed:
            return month
    return None
