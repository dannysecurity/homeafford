"""Declarative registry linking query dimensions to provider capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeafford.market.query import DEFAULT_QUERY

if TYPE_CHECKING:
    from homeafford.market.capabilities import ProviderCapabilities
    from homeafford.market.query import MarketQuery


@dataclass(frozen=True)
class QueryDimension:
    """One query field and the capability flag that governs support for it."""

    field_name: str
    capability_attr: str

    def is_set(self, query: MarketQuery) -> bool:
        """Return True when this dimension differs from the default query."""
        if self.field_name == "loan_term_years":
            return query.loan_term_years != DEFAULT_QUERY.loan_term_years
        if self.field_name == "metro_id":
            return query.metro_id is not None
        if self.field_name == "reference_year":
            return query.reference_year is not None
        raise ValueError(f"unknown query dimension: {self.field_name!r}")

    def is_supported(self, caps: ProviderCapabilities) -> bool:
        """Return True when the given capabilities honor this dimension."""
        return bool(getattr(caps, self.capability_attr))


QUERY_DIMENSIONS: tuple[QueryDimension, ...] = (
    QueryDimension("metro_id", "supports_metro_pricing"),
    QueryDimension("reference_year", "supports_reference_year"),
    QueryDimension("loan_term_years", "supports_term_rates"),
)


def unsupported_query_fields(query: MarketQuery, caps: ProviderCapabilities) -> tuple[str, ...]:
    """Return query dimensions the capabilities cannot honor."""
    return tuple(
        dimension.field_name
        for dimension in QUERY_DIMENSIONS
        if dimension.is_set(query) and not dimension.is_supported(caps)
    )
