"""Fluent builder for composing market data provider stacks."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from homeafford.market.base import validate_provider_contract
from homeafford.market.composite import CachedMarketProvider, FallbackMarketProvider, build_provider_stack
from homeafford.market.overrides import OverrideMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.request import MarketOverrides
from homeafford.market.term_adjusted import TermAdjustedMarketProvider


class ProviderBuilder:
    """Compose provider wrappers in a predictable order."""

    def __init__(self, base: MarketDataProvider | str) -> None:
        if isinstance(base, str):
            from homeafford.market.registry import get_provider

            provider = get_provider(base)
        else:
            provider = base
        validate_provider_contract(provider)
        self._provider = provider

    @property
    def provider(self) -> MarketDataProvider:
        """Current composed provider without further wrapping."""
        return self._provider

    def with_term_adjustment(self) -> ProviderBuilder:
        """Wrap the stack with loan-term mortgage rate spreads."""
        self._provider = TermAdjustedMarketProvider(self._provider)
        return self

    def with_overrides(
        self,
        overrides: Mapping[str, float | str] | MarketOverrides,
    ) -> ProviderBuilder:
        """Wrap the stack with explicit field overrides applied after fetch."""
        self._provider = OverrideMarketProvider(self._provider, overrides)
        return self

    def cached(self, ttl: timedelta | None = None) -> ProviderBuilder:
        """Wrap the stack with snapshot caching."""
        if ttl is None:
            self._provider = CachedMarketProvider(self._provider)
        else:
            self._provider = CachedMarketProvider(self._provider, ttl=ttl)
        return self

    def with_fallback(self, *others: MarketDataProvider | str) -> ProviderBuilder:
        """Try additional providers when the current stack fails."""
        providers: list[MarketDataProvider] = [self._provider]
        for other in others:
            if isinstance(other, str):
                from homeafford.market.registry import get_provider

                providers.append(get_provider(other))
            else:
                validate_provider_contract(other)
                providers.append(other)
        self._provider = FallbackMarketProvider(providers)
        return self

    def build(self, *, cache: bool = False, ttl: timedelta | None = None) -> MarketDataProvider:
        """Return the composed provider, optionally adding a cache layer."""
        if cache:
            return build_provider_stack(self._provider, ttl=ttl)
        return self._provider
