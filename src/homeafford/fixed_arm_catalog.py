"""Preset fixed vs ARM mortgage calculator scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.check import PurchaseScenario
from homeafford.mortgage_scenario import (
    FixedArmDecisionReport,
    FixedArmPurchaseComparison,
    FixedArmScenarioInputs,
    FixedArmScenarioResult,
    analyze_fixed_arm_scenario,
    compare_fixed_arm_purchase,
    fixed_arm_decision_report,
    format_fixed_arm_purchase_comparison,
    format_fixed_arm_scenario,
)
from homeafford.fixed_arm_timeline import (
    build_fixed_arm_timeline,
    format_fixed_arm_timeline,
)


@dataclass(frozen=True)
class LoanScenarioPreset:
    """Named loan-only fixed vs ARM comparison inputs."""

    preset_id: str
    title: str
    description: str
    inputs: FixedArmScenarioInputs


@dataclass(frozen=True)
class PurchaseScenarioPreset:
    """Named purchase scenario with ARM rate assumptions."""

    preset_id: str
    title: str
    description: str
    purchase: PurchaseScenario
    arm_intro_rate: float
    arm_adjusted_rate: float
    intro_years: int = 5
    band_label: str = "conservative"


@dataclass(frozen=True)
class FixedArmScenarioCatalog:
    """Indexed collection of preset fixed vs ARM calculator scenarios."""

    loan_presets: tuple[LoanScenarioPreset, ...]
    purchase_presets: tuple[PurchaseScenarioPreset, ...]

    def list_loan_ids(self) -> tuple[str, ...]:
        """Return sorted loan preset identifiers."""
        return tuple(preset.preset_id for preset in self.loan_presets)

    def list_purchase_ids(self) -> tuple[str, ...]:
        """Return sorted purchase preset identifiers."""
        return tuple(preset.preset_id for preset in self.purchase_presets)

    def loan_preset(self, preset_id: str) -> LoanScenarioPreset:
        """Return one loan preset by identifier."""
        for preset in self.loan_presets:
            if preset.preset_id == preset_id:
                return preset
        known = ", ".join(self.list_loan_ids())
        raise ValueError(f"unknown loan preset {preset_id!r}; choose from: {known}")

    def purchase_preset(self, preset_id: str) -> PurchaseScenarioPreset:
        """Return one purchase preset by identifier."""
        for preset in self.purchase_presets:
            if preset.preset_id == preset_id:
                return preset
        known = ", ".join(self.list_purchase_ids())
        raise ValueError(
            f"unknown purchase preset {preset_id!r}; choose from: {known}"
        )


def default_fixed_arm_catalog() -> FixedArmScenarioCatalog:
    """Return the bundled fixed vs ARM scenario catalog."""
    return FixedArmScenarioCatalog(
        loan_presets=(
            LoanScenarioPreset(
                preset_id="five_one_standard",
                title="5/1 ARM — typical teaser spread",
                description=(
                    "$400k loan, 6.5% fixed vs 5.5% intro and 7.5% after adjustment"
                ),
                inputs=FixedArmScenarioInputs(
                    principal=400_000,
                    term_years=30,
                    fixed_rate=0.065,
                    arm_intro_rate=0.055,
                    arm_adjusted_rate=0.075,
                    intro_years=5,
                ),
            ),
            LoanScenarioPreset(
                preset_id="seven_one_hold",
                title="7/1 ARM — longer intro window",
                description=(
                    "$400k loan with a 7-year intro at 5.25% before adjusting to 7.0%"
                ),
                inputs=FixedArmScenarioInputs(
                    principal=400_000,
                    term_years=30,
                    fixed_rate=0.065,
                    arm_intro_rate=0.0525,
                    arm_adjusted_rate=0.07,
                    intro_years=7,
                ),
            ),
            LoanScenarioPreset(
                preset_id="rate_shock_plus_three",
                title="Severe +3% rate shock",
                description=(
                    "5/1 ARM where the adjusted rate jumps 3 points above the intro"
                ),
                inputs=FixedArmScenarioInputs(
                    principal=400_000,
                    term_years=30,
                    fixed_rate=0.065,
                    arm_intro_rate=0.05,
                    arm_adjusted_rate=0.08,
                    intro_years=5,
                ),
            ),
            LoanScenarioPreset(
                preset_id="flat_rates",
                title="No intro savings",
                description="Intro rate matches fixed; ARM only loses after adjustment",
                inputs=FixedArmScenarioInputs(
                    principal=400_000,
                    term_years=30,
                    fixed_rate=0.065,
                    arm_intro_rate=0.065,
                    arm_adjusted_rate=0.085,
                    intro_years=5,
                ),
            ),
            LoanScenarioPreset(
                preset_id="arm_wins_full_term",
                title="ARM stays cheaper",
                description="Low intro and modest adjustment keep ARM ahead over 30 years",
                inputs=FixedArmScenarioInputs(
                    principal=400_000,
                    term_years=30,
                    fixed_rate=0.065,
                    arm_intro_rate=0.05,
                    arm_adjusted_rate=0.06,
                    intro_years=5,
                ),
            ),
            LoanScenarioPreset(
                preset_id="ten_one_jumbo",
                title="10/1 ARM — jumbo loan",
                description=(
                    "$750k jumbo with a decade-long intro at 6.0% before adjusting to 7.25%"
                ),
                inputs=FixedArmScenarioInputs(
                    principal=750_000,
                    term_years=30,
                    fixed_rate=0.0675,
                    arm_intro_rate=0.06,
                    arm_adjusted_rate=0.0725,
                    intro_years=10,
                ),
            ),
        ),
        purchase_presets=(
            PurchaseScenarioPreset(
                preset_id="starter_home",
                title="Starter home — 20% down",
                description=(
                    "$450k home, $90k down, $120k income; typical 5/1 ARM spread"
                ),
                purchase=PurchaseScenario(
                    home_price=450_000,
                    down_payment=90_000,
                    gross_annual_income=120_000,
                    monthly_debt_payments=350,
                    mortgage_rate=0.065,
                ),
                arm_intro_rate=0.055,
                arm_adjusted_rate=0.075,
                intro_years=5,
                band_label="conservative",
            ),
            PurchaseScenarioPreset(
                preset_id="dti_tight",
                title="DTI fails after adjustment",
                description=(
                    "$500k home on $150k income where intro passes but post-adjustment "
                    "ARM breaches conservative DTI caps"
                ),
                purchase=PurchaseScenario(
                    home_price=500_000,
                    down_payment=100_000,
                    gross_annual_income=150_000,
                    monthly_debt_payments=500,
                    mortgage_rate=0.065,
                ),
                arm_intro_rate=0.055,
                arm_adjusted_rate=0.095,
                intro_years=5,
                band_label="conservative",
            ),
            PurchaseScenarioPreset(
                preset_id="high_equity",
                title="High equity — comfortable DTI",
                description=(
                    "$600k home with $200k down; ARM shock stays within moderate band"
                ),
                purchase=PurchaseScenario(
                    home_price=600_000,
                    down_payment=200_000,
                    gross_annual_income=180_000,
                    monthly_debt_payments=400,
                    mortgage_rate=0.0625,
                ),
                arm_intro_rate=0.0525,
                arm_adjusted_rate=0.0725,
                intro_years=5,
                band_label="moderate",
            ),
            PurchaseScenarioPreset(
                preset_id="low_down_starter",
                title="Low down — PMI and ARM shock",
                description=(
                    "$360k home with 5% down on $115k income; intro passes moderate "
                    "DTI but post-adjustment ARM breaches caps"
                ),
                purchase=PurchaseScenario(
                    home_price=360_000,
                    down_payment=18_000,
                    gross_annual_income=115_000,
                    monthly_debt_payments=300,
                    mortgage_rate=0.065,
                ),
                arm_intro_rate=0.055,
                arm_adjusted_rate=0.09,
                intro_years=5,
                band_label="moderate",
            ),
        ),
    )


def analyze_loan_preset(
    preset: LoanScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None = None,
) -> FixedArmScenarioResult:
    """Run loan-only fixed vs ARM analysis for a catalog preset."""
    resolved = _resolve_loan_preset(preset, catalog=catalog)
    return analyze_fixed_arm_scenario(resolved.inputs)


def compare_purchase_preset(
    preset: PurchaseScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None = None,
) -> FixedArmPurchaseComparison:
    """Run purchase fixed vs ARM comparison for a catalog preset."""
    resolved = _resolve_purchase_preset(preset, catalog=catalog)
    return compare_fixed_arm_purchase(
        resolved.purchase,
        arm_intro_rate=resolved.arm_intro_rate,
        arm_adjusted_rate=resolved.arm_adjusted_rate,
        intro_years=resolved.intro_years,
        band_label=resolved.band_label,
    )


def purchase_preset_decision_report(
    preset: PurchaseScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None = None,
    sweep_adjusted_rates: tuple[float, ...] | None = None,
) -> FixedArmDecisionReport:
    """Build a fixed vs ARM decision report for a catalog purchase preset."""
    resolved = _resolve_purchase_preset(preset, catalog=catalog)
    return fixed_arm_decision_report(
        resolved.purchase,
        arm_intro_rate=resolved.arm_intro_rate,
        arm_adjusted_rate=resolved.arm_adjusted_rate,
        intro_years=resolved.intro_years,
        band_label=resolved.band_label,
        sweep_adjusted_rates=sweep_adjusted_rates,
    )


def format_catalog_listing(catalog: FixedArmScenarioCatalog | None = None) -> str:
    """Render a human-readable list of available presets."""
    resolved = catalog or default_fixed_arm_catalog()
    lines = ["Fixed vs ARM scenario catalog", ""]
    lines.append("Loan presets:")
    for preset in resolved.loan_presets:
        lines.append(f"  {preset.preset_id}")
        lines.append(f"    {preset.title}")
        lines.append(f"    {preset.description}")
    lines.append("")
    lines.append("Purchase presets:")
    for preset in resolved.purchase_presets:
        lines.append(f"  {preset.preset_id}")
        lines.append(f"    {preset.title}")
        lines.append(f"    {preset.description}")
    return "\n".join(lines)


def format_purchase_preset_matrix(catalog: FixedArmScenarioCatalog | None = None) -> str:
    """Render a side-by-side summary of all purchase presets with DTI and decisions."""
    resolved = catalog or default_fixed_arm_catalog()
    lines = [
        "Purchase preset comparison matrix",
        "",
        f"{'Preset':<22}  {'Home':>10}  {'Intro DTI':>9}  {'Post DTI':>8}  "
        f"{'Winner':>6}  {'Decision':>18}",
    ]
    for preset in resolved.purchase_presets:
        comparison = compare_purchase_preset(preset, catalog=resolved)
        intro_row = next(
            row for row in comparison.dti_rows if row.label == "arm_intro"
        )
        post_row = next(row for row in comparison.dti_rows if row.label == "arm_post")
        intro_ok = (
            "pass"
            if intro_row.passes_front_end and intro_row.passes_back_end
            else "fail"
        )
        post_ok = (
            "pass"
            if post_row.passes_front_end and post_row.passes_back_end
            else "fail"
        )
        winner = comparison.loan_result.cheaper_over_full_term
        report = purchase_preset_decision_report(preset, catalog=resolved)
        decision = report.recommendation.replace("_", " ")
        lines.append(
            f"{preset.preset_id:<22}  "
            f"${comparison.scenario.home_price:>9,.0f}  "
            f"{intro_ok:>9}  "
            f"{post_ok:>8}  "
            f"{winner:>6}  "
            f"{decision:>18}"
        )
    return "\n".join(lines)


def format_loan_preset_matrix(catalog: FixedArmScenarioCatalog | None = None) -> str:
    """Render a side-by-side summary of all loan presets."""
    resolved = catalog or default_fixed_arm_catalog()
    lines = [
        "Loan preset comparison matrix",
        "",
        f"{'Preset':<22}  {'Fixed P&I':>10}  {'ARM intro':>10}  "
        f"{'ARM post':>10}  {'Intro save':>11}  {'Winner':>6}  Break-even",
    ]
    for preset in resolved.loan_presets:
        result = analyze_fixed_arm_scenario(preset.inputs)
        comp = result.comparison
        break_even = (
            f"month {result.break_even_month}"
            if result.break_even_month is not None
            else "never"
        )
        lines.append(
            f"{preset.preset_id:<22}  "
            f"${comp.fixed_payment:>9,.0f}  "
            f"${comp.arm_intro_payment:>9,.0f}  "
            f"${comp.arm_post_adjustment_payment:>9,.0f}  "
            f"${result.arm_savings_during_intro:>10,.0f}  "
            f"{result.cheaper_over_full_term:>6}  "
            f"{break_even}"
        )
    return "\n".join(lines)


def format_loan_preset_timeline(
    preset: LoanScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None = None,
) -> str:
    """Render a year-by-year fixed vs ARM timeline for one loan preset."""
    resolved = _resolve_loan_preset(preset, catalog=catalog)
    timeline = build_fixed_arm_timeline(resolved.inputs)
    lines = [
        f"Loan preset timeline: {resolved.preset_id} — {resolved.title}",
        resolved.description,
        "",
        format_fixed_arm_timeline(timeline),
    ]
    return "\n".join(lines)


def format_loan_preset_detail(
    preset: LoanScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None = None,
) -> str:
    """Render full loan scenario output for one preset."""
    resolved = _resolve_loan_preset(preset, catalog=catalog)
    result = analyze_fixed_arm_scenario(resolved.inputs)
    lines = [
        f"Loan preset: {resolved.preset_id} — {resolved.title}",
        resolved.description,
        "",
        format_fixed_arm_scenario(result),
    ]
    return "\n".join(lines)


def format_purchase_preset_detail(
    preset: PurchaseScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None = None,
) -> str:
    """Render full purchase comparison output for one preset."""
    resolved = _resolve_purchase_preset(preset, catalog=catalog)
    result = compare_purchase_preset(resolved, catalog=catalog)
    lines = [
        f"Purchase preset: {resolved.preset_id} — {resolved.title}",
        resolved.description,
        "",
        format_fixed_arm_purchase_comparison(result),
    ]
    return "\n".join(lines)


def _resolve_loan_preset(
    preset: LoanScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None,
) -> LoanScenarioPreset:
    if isinstance(preset, LoanScenarioPreset):
        return preset
    resolved_catalog = catalog or default_fixed_arm_catalog()
    return resolved_catalog.loan_preset(preset)


def _resolve_purchase_preset(
    preset: PurchaseScenarioPreset | str,
    *,
    catalog: FixedArmScenarioCatalog | None,
) -> PurchaseScenarioPreset:
    if isinstance(preset, PurchaseScenarioPreset):
        return preset
    resolved_catalog = catalog or default_fixed_arm_catalog()
    return resolved_catalog.purchase_preset(preset)
