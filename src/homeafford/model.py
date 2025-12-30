"""Down payment and DTI affordability modeling for a fixed home price."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseScenario,
    _band_caps,
    _validate_scenario,
    check_affordability,
    check_purchase_readiness,
)

DEFAULT_DOWN_PAYMENT_PCTS: tuple[float, ...] = (0.03, 0.05, 0.10, 0.15, 0.20)


@dataclass(frozen=True)
class DownPaymentScenarioRow:
    """DTI and affordability outcome at one down payment level."""

    down_payment: float
    down_payment_pct: float
    check: AffordabilityCheckResult


@dataclass(frozen=True)
class DownPaymentDtiModelResult:
    """Sweep of down payment levels against DTI caps for a fixed home price."""

    home_price: float
    band_label: str | None
    rows: tuple[DownPaymentScenarioRow, ...]
    min_down_payment: float | None
    min_down_payment_pct: float | None


def _scenario_at_down(scenario: PurchaseScenario, down_payment: float) -> PurchaseScenario:
    return replace(scenario, down_payment=down_payment)


def _passes_dti(
    scenario: PurchaseScenario,
    *,
    down_payment: float,
    front_end_cap: float,
    back_end_cap: float,
) -> bool:
    result = check_affordability(
        _scenario_at_down(scenario, down_payment),
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=0.0,
    )
    return result.passes_front_end and result.passes_back_end


def min_down_payment_for_dti(
    scenario: PurchaseScenario,
    *,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    band_label: str | None = None,
    tolerance: float = 1.0,
) -> float | None:
    """Return the least down payment (dollars) that passes DTI caps, or None if unreachable.

    The search starts at ``home_price * min_down_payment_pct`` and assumes higher down
    payments monotonically improve DTI. Returns ``None`` when debt alone exceeds the
    back-end cap (no down payment can fix housing-independent debt load).
    """
    _validate_scenario(scenario)
    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    floor = scenario.home_price * min_down_payment_pct
    ceiling = scenario.home_price

    if not _passes_dti(
        scenario,
        down_payment=ceiling,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
    ):
        return None

    if _passes_dti(
        scenario,
        down_payment=floor,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
    ):
        return floor

    low, high = floor, ceiling
    while high - low > tolerance:
        mid = (low + high) / 2
        if _passes_dti(
            scenario,
            down_payment=mid,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
        ):
            high = mid
        else:
            low = mid
    return high


def model_down_payment_dti(
    scenario: PurchaseScenario,
    *,
    down_payment_pcts: tuple[float, ...] = DEFAULT_DOWN_PAYMENT_PCTS,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    band_label: str | None = None,
) -> DownPaymentDtiModelResult:
    """Evaluate DTI affordability at several down payment levels for a fixed home price.

    Returns a table of pass/fail outcomes plus the minimum down payment that satisfies
    the DTI caps (respecting ``min_down_payment_pct`` as a floor).
    """
    _validate_scenario(scenario)
    if band_label is not None:
        front_end_cap, back_end_cap = _band_caps(band_label)

    rows: list[DownPaymentScenarioRow] = []
    for pct in down_payment_pcts:
        down = scenario.home_price * pct
        sub = _scenario_at_down(scenario, down)
        check = check_affordability(
            sub,
            front_end_cap=front_end_cap,
            back_end_cap=back_end_cap,
            min_down_payment_pct=min_down_payment_pct,
            band_label=band_label,
        )
        rows.append(
            DownPaymentScenarioRow(
                down_payment=down,
                down_payment_pct=pct,
                check=check,
            )
        )

    min_down = min_down_payment_for_dti(
        scenario,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
    )
    min_pct = min_down / scenario.home_price if min_down is not None else None

    return DownPaymentDtiModelResult(
        home_price=scenario.home_price,
        band_label=band_label,
        rows=tuple(rows),
        min_down_payment=min_down,
        min_down_payment_pct=min_pct,
    )


@dataclass(frozen=True)
class PurchaseAffordabilityPlan:
    """DTI down-payment model combined with a savings readiness timeline."""

    home_price: float
    band_label: str | None
    dti_model: DownPaymentDtiModelResult
    min_down_payment: float | None
    min_down_payment_pct: float | None
    cash_required: float | None
    passes_dti_at_min_down: bool
    passes_savings: bool
    months_until_ready: int | None
    projected_balance: float | None
    ready_to_buy: bool
    affordability_at_min_down: AffordabilityCheckResult | None


def plan_purchase_affordability(
    scenario: PurchaseScenario,
    *,
    starting_balance: float,
    monthly_contribution: float,
    annual_return: float = 0.04,
    target_months: int | None = None,
    front_end_cap: float = 0.28,
    back_end_cap: float = 0.36,
    min_down_payment_pct: float = 0.03,
    band_label: str | None = None,
    down_payment_pcts: tuple[float, ...] = DEFAULT_DOWN_PAYMENT_PCTS,
) -> PurchaseAffordabilityPlan:
    """Build a purchase plan: DTI minimum down payment plus savings timeline.

    Sweeps common down payment levels, finds the least down that passes DTI caps,
    then projects whether savings can cover that down payment (plus closing costs)
    by a target date or reports months until ready.
    """
    _validate_scenario(scenario)
    if starting_balance < 0 or monthly_contribution < 0:
        raise ValueError("starting_balance and monthly_contribution must be non-negative")
    if target_months is not None and target_months < 0:
        raise ValueError("target_months must be non-negative")

    dti_model = model_down_payment_dti(
        scenario,
        down_payment_pcts=down_payment_pcts,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        band_label=band_label,
    )
    min_down = dti_model.min_down_payment
    min_pct = dti_model.min_down_payment_pct

    if min_down is None:
        return PurchaseAffordabilityPlan(
            home_price=scenario.home_price,
            band_label=band_label,
            dti_model=dti_model,
            min_down_payment=None,
            min_down_payment_pct=None,
            cash_required=None,
            passes_dti_at_min_down=False,
            passes_savings=False,
            months_until_ready=None,
            projected_balance=None,
            ready_to_buy=False,
            affordability_at_min_down=None,
        )

    scenario_at_min = _scenario_at_down(scenario, min_down)
    readiness = check_purchase_readiness(
        scenario_at_min,
        starting_balance=starting_balance,
        monthly_contribution=monthly_contribution,
        annual_return=annual_return,
        target_months=target_months,
        front_end_cap=front_end_cap,
        back_end_cap=back_end_cap,
        min_down_payment_pct=min_down_payment_pct,
        band_label=band_label,
    )

    return PurchaseAffordabilityPlan(
        home_price=scenario.home_price,
        band_label=band_label,
        dti_model=dti_model,
        min_down_payment=min_down,
        min_down_payment_pct=min_pct,
        cash_required=readiness.cash_required,
        passes_dti_at_min_down=readiness.passes_dti,
        passes_savings=readiness.passes_savings,
        months_until_ready=readiness.months_until_ready,
        projected_balance=readiness.projected_balance,
        ready_to_buy=readiness.passes,
        affordability_at_min_down=readiness.affordability,
    )


def format_down_payment_dti_model(result: DownPaymentDtiModelResult) -> str:
    """Render a down payment sweep table for CLI or logging."""
    band = result.band_label or "custom"
    lines = [
        f"Down payment vs DTI model (${result.home_price:,.0f} home, {band} band)",
    ]
    if result.min_down_payment is not None:
        lines.append(
            f"Minimum down for DTI pass: ${result.min_down_payment:,.0f} "
            f"({result.min_down_payment_pct:.1%})"
        )
    else:
        lines.append("Minimum down for DTI pass: not reachable (debt exceeds back-end cap)")
    lines.append(f"{'Down %':>7}  {'Down $':>12}  {'PITI':>10}  {'Front':>7}  {'Back':>7}  Pass")
    for row in result.rows:
        status = "yes" if row.check.passes else "no"
        lines.append(
            f"{row.down_payment_pct:>6.1%}  "
            f"${row.down_payment:>11,.0f}  "
            f"${row.check.estimated_piti:>9,.0f}  "
            f"{row.check.front_end_dti:>6.1%}  "
            f"{row.check.back_end_dti:>6.1%}  "
            f"{status}"
        )
    return "\n".join(lines)


def format_purchase_affordability_plan(plan: PurchaseAffordabilityPlan) -> str:
    """Render a combined DTI model and savings readiness summary."""
    lines = [format_down_payment_dti_model(plan.dti_model), ""]
    if plan.min_down_payment is None:
        lines.append("Purchase plan: DTI caps cannot be met at any down payment level.")
        return "\n".join(lines)

    lines.append("Purchase readiness (at minimum DTI down payment):")
    lines.append(f"  Cash required: ${plan.cash_required:,.0f}")
    lines.append(f"  DTI at min down: {'PASS' if plan.passes_dti_at_min_down else 'FAIL'}")
    lines.append(f"  Savings: {'PASS' if plan.passes_savings else 'FAIL'}")
    if plan.projected_balance is not None:
        lines.append(f"  Projected balance: ${plan.projected_balance:,.0f}")
    if plan.months_until_ready is not None:
        lines.append(f"  Months until down payment saved: {plan.months_until_ready}")
    lines.append(f"  Ready to buy: {'YES' if plan.ready_to_buy else 'NO'}")
    return "\n".join(lines)
