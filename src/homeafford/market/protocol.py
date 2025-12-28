"""Provider interface for resolving market assumptions."""

from __future__ import annotations

from typing import Protocol

from homeafford.market.snapshot import MarketSnapshot


class MarketDataProvider(Protocol):
    """Source of market assumptions for affordability calculations."""

    def get_snapshot(self, *, loan_term_years: int = 30) -> MarketSnapshot:
        """Return assumptions for the given loan term."""
        ...
