"""Resolution results with query-plan metadata."""

from __future__ import annotations

from dataclasses import dataclass

from homeafford.market.planner import QueryPlan
from homeafford.market.snapshot import MarketSnapshot


@dataclass(frozen=True)
class ResolvedMarket:
    """Market snapshot plus metadata about how the provider resolved the query."""

    snapshot: MarketSnapshot
    plan: QueryPlan
    provider: str
    overrides_applied: bool = False

    @property
    def has_degraded_query(self) -> bool:
        """Return True when unsupported query dimensions were dropped."""
        return self.plan.has_dropped_fields

    @property
    def is_fully_supported(self) -> bool:
        """Return True when every requested query dimension was honored."""
        return self.plan.is_fully_supported
