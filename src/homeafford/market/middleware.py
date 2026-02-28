"""Composable middleware pipeline for market data providers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

from homeafford.market.cache import SnapshotCache
from homeafford.market.composite import CachedMarketProvider, FallbackMarketProvider
from homeafford.market.overrides import OverrideMarketProvider
from homeafford.market.protocol import MarketDataProvider, validate_provider_contract
from homeafford.market.request import MarketOverrides
from homeafford.market.term_adjusted import TermAdjustedMarketProvider

__all__ = [
    "CacheMiddleware",
    "MiddlewareStack",
    "OverrideMiddleware",
    "ProviderMiddleware",
    "TermAdjustmentMiddleware",
    "apply_middleware_stack",
    "build_fallback_stack",
    "cache_middleware",
    "override_middleware",
    "term_adjustment_middleware",
]


@runtime_checkable
class ProviderMiddleware(Protocol):
    """Composable layer that wraps a :class:`MarketDataProvider`."""

    @property
    def label(self) -> str:
        """Short identifier used when composing provider names."""
        ...

    def wrap(self, inner: MarketDataProvider) -> MarketDataProvider:
        """Return *inner* transformed by this middleware layer."""
        ...


@dataclass(frozen=True)
class CacheMiddleware:
    """Cache snapshots from an inner provider."""

    ttl: timedelta | None = None
    cache: SnapshotCache | None = None

    @property
    def label(self) -> str:
        return "cached"

    def wrap(self, inner: MarketDataProvider) -> MarketDataProvider:
        if self.cache is not None:
            return CachedMarketProvider(inner, cache=self.cache)
        if self.ttl is not None:
            return CachedMarketProvider(inner, ttl=self.ttl)
        return CachedMarketProvider(inner)


@dataclass(frozen=True)
class TermAdjustmentMiddleware:
    """Apply loan-term mortgage rate spreads on top of an inner provider."""

    term_spreads: dict[int, float] | None = None

    @property
    def label(self) -> str:
        return "term-adjusted"

    def wrap(self, inner: MarketDataProvider) -> MarketDataProvider:
        return TermAdjustedMarketProvider(inner, term_spreads=self.term_spreads)


@dataclass(frozen=True)
class OverrideMiddleware:
    """Apply explicit field overrides after an inner provider fetch."""

    overrides: Mapping[str, float | str] | MarketOverrides

    @property
    def label(self) -> str:
        return "override"

    def wrap(self, inner: MarketDataProvider) -> MarketDataProvider:
        return OverrideMarketProvider(inner, self.overrides)


def cache_middleware(
    *,
    ttl: timedelta | None = None,
    cache: SnapshotCache | None = None,
) -> CacheMiddleware:
    """Return middleware that caches snapshots from the wrapped provider."""
    return CacheMiddleware(ttl=ttl, cache=cache)


def term_adjustment_middleware(
    *,
    term_spreads: dict[int, float] | None = None,
) -> TermAdjustmentMiddleware:
    """Return middleware that applies loan-term mortgage rate spreads."""
    return TermAdjustmentMiddleware(term_spreads=term_spreads)


def override_middleware(
    overrides: Mapping[str, float | str] | MarketOverrides,
) -> OverrideMiddleware:
    """Return middleware that applies explicit field overrides after fetch."""
    return OverrideMiddleware(overrides=overrides)


def apply_middleware_stack(
    base: MarketDataProvider,
    middleware: tuple[ProviderMiddleware, ...],
) -> MarketDataProvider:
    """Apply middleware layers in order, innermost to outermost."""
    provider = base
    for layer in middleware:
        provider = layer.wrap(provider)
    return provider


def build_fallback_stack(
    primary: MarketDataProvider,
    *alternatives: MarketDataProvider,
) -> MarketDataProvider:
    """Combine providers into a fallback chain, trying *primary* first."""
    if not alternatives:
        return primary
    return FallbackMarketProvider([primary, *alternatives])


class MiddlewareStack:
    """Build a provider by applying middleware layers in registration order."""

    def __init__(self, base: MarketDataProvider | str) -> None:
        if isinstance(base, str):
            from homeafford.market.registry import get_provider

            provider = get_provider(base)
        else:
            provider = base
        validate_provider_contract(provider)
        self._base = provider
        self._middleware: list[ProviderMiddleware] = []

    @property
    def base(self) -> MarketDataProvider:
        """Unwrapped provider at the center of the stack."""
        return self._base

    @property
    def middleware(self) -> tuple[ProviderMiddleware, ...]:
        """Registered middleware layers in application order."""
        return tuple(self._middleware)

    def use(self, middleware: ProviderMiddleware) -> MiddlewareStack:
        """Register one middleware layer and return self for chaining."""
        self._middleware.append(middleware)
        return self

    def with_cache(
        self,
        ttl: timedelta | None = None,
        *,
        cache: SnapshotCache | None = None,
    ) -> MiddlewareStack:
        """Register snapshot caching middleware."""
        return self.use(cache_middleware(ttl=ttl, cache=cache))

    def with_term_adjustment(
        self,
        *,
        term_spreads: dict[int, float] | None = None,
    ) -> MiddlewareStack:
        """Register loan-term mortgage rate spread middleware."""
        return self.use(term_adjustment_middleware(term_spreads=term_spreads))

    def with_overrides(
        self,
        overrides: Mapping[str, float | str] | MarketOverrides,
    ) -> MiddlewareStack:
        """Register field override middleware."""
        return self.use(override_middleware(overrides))

    def build(self) -> MarketDataProvider:
        """Return the composed provider with all registered middleware applied."""
        return apply_middleware_stack(self._base, self.middleware)
