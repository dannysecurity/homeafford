"""Abstract base class for market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import MarketSnapshot


class BaseMarketProvider(ABC):
    """Common provider contract with identity, capabilities, and snapshot lookup."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for logging, caching, and registry lookup."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return feature flags describing supported query dimensions."""
        return ProviderCapabilities()

    def list_metros(self) -> tuple[str, ...] | None:
        """Return supported metro IDs when metro pricing is available."""
        return None

    @abstractmethod
    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        """Return assumptions for the given query context."""


class DelegatingMarketProvider(BaseMarketProvider):
    """Base for wrapper providers that delegate identity metadata to an inner source."""

    @property
    def inner(self) -> MarketDataProvider:
        """Wrapped provider receiving delegated calls."""
        raise NotImplementedError(f"{type(self).__name__} must expose inner")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self.inner.capabilities

    def list_metros(self) -> tuple[str, ...] | None:
        return self.inner.list_metros()
