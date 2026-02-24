"""DTI binding analysis and income sensitivity for down payment affordability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseScenario,
    _validate_scenario,
    check_affordability,
)
from homeafford.dti_params import resolve_dti_params, scenario_at_down, scenario_at_income
from homeafford.dti_serialize import affordability_check_to_dict, dumps_dti_payload
from homeafford.model import (
    DownPaymentDtiModelResult,
    DEFAULT_DOWN_PAYMENT_PCTS,
    _validate_down_payment_pcts,
    model_down_payment_dti,
)

BindingConstraint = Literal["front_end", "back_end", "down_payment", "pass"]

DEFAULT_INCOME_MULTIPLIERS: tuple[float, ...] = (0.75, 0.85, 1.0, 1.15, 1.30)


@dataclass(frozen=True)
class DtiConstraintMargins:
    """Headroom to each affordability cap (positive means passing with room to spare)."""

    front_end_headroom: float
    back_end_headroom: float
    down_payment_headroom: float


@dataclass(frozen=True)
class DtiBindingRow:
    """Which DTI or down-payment constraint binds at one down payment level."""

    down_payment: float
    down_payment_pct: float
    check: AffordabilityCheckResult
    margins: DtiConstraintMargins
    binding: BindingConstraint


@dataclass(frozen=True)
class DtiBindingAnalysisResult:
    """Down payment sweep annotated with binding constraints and cap headroom."""

    home_price: float
    band_label: str | None
    front_end_cap: float
    back_end_cap: float
    rows: tuple[DtiBindingRow, ...]
    first_dti_pass_down_pct: float | None
    binding_at_min_down: BindingConstraint | None


@dataclass(frozen=True)
class IncomeDtiRow:
    """DTI outcome at one gross income level for a fixed purchase scenario."""

    gross_annual_income: float
    income_multiplier: float | None
    check: AffordabilityCheckResult


@dataclass(frozen=True)
class IncomeDtiSensitivityResult:
    """Income sweep for a fixed home price and down payment."""

    home_price: float
    down_payment: float
    down_payment_pct: float
    band_label: str | None
    base_income: float
    rows: tuple[IncomeDtiRow, ...]
    min_income: float | None
    min_income_multiplier: float | None


@dataclass(frozen=True)
class DownPaymentAffordabilityDiagnostic:
    """Combined down payment sweep, binding analysis, and income sensitivity."""

    dti_model: DownPaymentDtiModelResult
    binding: DtiBindingAnalysisResult
    income_sensitivity: IncomeDtiSensitivityResult | None


def _compute_margins(
    check: AffordabilityCheckResult,
    *,
    front_end_cap: float,
    back_end_cap: float,
    min_down_payment_pct: float,
) -> DtiConstraintMargins:
    return DtiConstraintMargins(
        front_end_headroom=front_end_cap - check.front_end_dti,
        back_end_headroom=back_end_cap - check.back_end_dti,
        down_payment_headroom=check.down_payment_pct - min_down_payment_pct,
    )


def _compute_binding(
    check: AffordabilityCheckResult,
    margins: DtiConstraintMargins,
) -> BindingConstraint:
    if check.passes:
        headroom = {
            "front_end": margins.front_end_headroom,
            "back_end": margins.back_end_headroom,
            "down_payment": margins.down_payment_headroom,
        }
        return min(headroom, key=headroom.get)  # type: ignore[arg-type]

    failing: dict[str, float] = {}
    if not check.passes_front_end:
        failing["front_end"] = margins.front_end_headroom
    if not check.passes_back_end:
        failing["back_end"] = margins.back_end_headroom
    if not check.passes_down_payment:
        failing["down_payment"] = margins.down_payment_headroom
    return min(failing, key=failing.get)  # type: ignore[return-value]


def _binding_row_from_check(
    *,
    down_payment: float,
    down_payment_pct: float,
    check: AffordabilityCheckResult,
    front_end_cap: float,
    back_end_cap: float,
    min_down_payment_pct: float,
) -> DtiBindingRow:
    margins = _compute_margins(
        check,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
    )
    return DtiBindingRow(
        down_payment=down_payment,
        down_payment_pct=down_payment_pct,
        check=check,
        margins=margins,
        binding=_compute_binding(check, margins),
    )


def _binding_analysis_from_dti_model(
    dti_model: DownPaymentDtiModelResult,
    *,
    front_end_cap: float,
    back_end_cap: float,
    min_down_payment_pct: float,
    pmi_annual_rate: float | None,
    pmi_ltv_threshold: float | None,
    mortgage_insurance_always: bool,
    band_label: str | None,
    scenario: PurchaseScenario,
) -> DtiBindingAnalysisResult:
    rows = tuple(
        _binding_row_from_check(
            down_payment=row.down_payment,
            down_payment_pct=row.down_payment_pct,
            check=row.check,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=min_down_payment_pct,
        )
        for row in dti_model.rows
    )
    first_dti_pass_down_pct: float | None = None
    for row in rows:
        if row.check.passes_front_end and row.check.passes_back_end:
            first_dti_pass_down_pct = row.down_payment_pct
            break

    binding_at_min_down: BindingConstraint | None = None
    if dti_model.min_down_payment is not None:
        min_check = check_affordability(
            scenario_at_down(scenario, dti_model.min_down_payment),
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=min_down_payment_pct,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
            mortgage_insurance_always=mortgage_insurance_always,
            band_label=band_label,
        )
        min_margins = _compute_margins(
            min_check,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=min_down_payment_pct,
        )
        binding_at_min_down = _compute_binding(min_check, min_margins)

    return DtiBindingAnalysisResult(
        home_price=dti_model.home_price,
        band_label=band_label,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        rows=rows,
        first_dti_pass_down_pct=first_dti_pass_down_pct,
        binding_at_min_down=binding_at_min_down,
    )


def analyze_dti_binding(
    scenario: PurchaseScenario,
    *,
    down_payment_pcts: tuple[float, ...] = DEFAULT_DOWN_PAYMENT_PCTS,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
    mortgage_insurance_always: bool = False,
    loan_program: str | None = None,
    band_label: str | None = None,
) -> DtiBindingAnalysisResult:
    """Sweep down payment levels and identify which constraint binds at each step."""
    _validate_scenario(scenario)
    _validate_down_payment_pcts(down_payment_pcts)
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

    dti_model = model_down_payment_dti(
        scenario,
        down_payment_pcts=down_payment_pcts,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        band_label=band_label,
    )
    return _binding_analysis_from_dti_model(
        dti_model,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        band_label=band_label,
        scenario=scenario,
    )


def _passes_dti_at_income(
    scenario: PurchaseScenario,
    *,
    gross_annual_income: float,
    front_end_cap: float,
    back_end_cap: float,
    pmi_annual_rate: float | None,
    pmi_ltv_threshold: float | None,
    mortgage_insurance_always: bool,
) -> bool:
    result = check_affordability(
        scenario_at_income(scenario, gross_annual_income),
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=0.0,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    )
    return result.passes_front_end and result.passes_back_end


def min_income_for_dti(
    scenario: PurchaseScenario,
    *,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
    mortgage_insurance_always: bool = False,
    loan_program: str | None = None,
    band_label: str | None = None,
    tolerance: float = 100.0,
) -> float | None:
    """Return the least gross annual income that passes DTI caps at a fixed down payment."""
    _validate_scenario(scenario)
    (
        front_end_cap,
        back_end_cap,
        _min_down_pct,
        pmi_annual_rate,
        pmi_ltv_threshold,
        mortgage_insurance_always,
    ) = resolve_dti_params(
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=0.03,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        loan_program=loan_program,
        band_label=band_label,
        market=scenario.market,
    )

    floor = max(scenario.monthly_debt_payments * 12 / back_end_cap, 1.0)
    ceiling = max(scenario.gross_annual_income * 5, floor * 2)

    while ceiling < 1_000_000_000 and not _passes_dti_at_income(
        scenario,
        gross_annual_income=ceiling,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    ):
        ceiling *= 2

    if not _passes_dti_at_income(
        scenario,
        gross_annual_income=ceiling,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    ):
        return None

    if _passes_dti_at_income(
        scenario,
        gross_annual_income=floor,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    ):
        return floor

    low, high = floor, ceiling
    while high - low > tolerance:
        mid = (low + high) / 2
        if _passes_dti_at_income(
            scenario,
            gross_annual_income=mid,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
            mortgage_insurance_always=mortgage_insurance_always,
        ):
            high = mid
        else:
            low = mid
    return high


def model_income_dti_sensitivity(
    scenario: PurchaseScenario,
    *,
    income_multipliers: tuple[float, ...] = DEFAULT_INCOME_MULTIPLIERS,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
    mortgage_insurance_always: bool = False,
    loan_program: str | None = None,
    band_label: str | None = None,
) -> IncomeDtiSensitivityResult:
    """Evaluate DTI affordability across several income levels for a fixed down payment."""
    _validate_scenario(scenario)
    base_income = scenario.gross_annual_income
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

    rows: list[IncomeDtiRow] = []
    for mult in income_multipliers:
        income = base_income * mult
        check = check_affordability(
            scenario_at_income(scenario, income),
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=min_down_payment_pct,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
            mortgage_insurance_always=mortgage_insurance_always,
            band_label=band_label,
        )
        rows.append(
            IncomeDtiRow(
                gross_annual_income=income,
                income_multiplier=mult,
                check=check,
            )
        )

    min_income = min_income_for_dti(
        scenario,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
    )
    min_mult = min_income / base_income if min_income is not None and base_income > 0 else None

    return IncomeDtiSensitivityResult(
        home_price=scenario.home_price,
        down_payment=scenario.down_payment,
        down_payment_pct=scenario.down_payment / scenario.home_price,
        band_label=band_label,
        base_income=base_income,
        rows=tuple(rows),
        min_income=min_income,
        min_income_multiplier=min_mult,
    )


def diagnose_down_payment_affordability(
    scenario: PurchaseScenario,
    *,
    down_payment_pcts: tuple[float, ...] = DEFAULT_DOWN_PAYMENT_PCTS,
    income_multipliers: tuple[float, ...] = DEFAULT_INCOME_MULTIPLIERS,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
    mortgage_insurance_always: bool = False,
    loan_program: str | None = None,
    band_label: str | None = None,
) -> DownPaymentAffordabilityDiagnostic:
    """Run down payment sweep, binding analysis, and income sensitivity at minimum down."""
    _validate_scenario(scenario)
    _validate_down_payment_pcts(down_payment_pcts)
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

    dti_model = model_down_payment_dti(
        scenario,
        down_payment_pcts=down_payment_pcts,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        band_label=band_label,
    )
    binding = _binding_analysis_from_dti_model(
        dti_model,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        band_label=band_label,
        scenario=scenario,
    )

    income_sensitivity: IncomeDtiSensitivityResult | None = None
    if dti_model.min_down_payment is not None:
        income_sensitivity = model_income_dti_sensitivity(
            scenario_at_down(scenario, dti_model.min_down_payment),
            income_multipliers=income_multipliers,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=min_down_payment_pct,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
            mortgage_insurance_always=mortgage_insurance_always,
            loan_program=loan_program,
            band_label=band_label,
        )

    return DownPaymentAffordabilityDiagnostic(
        dti_model=dti_model,
        binding=binding,
        income_sensitivity=income_sensitivity,
    )


def format_dti_binding_analysis(result: DtiBindingAnalysisResult) -> str:
    """Render a binding-constraint table for CLI or logging."""
    band = result.band_label or "custom"
    lines = [
        f"DTI binding analysis (${result.home_price:,.0f} home, {band} band)",
        f"Caps: front {result.front_end_cap:.0%}  back {result.back_end_cap:.0%}",
    ]
    if result.first_dti_pass_down_pct is not None:
        lines.append(f"First DTI pass at down: {result.first_dti_pass_down_pct:.1%}")
    if result.binding_at_min_down is not None:
        lines.append(f"Tightest constraint at min DTI down: {result.binding_at_min_down}")
    lines.append(
        f"{'Down %':>7}  {'Front Δ':>8}  {'Back Δ':>8}  {'Down Δ':>8}  "
        f"{'Binding':>12}  {'All':>5}"
    )
    for row in result.rows:
        m = row.margins
        all_status = "yes" if row.check.passes else "no"
        lines.append(
            f"{row.down_payment_pct:>6.1%}  "
            f"{m.front_end_headroom:>7.1%}  "
            f"{m.back_end_headroom:>7.1%}  "
            f"{m.down_payment_headroom:>7.1%}  "
            f"{row.binding:>12}  "
            f"{all_status}"
        )
    return "\n".join(lines)


def format_income_dti_sensitivity(result: IncomeDtiSensitivityResult) -> str:
    """Render an income sensitivity table for CLI or logging."""
    band = result.band_label or "custom"
    lines = [
        (
            f"Income DTI sensitivity (${result.home_price:,.0f} home, "
            f"{result.down_payment_pct:.1%} down, {band} band)"
        ),
    ]
    if result.min_income is not None:
        mult_str = (
            f" ({result.min_income_multiplier:.2f}x base)"
            if result.min_income_multiplier is not None
            else ""
        )
        lines.append(f"Minimum income for DTI pass: ${result.min_income:,.0f}{mult_str}")
    lines.append(
        f"{'Income':>12}  {'Mult':>6}  {'Front':>7}  {'Back':>7}  {'DTI':>5}  {'All':>5}"
    )
    for row in result.rows:
        dti_status = "yes" if row.check.passes_front_end and row.check.passes_back_end else "no"
        all_status = "yes" if row.check.passes else "no"
        mult = f"{row.income_multiplier:.2f}x" if row.income_multiplier is not None else "—"
        lines.append(
            f"${row.gross_annual_income:>11,.0f}  "
            f"{mult:>6}  "
            f"{row.check.front_end_dti:>6.1%}  "
            f"{row.check.back_end_dti:>6.1%}  "
            f"{dti_status:>5}  "
            f"{all_status}"
        )
    return "\n".join(lines)


def format_down_payment_affordability_diagnostic(
    diagnostic: DownPaymentAffordabilityDiagnostic,
) -> str:
    """Render the full down payment affordability diagnostic report."""
    from homeafford.model import format_down_payment_dti_model

    sections = [
        format_down_payment_dti_model(diagnostic.dti_model),
        "",
        format_dti_binding_analysis(diagnostic.binding),
    ]
    if diagnostic.income_sensitivity is not None:
        sections.extend(["", format_income_dti_sensitivity(diagnostic.income_sensitivity)])
    return "\n".join(sections)


def _binding_row_to_dict(row: DtiBindingRow) -> dict[str, object]:
    return {
        "down_payment": row.down_payment,
        "down_payment_pct": row.down_payment_pct,
        "binding": row.binding,
        "margins": {
            "front_end_headroom": row.margins.front_end_headroom,
            "back_end_headroom": row.margins.back_end_headroom,
            "down_payment_headroom": row.margins.down_payment_headroom,
        },
        "check": affordability_check_to_dict(row.check),
    }


def format_dti_binding_analysis_json(result: DtiBindingAnalysisResult) -> str:
    """Serialize a DTI binding analysis as JSON for scripting."""
    payload: dict[str, object] = {
        "home_price": result.home_price,
        "band_label": result.band_label,
        "front_end_cap": result.front_end_cap,
        "back_end_cap": result.back_end_cap,
        "first_dti_pass_down_pct": result.first_dti_pass_down_pct,
        "binding_at_min_down": result.binding_at_min_down,
        "rows": [_binding_row_to_dict(row) for row in result.rows],
    }
    return dumps_dti_payload(payload)


def format_income_dti_sensitivity_json(result: IncomeDtiSensitivityResult) -> str:
    """Serialize an income DTI sensitivity sweep as JSON for scripting."""
    payload: dict[str, object] = {
        "home_price": result.home_price,
        "down_payment": result.down_payment,
        "down_payment_pct": result.down_payment_pct,
        "band_label": result.band_label,
        "base_income": result.base_income,
        "min_income": result.min_income,
        "min_income_multiplier": result.min_income_multiplier,
        "rows": [
            {
                "gross_annual_income": row.gross_annual_income,
                "income_multiplier": row.income_multiplier,
                "check": affordability_check_to_dict(row.check),
            }
            for row in result.rows
        ],
    }
    return dumps_dti_payload(payload)


def format_down_payment_affordability_diagnostic_json(
    diagnostic: DownPaymentAffordabilityDiagnostic,
) -> str:
    """Serialize the full down payment affordability diagnostic as JSON for scripting."""
    payload: dict[str, object] = {
        "home_price": diagnostic.dti_model.home_price,
        "band_label": diagnostic.dti_model.band_label,
        "min_down_payment": diagnostic.dti_model.min_down_payment,
        "min_down_payment_pct": diagnostic.dti_model.min_down_payment_pct,
        "dti_model_rows": [
            {
                "down_payment": row.down_payment,
                "down_payment_pct": row.down_payment_pct,
                "check": affordability_check_to_dict(row.check),
            }
            for row in diagnostic.dti_model.rows
        ],
        "binding": {
            "front_end_cap": diagnostic.binding.front_end_cap,
            "back_end_cap": diagnostic.binding.back_end_cap,
            "first_dti_pass_down_pct": diagnostic.binding.first_dti_pass_down_pct,
            "binding_at_min_down": diagnostic.binding.binding_at_min_down,
            "rows": [_binding_row_to_dict(row) for row in diagnostic.binding.rows],
        },
    }
    if diagnostic.income_sensitivity is not None:
        sensitivity = diagnostic.income_sensitivity
        payload["income_sensitivity"] = {
            "down_payment": sensitivity.down_payment,
            "down_payment_pct": sensitivity.down_payment_pct,
            "base_income": sensitivity.base_income,
            "min_income": sensitivity.min_income,
            "min_income_multiplier": sensitivity.min_income_multiplier,
            "rows": [
                {
                    "gross_annual_income": row.gross_annual_income,
                    "income_multiplier": row.income_multiplier,
                    "check": affordability_check_to_dict(row.check),
                }
                for row in sensitivity.rows
            ],
        }
    return dumps_dti_payload(payload)
