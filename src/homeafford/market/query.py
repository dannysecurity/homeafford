"""Query context passed to market data providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketQuery:
    """Parameters that can change provider output."""

    loan_term_years: int = 30
    metro_id: str | None = None


DEFAULT_QUERY = MarketQuery()


def normalize_query(
    query: MarketQuery | None = None,
    *,
    loan_term_years: int | None = None,
) -> MarketQuery:
    """Return an explicit query, building one from legacy term arguments when needed."""
    if query is not None:
        if loan_term_years is not None and loan_term_years != query.loan_term_years:
            return MarketQuery(loan_term_years=loan_term_years, metro_id=query.metro_id)
        return query
    if loan_term_years is not None:
        return MarketQuery(loan_term_years=loan_term_years)
    return DEFAULT_QUERY
