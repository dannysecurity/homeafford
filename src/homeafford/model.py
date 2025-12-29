"""Down payment and DTI affordability modeling for a fixed home price."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeafford.check import (
    AffordabilityCheckResult,
    PurchaseScenario,
    _band_caps,
    _validate_scenario,
    check_affordability,
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
