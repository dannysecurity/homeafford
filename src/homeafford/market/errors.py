"""Shared exceptions for market data providers."""


class MarketDataError(Exception):
    """Base error for market provider failures."""


class MarketDataUnavailable(MarketDataError):
    """Raised when a provider cannot supply market data for a query."""
