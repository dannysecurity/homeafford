"""Two-dimensional down payment × income affordability frontier modeling."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.check import PurchaseScenario, _validate_scenario, check_affordability
from homeafford.dti_analysis import DEFAULT_INCOME_MULTIPLIERS, min_income_for_dti
from homeafford.dti_params import resolve_dti_params, scenario_at_down, scenario_at_income
from homeafford.dti_serialize import affordability_check_to_dict, dumps_dti_payload
from homeafford.model import (
    DEFAULT_DOWN_PAYMENT_PCTS,
    _validate_down_payment_pcts,
    min_down_payment_for_dti,
)


def _validate_income_multipliers(income_multipliers: tuple[float, ...]) -> None:
    if not income_multipliers:
        raise ValueError("income_multipliers must contain at least one multiplier")
    for mult in income_multipliers:
        if mult <= 0:
            raise ValueError(f"each income multiplier must be positive; got {mult!r}")


@dataclass(frozen=True)
class FrontierCell:
    """Affordability outcome at one down payment and income combination."""

    down_payment: float
    down_payment_pct: float
    gross_annual_income: float
    income_multiplier: float
    check: AffordabilityCheckResult
    passes_all: bool
    passes_dti: bool


@dataclass(frozen=True)
class AffordabilityFrontierResult:
    """Grid of down payment × income pairs and the affordability boundary."""

    home_price: float
    band_label: str | None
    base_income: float
    down_payment_pcts: tuple[float, ...]
    income_multipliers: tuple[float, ...]
    cells: tuple[FrontierCell, ...]
    min_down_at_base_income: float | None
    min_down_at_base_income_pct: float | None
    min_income_at_base_down: float | None
    min_income_at_base_down_multiplier: float | None
    boundary_cells: tuple[FrontierCell, ...]


def _cell_key(cell: FrontierCell) -> tuple[float, float]:
    return (cell.down_payment_pct, cell.income_multiplier)


def _extract_boundary_cells(
    cells: tuple[FrontierCell, ...],
    *,
    down_payment_pcts: tuple[float, ...],
    income_multipliers: tuple[float, ...],
) -> tuple[FrontierCell, ...]:
    """Return passing cells on the down × income tradeoff frontier."""
    by_key = {_cell_key(cell): cell for cell in cells}
    boundary: list[FrontierCell] = []

    for down_idx, down_pct in enumerate(down_payment_pcts):
        for income_idx, income_mult in enumerate(income_multipliers):
            cell = by_key.get((down_pct, income_mult))
            if cell is None or not cell.passes_all:
                continue

            lower_down_fails = True
            if down_idx > 0:
                lower_down = down_payment_pcts[down_idx - 1]
                neighbor = by_key.get((lower_down, income_mult))
                lower_down_fails = neighbor is None or not neighbor.passes_all

            lower_income_fails = True
            if income_idx > 0:
                lower_income = income_multipliers[income_idx - 1]
                neighbor = by_key.get((down_pct, lower_income))
                lower_income_fails = neighbor is None or not neighbor.passes_all

            if lower_down_fails or lower_income_fails:
                boundary.append(cell)

    return tuple(boundary)


def model_affordability_frontier(
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
) -> AffordabilityFrontierResult:
    """Evaluate affordability across a grid of down payment and income levels.

    Returns pass/fail outcomes for each (down, income) pair plus solver-derived
    minimums at the scenario's base income and down payment.
    """
    _validate_scenario(scenario)
    _validate_down_payment_pcts(down_payment_pcts)
    _validate_income_multipliers(income_multipliers)

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

    base_income = scenario.gross_annual_income
    cells: list[FrontierCell] = []

    for down_pct in down_payment_pcts:
        down = scenario.home_price * down_pct
        for income_mult in income_multipliers:
            income = base_income * income_mult
            sub = scenario_at_down(scenario_at_income(scenario, income), down)
            check = check_affordability(
                sub,
                front_end_cap=front_end_cap,
                back_end_cap=back_end_cap,
                min_down_payment_pct=min_down_payment_pct,
                pmi_annual_rate=pmi_annual_rate,
                pmi_ltv_threshold=pmi_ltv_threshold,
                mortgage_insurance_always=mortgage_insurance_always,
                band_label=band_label,
            )
            cells.append(
                FrontierCell(
                    down_payment=down,
                    down_payment_pct=down_pct,
                    gross_annual_income=income,
                    income_multiplier=income_mult,
                    check=check,
                    passes_all=check.passes,
                    passes_dti=check.passes_front_end and check.passes_back_end,
                )
            )

    cell_tuple = tuple(cells)
    boundary = _extract_boundary_cells(
        cell_tuple,
        down_payment_pcts=down_payment_pcts,
        income_multipliers=income_multipliers,
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

    min_income = min_income_for_dti(
        scenario,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        pmi_annual_rate=pmi_annual_rate,
        pmi_ltv_threshold=pmi_ltv_threshold,
        mortgage_insurance_always=mortgage_insurance_always,
        loan_program=loan_program,
        band_label=band_label,
    )
    min_income_mult = (
        min_income / base_income if min_income is not None and base_income > 0 else None
    )

    return AffordabilityFrontierResult(
        home_price=scenario.home_price,
        band_label=band_label,
        base_income=base_income,
        down_payment_pcts=down_payment_pcts,
        income_multipliers=income_multipliers,
        cells=cell_tuple,
        min_down_at_base_income=min_down,
        min_down_at_base_income_pct=min_down_pct,
        min_income_at_base_down=min_income,
        min_income_at_base_down_multiplier=min_income_mult,
        boundary_cells=boundary,
    )


def format_affordability_frontier(result: AffordabilityFrontierResult) -> str:
    """Render a down × income pass/fail grid for CLI or logging."""
    band = result.band_label or "custom"
    lines = [
        (
            f"Down × income affordability frontier "
            f"(${result.home_price:,.0f} home, {band} band)"
        ),
        f"Base income: ${result.base_income:,.0f}",
    ]

    if result.min_down_at_base_income is not None:
        lines.append(
            f"Minimum down at base income: ${result.min_down_at_base_income:,.0f} "
            f"({result.min_down_at_base_income_pct:.1%})"
        )
    else:
        lines.append("Minimum down at base income: not reachable")

    if result.min_income_at_base_down is not None:
        mult_str = (
            f" ({result.min_income_at_base_down_multiplier:.2f}x base)"
            if result.min_income_at_base_down_multiplier is not None
            else ""
        )
        lines.append(
            f"Minimum income at base down: "
            f"${result.min_income_at_base_down:,.0f}{mult_str}"
        )

    header = f"{'Down %':>7}  " + "  ".join(
        f"{mult:>6.2f}x" for mult in result.income_multipliers
    )
    lines.append(header)

    by_key = {_cell_key(cell): cell for cell in result.cells}
    for down_pct in result.down_payment_pcts:
        row_cells = [
            by_key[(down_pct, mult)] for mult in result.income_multipliers
        ]
        statuses = []
        for cell in row_cells:
            if cell.passes_all:
                statuses.append("  yes ")
            elif cell.passes_dti:
                statuses.append(" dti  ")
            else:
                statuses.append("  no  ")
        lines.append(f"{down_pct:>6.1%}  " + "  ".join(statuses))

    if result.boundary_cells:
        lines.append("")
        lines.append("Affordability boundary (minimum down/income pairs that pass):")
        for cell in sorted(
            result.boundary_cells,
            key=lambda c: (c.down_payment_pct, c.income_multiplier),
        ):
            lines.append(
                f"  {cell.down_payment_pct:.1%} down, "
                f"${cell.gross_annual_income:,.0f} income "
                f"({cell.income_multiplier:.2f}x)"
            )

    return "\n".join(lines)


def _frontier_cell_to_dict(cell: FrontierCell) -> dict[str, object]:
    return {
        "down_payment": cell.down_payment,
        "down_payment_pct": cell.down_payment_pct,
        "gross_annual_income": cell.gross_annual_income,
        "income_multiplier": cell.income_multiplier,
        "passes_all": cell.passes_all,
        "passes_dti": cell.passes_dti,
        "check": affordability_check_to_dict(cell.check),
    }


def format_affordability_frontier_json(result: AffordabilityFrontierResult) -> str:
    """Serialize an affordability frontier grid as JSON for scripting."""
    payload: dict[str, object] = {
        "home_price": result.home_price,
        "band_label": result.band_label,
        "base_income": result.base_income,
        "down_payment_pcts": list(result.down_payment_pcts),
        "income_multipliers": list(result.income_multipliers),
        "min_down_at_base_income": result.min_down_at_base_income,
        "min_down_at_base_income_pct": result.min_down_at_base_income_pct,
        "min_income_at_base_down": result.min_income_at_base_down,
        "min_income_at_base_down_multiplier": result.min_income_at_base_down_multiplier,
        "cells": [_frontier_cell_to_dict(cell) for cell in result.cells],
        "boundary_cells": [_frontier_cell_to_dict(cell) for cell in result.boundary_cells],
    }
    return dumps_dti_payload(payload)
