"""Abstract base class for market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.errors import MarketDataUnavailable
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import DEFAULT_QUERY, MarketQuery, normalize_query
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
    unsupported = caps.unsupported_query_fields(query)
    if unsupported:
        joined = ", ".join(unsupported)
        raise MarketDataUnavailable(
            f"provider {provider_name(provider)!r} does not support query field(s): {joined}"
        )


def query_for_capabilities(query: MarketQuery, caps: ProviderCapabilities) -> MarketQuery:
    """Return a query limited to dimensions the capabilities can honor."""
    return MarketQuery(
        loan_term_years=query.loan_term_years if caps.supports_term_rates else DEFAULT_QUERY.loan_term_years,
        metro_id=query.metro_id if caps.supports_metro_pricing else None,
        reference_year=query.reference_year if caps.supports_reference_year else None,
    )


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
        inner_query = query_for_capabilities(query, provider_capabilities(self.inner))
        return self.inner.get_snapshot(query=inner_query)
