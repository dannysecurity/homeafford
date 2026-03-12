"""Provider interface for resolving market assumptions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.query import MarketQuery
from homeafford.market.snapshot import MarketSnapshot


@runtime_checkable
class MarketDataProvider(Protocol):
    """Source of market assumptions for affordability calculations."""

    @property
    def name(self) -> str:
        """Stable provider identifier."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Feature flags describing supported query dimensions."""
        ...

    def list_metros(self) -> tuple[str, ...] | None:
        """Return supported metro IDs when metro pricing is available."""
        ...

    def get_snapshot(self, *, query: MarketQuery | None = None) -> MarketSnapshot:
        """Return assumptions for the given query context."""
        ...


def provider_name(provider: MarketDataProvider) -> str:
    """Return a provider's stable identifier, falling back to the class name.

    Duck-typed providers may omit an explicit ``name`` attribute; wrappers
    should use this helper rather than accessing ``inner.name`` directly.
    """
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
