"""Shared exceptions for market data providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeafford.market.query import MarketQuery


class MarketDataError(Exception):
    """Base error for market provider failures."""


class MarketDataUnavailable(MarketDataError):
    """Raised when a provider cannot supply market data for a query."""


class UnsupportedQueryError(MarketDataUnavailable):
    """Raised when a provider cannot honor every set query dimension."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        query: MarketQuery | None = None,
        unsupported_fields: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.query = query
        self.unsupported_fields = unsupported_fields
