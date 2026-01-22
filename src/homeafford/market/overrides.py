"""Providers that layer user overrides on top of another source."""

from __future__ import annotations

from collections.abc import Mapping

from homeafford.market.base import BaseMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.request import MarketOverrides
from homeafford.market.snapshot import MarketSnapshot


class OverrideMarketProvider(BaseMarketProvider):
    """Apply explicit field overrides after delegating to a base provider."""

    def __init__(
        self,
        base: MarketDataProvider,
        overrides: Mapping[str, float | str] | MarketOverrides,
    ) -> None:
        self._base = base
        if isinstance(overrides, MarketOverrides):
            self._overrides = overrides
        else:
            self._overrides = MarketOverrides.from_mapping(overrides)

    @property
    def name(self) -> str:
        return f"override:{self._base.name}"

    @property
    def capabilities(self):
        return self._base.capabilities

    def list_metros(self) -> tuple[str, ...] | None:
        return self._base.list_metros()

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        normalized = normalize_query(query)
        snapshot = self._base.get_snapshot(query=normalized)
        return self._overrides.apply_to(snapshot)
