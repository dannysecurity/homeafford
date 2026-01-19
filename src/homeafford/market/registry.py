"""Factory for named market data providers."""

from __future__ import annotations

from collections.abc import Callable

from homeafford.market.csv_metro import csv_metro_provider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.static import StaticMarketProvider

ProviderFactory = Callable[[], MarketDataProvider]

_REGISTRY: dict[str, ProviderFactory] = {
    "csv-metro": csv_metro_provider,
    "static": StaticMarketProvider,
}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a named provider factory."""
    if not name:
        raise ValueError("provider name must be non-empty")
    _REGISTRY[name] = factory


def available_providers() -> tuple[str, ...]:
    """Return registered provider names in sorted order."""
    return tuple(sorted(_REGISTRY))


def get_provider(name: str = "static") -> MarketDataProvider:
    """Instantiate a provider by registry name."""
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        valid = ", ".join(available_providers())
        raise ValueError(f"unknown provider {name!r}; expected one of: {valid}") from exc
    return factory()
