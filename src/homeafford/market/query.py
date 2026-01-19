"""Query context passed to market data providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketQuery:
    """Parameters that can change provider output."""

    loan_term_years: int = 30
    metro_id: str | None = None
    reference_year: int | None = None


DEFAULT_QUERY = MarketQuery()


def market_query(
    *,
    loan_term_years: int = 30,
    metro_id: str | None = None,
    reference_year: int | None = None,
) -> MarketQuery:
    """Build an explicit query from discrete parameters."""
    return MarketQuery(
        loan_term_years=loan_term_years,
        metro_id=metro_id,
        reference_year=reference_year,
    )


def normalize_query(
    query: MarketQuery | None = None,
    *,
    loan_term_years: int | None = None,
    metro_id: str | None = None,
    reference_year: int | None = None,
) -> MarketQuery:
    """Return an explicit query, merging legacy keyword arguments when needed."""
    if query is not None:
        merged_term = loan_term_years if loan_term_years is not None else query.loan_term_years
        merged_metro = metro_id if metro_id is not None else query.metro_id
        merged_year = reference_year if reference_year is not None else query.reference_year
        if (
            merged_term != query.loan_term_years
            or merged_metro != query.metro_id
            or merged_year != query.reference_year
        ):
            return MarketQuery(
                loan_term_years=merged_term,
                metro_id=merged_metro,
                reference_year=merged_year,
            )
        return query
    if loan_term_years is not None or metro_id is not None or reference_year is not None:
        return MarketQuery(
            loan_term_years=30 if loan_term_years is None else loan_term_years,
            metro_id=metro_id,
            reference_year=reference_year,
        )
    return DEFAULT_QUERY
