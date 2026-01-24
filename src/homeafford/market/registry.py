"""Factory for named market data providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeafford.market.composite import build_provider_stack
from homeafford.market.csv_metro import CsvMetroMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.static import StaticMarketProvider
from homeafford.market.term_adjusted import TermAdjustedMarketProvider

ProviderFactory = Callable[[], MarketDataProvider]


@dataclass(frozen=True)
class ProviderSpec:
    """Registry entry describing how to build a named provider."""

    factory: ProviderFactory
    description: str
    cache: bool = False


def _static_provider() -> MarketDataProvider:
    return StaticMarketProvider()


def _csv_metro_provider() -> MarketDataProvider:
    return CsvMetroMarketProvider()


def _term_adjusted_provider() -> MarketDataProvider:
    return TermAdjustedMarketProvider(StaticMarketProvider())


def _term_adjusted_metro_provider() -> MarketDataProvider:
    return TermAdjustedMarketProvider(CsvMetroMarketProvider())


def _instantiate_spec(spec: ProviderSpec) -> MarketDataProvider:
    """Build a provider from a registry spec, applying optional stack layers."""
    provider = spec.factory()
    if spec.cache:
        return build_provider_stack(provider)
    return provider


_REGISTRY: dict[str, ProviderSpec] = {
    "csv-metro": ProviderSpec(
        factory=_csv_metro_provider,
        description="Metro median home prices from bundled CSV trends",
        cache=True,
    ),
    "static": ProviderSpec(
        factory=_static_provider,
        description="Fixed default rates and housing cost assumptions",
    ),
    "term-adjusted": ProviderSpec(
        factory=_term_adjusted_provider,
        description="Static defaults with loan-term mortgage rate spreads",
    ),
    "term-adjusted-metro": ProviderSpec(
        factory=_term_adjusted_metro_provider,
        description="CSV metro pricing with term spreads and caching",
        cache=True,
    ),
}


def register_provider(
    name: str,
    factory: ProviderFactory,
    *,
    description: str = "",
    cache: bool = False,
) -> None:
    """Register a named provider factory."""
    if not name:
        raise ValueError("provider name must be non-empty")
    _REGISTRY[name] = ProviderSpec(factory=factory, description=description, cache=cache)


def available_providers() -> tuple[str, ...]:
    """Return registered provider names in sorted order."""
    return tuple(sorted(_REGISTRY))


def provider_descriptions() -> dict[str, str]:
    """Return human-readable descriptions for registered providers."""
    return {name: spec.description for name, spec in sorted(_REGISTRY.items())}


def format_provider_choices() -> str:
    """Format provider names and descriptions for CLI help text."""
    return "; ".join(
        f"{name} ({spec.description})" if spec.description else name
        for name, spec in sorted(_REGISTRY.items())
    )


def get_provider(name: str = "static") -> MarketDataProvider:
    """Instantiate a provider by registry name."""
    try:
        spec = _REGISTRY[name]
    except KeyError as exc:
        valid = ", ".join(available_providers())
        raise ValueError(f"unknown provider {name!r}; expected one of: {valid}") from exc
    return _instantiate_spec(spec)
