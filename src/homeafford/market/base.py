"""Abstract base class for market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.errors import UnsupportedQueryError
from homeafford.market.planner import (
    QueryPlan,
    QueryPolicy,
    effective_query_for_capabilities,
    plan_query,
)
from homeafford.market.protocol import (
    MarketDataProvider,
    provider_capabilities,
    provider_list_metros,
    provider_name,
)
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.snapshot import MarketSnapshot


def prepare_provider_query(
    provider: MarketDataProvider,
    query: MarketQuery | None,
    *,
    policy: QueryPolicy = QueryPolicy.STRICT,
) -> tuple[MarketQuery, QueryPlan]:
    """Normalize a query and plan it against provider capabilities."""
    normalized = normalize_query(query)
    query_plan = plan_query(normalized, provider_capabilities(provider))
    if policy == QueryPolicy.STRICT and query_plan.has_dropped_fields:
        joined = ", ".join(query_plan.dropped_fields)
        raise UnsupportedQueryError(
            f"provider {provider_name(provider)!r} does not support query field(s): {joined}",
            provider_name=provider_name(provider),
            query=normalized,
            unsupported_fields=query_plan.dropped_fields,
        )
    if policy == QueryPolicy.DEGRADE:
        return query_plan.effective, query_plan
    return normalized, query_plan


def validate_query_support(provider: MarketDataProvider, query: MarketQuery) -> None:
    """Raise when a provider cannot honor every set query dimension."""
    prepare_provider_query(provider, query, policy=QueryPolicy.STRICT)


def fetch_provider_snapshot(
    provider: MarketDataProvider,
    query: MarketQuery | None = None,
    *,
    policy: QueryPolicy = QueryPolicy.STRICT,
) -> MarketSnapshot:
    """Fetch a snapshot with consistent query normalization and policy handling."""
    query_to_use, _ = prepare_provider_query(provider, query, policy=policy)
    return provider.get_snapshot(query=query_to_use)


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
        normalized, _ = prepare_provider_query(self, query, policy=QueryPolicy.STRICT)
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
        return fetch_provider_snapshot(self.inner, query, policy=QueryPolicy.DEGRADE)
