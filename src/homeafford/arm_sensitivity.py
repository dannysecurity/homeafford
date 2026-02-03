"""Sensitivity analysis for fixed vs ARM scenarios across post-adjustment rates."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.check import PurchaseScenario, _band_caps, _validate_scenario
from homeafford.mortgage import format_arm_label
from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    FixedArmScenarioResult,
    analyze_fixed_arm_scenario,
    compare_fixed_arm_purchase,
)

DEFAULT_ADJUSTED_RATES: tuple[float, ...] = (
    0.055,
    0.06,
    0.065,
    0.07,
    0.075,
    0.08,
    0.085,
    0.09,
    0.095,
    0.10,
)


@dataclass(frozen=True)
class ArmAdjustedRateRow:
    """Loan-level fixed vs ARM outcome at one post-adjustment rate."""

    arm_adjusted_rate: float
    result: FixedArmScenarioResult
    post_adjustment_pi: float
    payment_shock_dollars: float
    cheaper_over_full_term: str
    break_even_month: int | None


@dataclass(frozen=True)
class ArmRateSensitivityResult:
    """Sweep of ARM post-adjustment rates for a single loan comparison."""

    base_inputs: FixedArmScenarioInputs
    adjusted_rates: tuple[float, ...]
    rows: tuple[ArmAdjustedRateRow, ...]
    fixed_wins_from_rate: float | None
    arm_always_cheaper: bool


@dataclass(frozen=True)
class ArmPurchaseSensitivityRow:
    """Purchase DTI and loan outcome at one post-adjustment ARM rate."""

    arm_adjusted_rate: float
    loan_result: FixedArmScenarioResult
    post_adjustment_pi: float
    post_adjustment_piti: float
    post_adjustment_front_end_dti: float
    post_adjustment_back_end_dti: float
    post_adjustment_passes_dti: bool
    cheaper_over_full_term: str


@dataclass(frozen=True)
class ArmPurchaseSensitivityResult:
    """Sweep of post-adjustment rates with DTI impact for a purchase scenario."""

    scenario: PurchaseScenario
    arm_intro_rate: float
    intro_years: int
    band_label: str | None
    front_end_cap: float
    back_end_cap: float
    adjusted_rates: tuple[float, ...]
    rows: tuple[ArmPurchaseSensitivityRow, ...]
    max_rate_passing_dti: float | None
    fixed_wins_from_rate: float | None


def _build_base_inputs(
    *,
    principal: float,
    term_years: int,
    fixed_rate: float,
    arm_intro_rate: float,
    arm_adjusted_rate: float,
    intro_years: int,
) -> FixedArmScenarioInputs:
    return FixedArmScenarioInputs(
        principal=principal,
        term_years=term_years,
        fixed_rate=fixed_rate,
        arm_intro_rate=arm_intro_rate,
        arm_adjusted_rate=arm_adjusted_rate,
        intro_years=intro_years,
    )


def _fixed_wins_from_rate(rows: tuple[ArmAdjustedRateRow, ...]) -> float | None:
    for row in rows:
        if row.cheaper_over_full_term == "fixed":
            return row.arm_adjusted_rate
    return None


def sweep_arm_adjusted_rates(
    *,
    principal: float,
    term_years: int,
    fixed_rate: float,
    arm_intro_rate: float,
    adjusted_rates: tuple[float, ...] = DEFAULT_ADJUSTED_RATES,
    intro_years: int = 5,
) -> ArmRateSensitivityResult:
    """Sweep post-adjustment ARM rates and compare each against a fixed-rate loan."""
    if principal <= 0:
        raise ValueError("principal must be positive")
    if term_years <= 0:
        raise ValueError("term_years must be positive")
    if not adjusted_rates:
        raise ValueError("adjusted_rates must not be empty")

    sorted_rates = tuple(sorted(adjusted_rates))
    rows: list[ArmAdjustedRateRow] = []
    for rate in sorted_rates:
        inputs = _build_base_inputs(
            principal=principal,
            term_years=term_years,
            fixed_rate=fixed_rate,
            arm_intro_rate=arm_intro_rate,
            arm_adjusted_rate=rate,
            intro_years=intro_years,
        )
        result = analyze_fixed_arm_scenario(inputs)
        rows.append(
            ArmAdjustedRateRow(
                arm_adjusted_rate=rate,
                result=result,
                post_adjustment_pi=result.comparison.arm_post_adjustment_payment,
                payment_shock_dollars=result.arm_payment_shock_dollars,
                cheaper_over_full_term=result.cheaper_over_full_term,
                break_even_month=result.break_even_month,
            )
        )

    fixed_wins = _fixed_wins_from_rate(tuple(rows))
    return ArmRateSensitivityResult(
        base_inputs=_build_base_inputs(
            principal=principal,
            term_years=term_years,
            fixed_rate=fixed_rate,
            arm_intro_rate=arm_intro_rate,
            arm_adjusted_rate=sorted_rates[0],
            intro_years=intro_years,
        ),
        adjusted_rates=sorted_rates,
        rows=tuple(rows),
        fixed_wins_from_rate=fixed_wins,
        arm_always_cheaper=fixed_wins is None,
    )


def sweep_arm_adjusted_rates_purchase(
    scenario: PurchaseScenario,
    *,
    arm_intro_rate: float,
    adjusted_rates: tuple[float, ...] = DEFAULT_ADJUSTED_RATES,
    intro_years: int = 5,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    band_label: str | None = None,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
) -> ArmPurchaseSensitivityResult:
    """Sweep post-adjustment ARM rates for a purchase, including DTI pass/fail."""
    _validate_scenario(scenario)
    if not adjusted_rates:
        raise ValueError("adjusted_rates must not be empty")
    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    sorted_rates = tuple(sorted(adjusted_rates))
    rows: list[ArmPurchaseSensitivityRow] = []
    max_passing: float | None = None

    for rate in sorted_rates:
        comparison = compare_fixed_arm_purchase(
            scenario,
            arm_intro_rate=arm_intro_rate,
            arm_adjusted_rate=rate,
            intro_years=intro_years,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            band_label=band_label,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        post_row = next(row for row in comparison.dti_rows if row.label == "arm_post")
        passes = post_row.passes_front_end and post_row.passes_back_end
        if passes:
            max_passing = rate

        rows.append(
            ArmPurchaseSensitivityRow(
                arm_adjusted_rate=rate,
                loan_result=comparison.loan_result,
                post_adjustment_pi=post_row.principal_and_interest,
                post_adjustment_piti=post_row.piti,
                post_adjustment_front_end_dti=post_row.front_end_dti,
                post_adjustment_back_end_dti=post_row.back_end_dti,
                post_adjustment_passes_dti=passes,
                cheaper_over_full_term=comparison.loan_result.cheaper_over_full_term,
            )
        )

    loan_rows = tuple(
        ArmAdjustedRateRow(
            arm_adjusted_rate=row.arm_adjusted_rate,
            result=row.loan_result,
            post_adjustment_pi=row.post_adjustment_pi,
            payment_shock_dollars=row.loan_result.arm_payment_shock_dollars,
            cheaper_over_full_term=row.cheaper_over_full_term,
            break_even_month=row.loan_result.break_even_month,
        )
        for row in rows
    )

    return ArmPurchaseSensitivityResult(
        scenario=scenario,
        arm_intro_rate=arm_intro_rate,
        intro_years=intro_years,
        band_label=band_label,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        adjusted_rates=sorted_rates,
        rows=tuple(rows),
        max_rate_passing_dti=max_passing,
        fixed_wins_from_rate=_fixed_wins_from_rate(loan_rows),
    )


def format_arm_rate_sensitivity(result: ArmRateSensitivityResult) -> str:
    """Render a loan-level ARM adjusted-rate sensitivity table."""
    inputs = result.base_inputs
    lines = [
        "ARM post-adjustment rate sensitivity",
        f"Loan: ${inputs.principal:,.0f} over {inputs.term_years} years "
        f"({format_arm_label(inputs.intro_years)})",
        f"Fixed rate: {inputs.fixed_rate:.2%}  ARM intro: {inputs.arm_intro_rate:.2%}",
        "",
    ]
    if result.fixed_wins_from_rate is not None:
        lines.append(
            f"Fixed becomes cheaper from adjusted rate: {result.fixed_wins_from_rate:.2%}"
        )
    else:
        lines.append("Fixed never cheaper over full term at these adjusted rates")
    lines.append("")
    lines.append(
        f"{'Adj rate':>8}  {'Post P&I':>10}  {'Shock $':>9}  "
        f"{'Break-even':>10}  {'Cheaper':>7}"
    )
    for row in result.rows:
        be = str(row.break_even_month) if row.break_even_month is not None else "never"
        lines.append(
            f"{row.arm_adjusted_rate:>7.2%}  "
            f"${row.post_adjustment_pi:>9,.0f}  "
            f"${row.payment_shock_dollars:>8,.0f}  "
            f"{be:>10}  "
            f"{row.cheaper_over_full_term.upper():>7}"
        )
    return "\n".join(lines)


def format_arm_purchase_sensitivity(result: ArmPurchaseSensitivityResult) -> str:
    """Render purchase ARM sensitivity with DTI pass/fail per adjusted rate."""
    scenario = result.scenario
    band = result.band_label or "custom"
    lines = [
        "ARM post-adjustment rate sensitivity (purchase)",
        f"Home: ${scenario.home_price:,.0f}  Down: ${scenario.down_payment:,.0f}  "
        f"Fixed rate: {scenario.mortgage_rate:.2%}  "
        f"ARM intro: {result.arm_intro_rate:.2%}  "
        f"({format_arm_label(result.intro_years)})",
        f"DTI band: {band} (front {result.front_end_cap:.0%}, back {result.back_end_cap:.0%})",
        "",
    ]
    if result.max_rate_passing_dti is not None:
        lines.append(
            f"Highest adjusted rate passing DTI: {result.max_rate_passing_dti:.2%}"
        )
    else:
        lines.append("No adjusted rate in sweep passes post-adjustment DTI caps")
    if result.fixed_wins_from_rate is not None:
        lines.append(
            f"Fixed becomes cheaper from adjusted rate: {result.fixed_wins_from_rate:.2%}"
        )
    else:
        lines.append("Fixed never cheaper over full term at these adjusted rates")
    lines.append("")
    lines.append(
        f"{'Adj rate':>8}  {'Post P&I':>10}  {'PITI':>10}  "
        f"{'Back DTI':>9}  {'DTI':>4}  {'Cheaper':>7}"
    )
    for row in result.rows:
        dti_status = "pass" if row.post_adjustment_passes_dti else "fail"
        lines.append(
            f"{row.arm_adjusted_rate:>7.2%}  "
            f"${row.post_adjustment_pi:>9,.0f}  "
            f"${row.post_adjustment_piti:>9,.0f}  "
            f"{row.post_adjustment_back_end_dti:>8.1%}  "
            f"{dti_status:>4}  "
            f"{row.cheaper_over_full_term.upper():>7}"
        )
    return "\n".join(lines)
