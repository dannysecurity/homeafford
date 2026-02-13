"""Query planning for market data provider capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.query import DEFAULT_QUERY, MarketQuery


class QuerySatisfiability(str, Enum):
    """How completely a provider can honor a market query."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class QueryPolicy(str, Enum):
    """How a provider should handle query dimensions it cannot fully support."""

    STRICT = "strict"
    """Raise when any requested dimension is unsupported."""

    DEGRADE = "degrade"
    """Silently trim unsupported dimensions before fetching."""


@dataclass(frozen=True)
class QueryPlan:
    """Planned resolution of a market query against provider capabilities."""

    requested: MarketQuery
    effective: MarketQuery
    dropped_fields: tuple[str, ...]
    satisfiability: QuerySatisfiability

    @property
    def is_fully_supported(self) -> bool:
        """Return True when every requested dimension can be honored."""
        return self.satisfiability == QuerySatisfiability.FULL

    @property
    def has_dropped_fields(self) -> bool:
        """Return True when unsupported dimensions were stripped from the query."""
        return bool(self.dropped_fields)


def _non_default_query_fields(query: MarketQuery) -> tuple[str, ...]:
    """Return query dimensions that differ from the default context."""
    fields: list[str] = []
    if query.loan_term_years != DEFAULT_QUERY.loan_term_years:
        fields.append("loan_term_years")
    if query.metro_id is not None:
        fields.append("metro_id")
    if query.reference_year is not None:
        fields.append("reference_year")
    return tuple(fields)


def effective_query_for_capabilities(
    query: MarketQuery,
    caps: ProviderCapabilities,
) -> MarketQuery:
    """Return a query limited to dimensions the capabilities can honor."""
    return MarketQuery(
        loan_term_years=query.loan_term_years if caps.supports_term_rates else DEFAULT_QUERY.loan_term_years,
        metro_id=query.metro_id if caps.supports_metro_pricing else None,
        reference_year=query.reference_year if caps.supports_reference_year else None,
    )


def plan_query(query: MarketQuery, caps: ProviderCapabilities) -> QueryPlan:
    """Plan how to satisfy a query given provider capabilities."""
    dropped = caps.unsupported_query_fields(query)
    if not dropped:
        return QueryPlan(
            requested=query,
            effective=query,
            dropped_fields=(),
            satisfiability=QuerySatisfiability.FULL,
        )

    effective = effective_query_for_capabilities(query, caps)
    non_default = _non_default_query_fields(query)
    if set(dropped) == set(non_default):
        satisfiability = QuerySatisfiability.NONE
    else:
        satisfiability = QuerySatisfiability.PARTIAL

    return QueryPlan(
        requested=query,
        effective=effective,
        dropped_fields=dropped,
        satisfiability=satisfiability,
    )
