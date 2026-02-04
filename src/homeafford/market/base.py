"""Abstract base class for market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.errors import UnsupportedQueryError
from homeafford.market.planner import effective_query_for_capabilities, plan_query
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.snapshot import MarketSnapshot


def provider_name(provider: MarketDataProvider) -> str:
    """Return a provider's stable identifier, falling back to the class name."""
    return getattr(provider, "name", type(provider).__name__)


def provider_capabilities(provider: MarketDataProvider) -> ProviderCapabilities:
    """Return capability flags for any provider, including duck-typed sources."""
    return getattr(provider, "capabilities", ProviderCapabilities())


def provider_list_metros(provider: MarketDataProvider) -> tuple[str, ...] | None:
    """Return supported metro IDs when the provider exposes listing."""
    list_metros = getattr(provider, "list_metros", None)
    if list_metros is None:
        return None
    return list_metros()


def validate_provider_contract(provider: object) -> None:
    """Raise TypeError when an object does not satisfy MarketDataProvider."""
    if not isinstance(provider, MarketDataProvider):
        raise TypeError(
            f"{type(provider).__name__} does not implement MarketDataProvider"
        )


def validate_query_support(provider: MarketDataProvider, query: MarketQuery) -> None:
    """Raise when a provider cannot honor every set query dimension."""
    caps = provider_capabilities(provider)
    query_plan = plan_query(query, caps)
    if query_plan.has_dropped_fields:
        joined = ", ".join(query_plan.dropped_fields)
        raise UnsupportedQueryError(
            f"provider {provider_name(provider)!r} does not support query field(s): {joined}",
            provider_name=provider_name(provider),
            query=query,
            unsupported_fields=query_plan.dropped_fields,
        )


def query_for_capabilities(query: MarketQuery, caps: ProviderCapabilities) -> MarketQuery:
    """Return a query limited to dimensions the capabilities can honor."""
    return effective_query_for_capabilities(query, caps)


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

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        """Return assumptions for the given query context."""
        normalized = normalize_query(query)
        validate_query_support(self, normalized)
        return self._fetch_snapshot(query=normalized)

    @abstractmethod
    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        """Return a snapshot without re-validating query support."""


class DelegatingMarketProvider(BaseMarketProvider):
    """Base for wrapper providers that delegate identity metadata to an inner source."""

    @property
    def inner(self) -> MarketDataProvider:
        """Wrapped provider receiving delegated calls."""
        raise NotImplementedError(f"{type(self).__name__} must expose inner")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return provider_capabilities(self.inner)

    def list_metros(self) -> tuple[str, ...] | None:
        return provider_list_metros(self.inner)

    def _fetch_snapshot(self, *, query: MarketQuery) -> MarketSnapshot:
        inner_plan = plan_query(query, provider_capabilities(self.inner))
        return self.inner.get_snapshot(query=inner_plan.effective)
