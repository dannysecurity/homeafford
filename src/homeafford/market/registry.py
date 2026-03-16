"""Factory for named market data providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeafford.market.assembler import (
    assembled_csv_metro_provider,
    assembled_term_adjusted_metro_provider,
)
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.composite import build_provider_stack
from homeafford.market.errors import UnsupportedQueryError
from homeafford.market.planner import plan_query
from homeafford.market.protocol import (
    MarketDataProvider,
    introspect_provider_capabilities,
    provider_capabilities,
)
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.static import StaticMarketProvider
from homeafford.market.term_adjusted import TermAdjustedMarketProvider

ProviderFactory = Callable[[], MarketDataProvider]


@dataclass(frozen=True)
class ProviderSpec:
    """Registry entry describing how to build a named provider."""

    factory: ProviderFactory
    description: str
    cache: bool = False
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)


def _static_provider() -> MarketDataProvider:
    return StaticMarketProvider()


def _csv_metro_provider() -> MarketDataProvider:
    return assembled_csv_metro_provider(name="csv-metro")


def _term_adjusted_provider() -> MarketDataProvider:
    return TermAdjustedMarketProvider(StaticMarketProvider())


def _term_adjusted_metro_provider() -> MarketDataProvider:
    return assembled_term_adjusted_metro_provider(name="term-adjusted-metro")


def _make_spec(
    factory: ProviderFactory,
    *,
    description: str,
    cache: bool = False,
    capabilities: ProviderCapabilities | None = None,
) -> ProviderSpec:
    """Build a registry spec with capabilities derived from the live provider."""
    return ProviderSpec(
        factory=factory,
        description=description,
        cache=cache,
        capabilities=capabilities or introspect_provider_capabilities(factory),
    )


def _instantiate_spec(spec: ProviderSpec) -> MarketDataProvider:
    """Build a provider from a registry spec, applying optional stack layers."""
    provider = spec.factory()
    if spec.cache:
        return build_provider_stack(provider)
    return provider


_REGISTRY: dict[str, ProviderSpec] = {
    "csv-metro": _make_spec(
        factory=_csv_metro_provider,
        description="Metro median home prices from bundled CSV trends",
        cache=True,
    ),
    "static": _make_spec(
        factory=_static_provider,
        description="Fixed default rates and housing cost assumptions",
    ),
    "term-adjusted": _make_spec(
        factory=_term_adjusted_provider,
        description="Static defaults with loan-term mortgage rate spreads",
    ),
    "term-adjusted-metro": _make_spec(
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
    capabilities: ProviderCapabilities | None = None,
) -> None:
    """Register a named provider factory."""
    if not name:
        raise ValueError("provider name must be non-empty")
    _REGISTRY[name] = _make_spec(
        factory=factory,
        description=description,
        cache=cache,
        capabilities=capabilities,
    )


def available_providers() -> tuple[str, ...]:
    """Return registered provider names in sorted order."""
    return tuple(sorted(_REGISTRY))


def provider_descriptions() -> dict[str, str]:
    """Return human-readable descriptions for registered providers."""
    return {name: spec.description for name, spec in sorted(_REGISTRY.items())}


def provider_capabilities_for(name: str) -> ProviderCapabilities:
    """Return declared capabilities for a registered provider name."""
    try:
        return _REGISTRY[name].capabilities
    except KeyError as exc:
        valid = ", ".join(available_providers())
        raise ValueError(f"unknown provider {name!r}; expected one of: {valid}") from exc


def validate_registry_capabilities() -> None:
    """Raise AssertionError when stored capabilities drift from live providers."""
    mismatches: list[str] = []
    for name, spec in _REGISTRY.items():
        live = provider_capabilities(spec.factory())
        if live != spec.capabilities:
            mismatches.append(
                f"{name!r}: stored={spec.capabilities!r}, live={live!r}",
            )
    if mismatches:
        joined = "; ".join(mismatches)
        raise AssertionError(f"registry capability drift: {joined}")


def validate_registry_query(
    provider_name: str,
    query: MarketQuery | None = None,
    *,
    loan_term_years: int = 30,
    metro_id: str | None = None,
    reference_year: int | None = None,
) -> MarketQuery:
    """Raise when a registered provider cannot honor the requested query dimensions."""
    normalized = normalize_query(
        query,
        loan_term_years=loan_term_years,
        metro_id=metro_id,
        reference_year=reference_year,
    )
    query_plan = plan_query(normalized, provider_capabilities_for(provider_name))
    if query_plan.has_dropped_fields:
        joined = ", ".join(query_plan.dropped_fields)
        raise UnsupportedQueryError(
            f"provider {provider_name!r} does not support query field(s): {joined}",
            provider_name=provider_name,
            query=normalized,
            unsupported_fields=query_plan.dropped_fields,
        )
    return normalized


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
