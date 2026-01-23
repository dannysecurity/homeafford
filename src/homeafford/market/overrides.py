"""Providers that layer user overrides on top of another source."""

from __future__ import annotations

from collections.abc import Mapping

from homeafford.market.base import DelegatingMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.request import MarketOverrides
from homeafford.market.snapshot import MarketSnapshot


class OverrideMarketProvider(DelegatingMarketProvider):
    """Apply explicit field overrides after delegating to a base provider."""

    def __init__(
        self,
        inner: MarketDataProvider,
        overrides: Mapping[str, float | str] | MarketOverrides,
    ) -> None:
        self._inner = inner
        if isinstance(overrides, MarketOverrides):
            self._overrides = overrides
        else:
            self._overrides = MarketOverrides.from_mapping(overrides)

    @property
    def inner(self) -> MarketDataProvider:
        return self._inner

    @property
    def name(self) -> str:
        return f"override:{self.inner.name}"

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        normalized = normalize_query(query)
        snapshot = self.inner.get_snapshot(query=normalized)
        return self._overrides.apply_to(snapshot)
