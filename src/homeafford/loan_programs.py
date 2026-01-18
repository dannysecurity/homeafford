"""Loan program rules for down payment floors and mortgage insurance in DTI checks."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseScenario,
    _band_caps,
    _validate_scenario,
    check_affordability,
)
from homeafford.market.resolve import effective_pmi_fields

if TYPE_CHECKING:
    from homeafford.market.snapshot import MarketSnapshot


@dataclass(frozen=True)
class LoanProgram:
    """Down payment and mortgage insurance rules for a loan program."""

    name: str
    display_name: str
    min_down_payment_pct: float
    pmi_ltv_threshold: float
    default_pmi_annual_rate: float | None
    mortgage_insurance_always: bool


@dataclass(frozen=True)
class ProgramDtiParams:
    """Resolved PMI and down-payment parameters for affordability checks."""

    program: LoanProgram
    min_down_payment_pct: float
    pmi_annual_rate: float
    pmi_ltv_threshold: float
    mortgage_insurance_always: bool


@dataclass(frozen=True)
class LoanProgramDtiRow:
    """Minimum down payment and DTI outcome for one loan program."""

    program: LoanProgram
    min_down_payment: float | None
    min_down_payment_pct: float | None
    check_at_min_down: AffordabilityCheckResult | None


@dataclass(frozen=True)
class LoanProgramDtiComparison:
    """Side-by-side DTI minimum down payment across loan programs."""

    home_price: float
    band_label: str | None
    rows: tuple[LoanProgramDtiRow, ...]


_LOAN_PROGRAMS: dict[str, LoanProgram] = {
    "conventional": LoanProgram(
        name="conventional",
        display_name="Conventional",
        min_down_payment_pct=0.03,
        pmi_ltv_threshold=0.80,
        default_pmi_annual_rate=None,
        mortgage_insurance_always=False,
    ),
    "fha": LoanProgram(
        name="fha",
        display_name="FHA",
        min_down_payment_pct=0.035,
        pmi_ltv_threshold=1.0,
        default_pmi_annual_rate=0.0055,
        mortgage_insurance_always=True,
    ),
    "va": LoanProgram(
        name="va",
        display_name="VA",
        min_down_payment_pct=0.0,
        pmi_ltv_threshold=1.0,
        default_pmi_annual_rate=0.0,
        mortgage_insurance_always=False,
    ),
}


def available_loan_programs() -> tuple[str, ...]:
    """Return registered loan program names in sorted order."""
    return tuple(sorted(_LOAN_PROGRAMS))


def get_loan_program(name: str) -> LoanProgram:
    """Look up a loan program by registry name."""
    try:
        return _LOAN_PROGRAMS[name]
    except KeyError as exc:
        valid = ", ".join(available_loan_programs())
        raise ValueError(f"unknown loan program {name!r}; expected one of: {valid}") from exc


def resolve_program_dti_params(
    program_name: str,
    *,
    market: MarketSnapshot | None = None,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
) -> ProgramDtiParams:
    """Resolve PMI and down-payment floors for a named loan program."""
    program = get_loan_program(program_name)
    market_rate, market_threshold = effective_pmi_fields(
        market=market,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
    )
    if program.default_pmi_annual_rate is not None:
        resolved_rate = program.default_pmi_annual_rate
    elif pmi_annual_rate is not None:
        resolved_rate = pmi_annual_rate
    else:
        resolved_rate = market_rate

    resolved_threshold = (
        program.pmi_ltv_threshold
        if program.mortgage_insurance_always
        else (pmi_ltv_threshold if pmi_ltv_threshold is not None else market_threshold)
    )

    return ProgramDtiParams(
        program=program,
        min_down_payment_pct=program.min_down_payment_pct,
        pmi_annual_rate=resolved_rate,
        pmi_ltv_threshold=resolved_threshold,
        mortgage_insurance_always=program.mortgage_insurance_always,
    )


def compare_loan_program_dti(
    scenario: PurchaseScenario,
    *,
    programs: tuple[str, ...] = ("conventional", "fha", "va"),
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    band_label: str | None = None,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
) -> LoanProgramDtiComparison:
    """Compare minimum down payments required to pass DTI caps across loan programs."""
    from homeafford.model import min_down_payment_for_dti

    _validate_scenario(scenario)
    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    rows: list[LoanProgramDtiRow] = []
    for program_name in programs:
        params = resolve_program_dti_params(
            program_name,
            market=scenario.market,
            pmi_annual_rate=pmi_annual_rate,
            pmi_ltv_threshold=pmi_ltv_threshold,
        )
        min_down = min_down_payment_for_dti(
            scenario,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=params.min_down_payment_pct,
            pmi_annual_rate=params.pmi_annual_rate,
            pmi_ltv_threshold=params.pmi_ltv_threshold,
            mortgage_insurance_always=params.mortgage_insurance_always,
        )
        min_pct = min_down / scenario.home_price if min_down is not None else None
        check_at_min = None
        if min_down is not None:
            scenario_at_min = replace(scenario, down_payment=min_down)
            check_at_min = check_affordability(
                scenario_at_min,
                front_end_cap=front_end_cap,
                back_end_cap=back_end_cap,
                min_down_payment_pct=params.min_down_payment_pct,
                pmi_annual_rate=params.pmi_annual_rate,
                pmi_ltv_threshold=params.pmi_ltv_threshold,
                mortgage_insurance_always=params.mortgage_insurance_always,
                band_label=band_label,
            )
        rows.append(
            LoanProgramDtiRow(
                program=params.program,
                min_down_payment=min_down,
                min_down_payment_pct=min_pct,
                check_at_min_down=check_at_min,
            )
        )

    return LoanProgramDtiComparison(
        home_price=scenario.home_price,
        band_label=band_label,
        rows=tuple(rows),
    )


def format_loan_program_dti_comparison(result: LoanProgramDtiComparison) -> str:
    """Render a loan-program comparison table for CLI or logging."""
    band = result.band_label or "custom"
    lines = [
        f"Loan program DTI comparison (${result.home_price:,.0f} home, {band} band)",
        f"{'Program':>12}  {'Min down %':>10}  {'Min down $':>12}  "
        f"{'Front DTI':>9}  {'Back DTI':>9}  Pass",
    ]
    for row in result.rows:
        if row.min_down_payment is None:
            lines.append(
                f"{row.program.display_name:>12}  "
                f"{'n/a':>10}  "
                f"{'n/a':>12}  "
                f"{'n/a':>9}  "
                f"{'n/a':>9}  no"
            )
            continue
        check = row.check_at_min_down
        assert check is not None
        status = "yes" if check.passes else "no"
        lines.append(
            f"{row.program.display_name:>12}  "
            f"{row.min_down_payment_pct:>9.1%}  "
            f"${row.min_down_payment:>11,.0f}  "
            f"{check.front_end_dti:>8.1%}  "
            f"{check.back_end_dti:>8.1%}  "
            f"{status}"
        )
    return "\n".join(lines)
