"""Built-in providers that do not fetch live market data."""

from __future__ import annotations

from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot


class StaticMarketProvider:
    """Return a fixed snapshot, matching legacy hardcoded defaults."""

    def __init__(self, snapshot: MarketSnapshot = DEFAULT_MARKET) -> None:
        self._snapshot = snapshot

    def get_snapshot(self, *, loan_term_years: int = 30) -> MarketSnapshot:
        return self._snapshot
