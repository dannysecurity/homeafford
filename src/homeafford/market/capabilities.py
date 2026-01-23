"""Capability flags describing what a market data provider supports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeafford.market.query import DEFAULT_QUERY

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
        unsupported: list[str] = []
        if query.metro_id is not None and not self.supports_metro_pricing:
            unsupported.append("metro_id")
        if query.reference_year is not None and not self.supports_reference_year:
            unsupported.append("reference_year")
        if (
            query.loan_term_years != DEFAULT_QUERY.loan_term_years
            and not self.supports_term_rates
        ):
            unsupported.append("loan_term_years")
        return tuple(unsupported)

    def satisfies(self, query: MarketQuery) -> bool:
        """Return True when the provider can honor every set query dimension."""
        return not self.unsupported_query_fields(query)
