"""Fluent builder for composing market data provider stacks."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from homeafford.market.middleware import MiddlewareStack, build_fallback_stack
from homeafford.market.protocol import MarketDataProvider, validate_provider_contract
from homeafford.market.request import MarketOverrides


class ProviderBuilder:
    """Compose provider wrappers in a predictable order via middleware."""

    def __init__(self, base: MarketDataProvider | str) -> None:
        self._stack = MiddlewareStack(base)
        self._fallback_alternatives: list[MarketDataProvider] = []

    @property
    def provider(self) -> MarketDataProvider:
        """Current composed provider without further wrapping."""
        return self._stack.build()

    def with_term_adjustment(self) -> ProviderBuilder:
        """Wrap the stack with loan-term mortgage rate spreads."""
        self._stack.with_term_adjustment()
        return self

    def with_overrides(
        self,
        overrides: Mapping[str, float | str] | MarketOverrides,
    ) -> ProviderBuilder:
        """Wrap the stack with explicit field overrides applied after fetch."""
        self._stack.with_overrides(overrides)
        return self

    def cached(self, ttl: timedelta | None = None) -> ProviderBuilder:
        """Wrap the stack with snapshot caching."""
        self._stack.with_cache(ttl=ttl)
        return self

    def with_fallback(self, *others: MarketDataProvider | str) -> ProviderBuilder:
        """Try additional providers when the current stack fails."""
        for other in others:
            if isinstance(other, str):
                from homeafford.market.registry import get_provider

                provider = get_provider(other)
            else:
                validate_provider_contract(other)
                provider = other
            self._fallback_alternatives.append(provider)
        return self

    def build(self, *, cache: bool = False, ttl: timedelta | None = None) -> MarketDataProvider:
        """Return the composed provider, optionally adding a cache layer."""
        if cache:
            self._stack.with_cache(ttl=ttl)
        provider = self._stack.build()
        if self._fallback_alternatives:
            return build_fallback_stack(provider, *self._fallback_alternatives)
        return provider
