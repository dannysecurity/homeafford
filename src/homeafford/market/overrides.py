"""Providers that layer user overrides on top of another source."""

from __future__ import annotations

from collections.abc import Mapping

from homeafford.market.protocol import MarketDataProvider
from homeafford.market.snapshot import MarketSnapshot


class OverrideMarketProvider:
    """Apply explicit field overrides after delegating to a base provider."""

    def __init__(
        self,
        base: MarketDataProvider,
        overrides: Mapping[str, float | str],
    ) -> None:
        self._base = base
        self._overrides = dict(overrides)

    def get_snapshot(self, *, loan_term_years: int = 30) -> MarketSnapshot:
        snapshot = self._base.get_snapshot(loan_term_years=loan_term_years)
        return snapshot.with_overrides(**self._overrides)
