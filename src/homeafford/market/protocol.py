"""Provider interface for resolving market assumptions."""

from __future__ import annotations

from typing import Protocol

from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import MarketSnapshot


class MarketDataProvider(Protocol):
    """Source of market assumptions for affordability calculations."""

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        """Return assumptions for the given query context."""
        ...
