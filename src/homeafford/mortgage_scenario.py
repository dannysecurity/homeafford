"""Fixed-rate vs ARM mortgage scenario analysis."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.check import PurchaseScenario, _band_caps, _validate_scenario
from homeafford.market.resolve import effective_market_fields, effective_pmi_fields
from homeafford.mortgage import FixedVsArmComparison, compare_fixed_vs_arm
from homeafford.piti import compute_dti_ratios, compute_piti


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


@dataclass(frozen=True)
class FixedArmDtiRow:
    """PITI and DTI outcome for one phase of a fixed vs ARM purchase."""

    label: str
    display_name: str
    principal_and_interest: float
    piti: float
    front_end_dti: float
    back_end_dti: float
    passes_front_end: bool
    passes_back_end: bool


@dataclass(frozen=True)
class FixedArmPurchaseComparison:
    """Fixed vs ARM loan math plus purchase DTI impact across ARM phases."""

    scenario: PurchaseScenario
    loan_result: FixedArmScenarioResult
    band_label: str | None
    front_end_cap: float
    back_end_cap: float
    dti_rows: tuple[FixedArmDtiRow, ...]
    post_adjustment_fails_band: bool


def fixed_arm_inputs_from_purchase(
    scenario: PurchaseScenario,
    *,
    arm_intro_rate: float,
    arm_adjusted_rate: float,
    intro_years: int = 5,
) -> FixedArmScenarioInputs:
    """Build fixed vs ARM comparison inputs from a purchase scenario's loan."""
    principal = scenario.home_price - scenario.down_payment
    if principal <= 0:
        raise ValueError("principal must be positive")

    return FixedArmScenarioInputs(
        principal=principal,
        term_years=scenario.loan_term_years,
        fixed_rate=scenario.mortgage_rate,
        arm_intro_rate=arm_intro_rate,
        arm_adjusted_rate=arm_adjusted_rate,
        intro_years=intro_years,
    )


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


def compare_fixed_arm_purchase(
    scenario: PurchaseScenario,
    *,
    arm_intro_rate: float,
    arm_adjusted_rate: float,
    intro_years: int = 5,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    band_label: str | None = None,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
) -> FixedArmPurchaseComparison:
    """Compare fixed vs ARM loan costs and DTI across intro and post-adjustment phases."""
    _validate_scenario(scenario)
    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    loan_inputs = fixed_arm_inputs_from_purchase(
        scenario,
        arm_intro_rate=arm_intro_rate,
        arm_adjusted_rate=arm_adjusted_rate,
        intro_years=intro_years,
    )
    loan_result = analyze_fixed_arm_scenario(loan_inputs)
    comp = loan_result.comparison

    _, property_tax_rate, insurance_annual = effective_market_fields(
        market=scenario.market,
        mortgage_rate=scenario.mortgage_rate,
        property_tax_rate=scenario.property_tax_rate,
        insurance_annual=scenario.insurance_annual,
    )
    resolved_pmi_rate, resolved_pmi_threshold = effective_pmi_fields(
        market=scenario.market,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
    )

    loan_amount = scenario.home_price - scenario.down_payment
    phases = (
        ("fixed", "Fixed rate", comp.fixed_payment),
        ("arm_intro", "ARM intro", comp.arm_intro_payment),
        (
            "arm_post",
            "ARM after adj",
            comp.arm_post_adjustment_payment,
        ),
    )

    dti_rows: list[FixedArmDtiRow] = []
    for label, display_name, payment in phases:
        breakdown = compute_piti(
            loan_amount=loan_amount,
            property_tax_rate=property_tax_rate,
            insurance_annual=insurance_annual,
            hoa_monthly=scenario.hoa_monthly,
            mortgage_rate=scenario.mortgage_rate,
            loan_term_years=scenario.loan_term_years,
            home_price=scenario.home_price,
            pmi_annual_rate=resolved_pmi_rate,
            pmi_ltv_threshold=resolved_pmi_threshold,
            principal_and_interest=payment,
        )
        front_end, back_end = compute_dti_ratios(
            piti=breakdown.piti,
            gross_annual_income=scenario.gross_annual_income,
            monthly_debt_payments=scenario.monthly_debt_payments,
        )
        dti_rows.append(
            FixedArmDtiRow(
                label=label,
                display_name=display_name,
                principal_and_interest=payment,
                piti=breakdown.piti,
                front_end_dti=front_end,
                back_end_dti=back_end,
                passes_front_end=front_end <= front_end_cap,
                passes_back_end=back_end <= back_end_cap,
            )
        )

    post_row = dti_rows[-1]
    post_adjustment_fails_band = (
        not post_row.passes_front_end or not post_row.passes_back_end
    )

    return FixedArmPurchaseComparison(
        scenario=scenario,
        loan_result=loan_result,
        band_label=band_label,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        dti_rows=tuple(dti_rows),
        post_adjustment_fails_band=post_adjustment_fails_band,
    )


def format_fixed_arm_purchase_comparison(result: FixedArmPurchaseComparison) -> str:
    """Render loan comparison plus DTI impact for a purchase scenario."""
    scenario = result.scenario
    band = result.band_label or "custom"
    lines = [
        f"Fixed vs ARM purchase (${scenario.home_price:,.0f} home, "
        f"${scenario.down_payment:,.0f} down, {band} band)",
        "",
        format_fixed_arm_scenario(result.loan_result),
        "",
        f"DTI impact (caps: front {result.front_end_cap:.0%}, "
        f"back {result.back_end_cap:.0%})",
        f"{'Phase':>14}  {'P&I':>10}  {'PITI':>10}  "
        f"{'Front DTI':>9}  {'Back DTI':>9}  Pass",
    ]
    for row in result.dti_rows:
        passes = row.passes_front_end and row.passes_back_end
        status = "yes" if passes else "no"
        lines.append(
            f"{row.display_name:>14}  "
            f"${row.principal_and_interest:>9,.0f}  "
            f"${row.piti:>9,.0f}  "
            f"{row.front_end_dti:>8.1%}  "
            f"{row.back_end_dti:>8.1%}  "
            f"{status}"
        )

    if result.post_adjustment_fails_band:
        lines.append("")
        lines.append(
            "Warning: post-adjustment ARM payment exceeds DTI caps "
            "even if intro period passes."
        )
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
