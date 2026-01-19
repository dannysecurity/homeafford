"""Immutable market assumption snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class MarketSnapshot:
    """Point-in-time housing and investment assumptions used by calculators."""

    mortgage_rate: float
    property_tax_rate: float
    insurance_annual: float
    savings_annual_return: float = 0.04
    pmi_annual_rate: float = 0.005
    pmi_ltv_threshold: float = 0.80
    metro_id: str | None = None
    metro_name: str | None = None
    median_home_price: float | None = None
    source: str = "static"

    def with_overrides(self, **overrides: float | str) -> MarketSnapshot:
        """Return a copy with selected fields replaced."""
        return replace(self, **overrides)


DEFAULT_MARKET = MarketSnapshot(
    mortgage_rate=0.065,
    property_tax_rate=0.012,
    insurance_annual=1_200.0,
    savings_annual_return=0.04,
    source="static",
)
