"""Built-in providers that do not fetch live market data."""

from __future__ import annotations

from homeafford.market.base import BaseMarketProvider
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot


class StaticMarketProvider(BaseMarketProvider):
    """Return a fixed snapshot, matching legacy hardcoded defaults."""

    def __init__(self, snapshot: MarketSnapshot = DEFAULT_MARKET) -> None:
        self._snapshot = snapshot

    @property
    def name(self) -> str:
        return "static"

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        return self._snapshot
