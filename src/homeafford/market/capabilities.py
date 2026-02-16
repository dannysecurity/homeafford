"""Capability flags describing what a market data provider supports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeafford.market.query import MarketQuery


@dataclass(frozen=True)
class ProviderCapabilities:
    """Feature flags that describe how a provider responds to query fields."""

    supports_metro_pricing: bool = False
    supports_reference_year: bool = False
    supports_term_rates: bool = False

    def merged_with(self, other: ProviderCapabilities) -> ProviderCapabilities:
        """Return capabilities satisfied by either provider."""
        return ProviderCapabilities(
            supports_metro_pricing=self.supports_metro_pricing or other.supports_metro_pricing,
            supports_reference_year=self.supports_reference_year or other.supports_reference_year,
            supports_term_rates=self.supports_term_rates or other.supports_term_rates,
        )

    def unsupported_query_fields(self, query: MarketQuery) -> tuple[str, ...]:
        """Return query dimensions this provider cannot honor."""
        from homeafford.market.dimensions import unsupported_query_fields

        return unsupported_query_fields(query, self)

    def satisfies(self, query: MarketQuery) -> bool:
        """Return True when the provider can honor every set query dimension."""
        from homeafford.market.planner import plan_query

        return plan_query(query, self).is_fully_supported
