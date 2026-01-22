"""Capability flags describing what a market data provider supports."""

from __future__ import annotations

from dataclasses import dataclass


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
