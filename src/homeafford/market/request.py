"""Unified request objects for resolving market data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace

from homeafford.market.query import DEFAULT_QUERY, MarketQuery, normalize_query
from homeafford.market.snapshot import MarketSnapshot

_VALID_OVERRIDE_FIELDS = frozenset(
    field.name for field in fields(MarketSnapshot) if field.name != "source"
)


@dataclass(frozen=True)
class MarketOverrides:
    """Typed, validated overrides applied after a provider fetch."""

    mortgage_rate: float | None = None
    property_tax_rate: float | None = None
    insurance_annual: float | None = None
    savings_annual_return: float | None = None
    pmi_annual_rate: float | None = None
    pmi_ltv_threshold: float | None = None
    metro_id: str | None = None
    metro_name: str | None = None
    median_home_price: float | None = None

    def apply_to(self, snapshot: MarketSnapshot) -> MarketSnapshot:
        """Return a copy of snapshot with non-None override fields applied."""
        overrides = {
            name: value
            for name, value in self.__dict__.items()
            if value is not None
        }
        if not overrides:
            return snapshot
        return snapshot.with_overrides(**overrides)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, float | str]) -> MarketOverrides:
        """Build overrides from a mapping, rejecting unknown field names."""
        unknown = set(mapping) - _VALID_OVERRIDE_FIELDS
        if unknown:
            joined = ", ".join(sorted(unknown))
            raise ValueError(f"unknown market override field(s): {joined}")
        return cls(**dict(mapping))


@dataclass(frozen=True)
class MarketRequest:
    """Complete resolution request combining query context and optional overrides."""

    query: MarketQuery = DEFAULT_QUERY
    overrides: MarketOverrides | None = None

    @classmethod
    def build(
        cls,
        *,
        query: MarketQuery | None = None,
        loan_term_years: int = 30,
        metro_id: str | None = None,
        reference_year: int | None = None,
        overrides: Mapping[str, float | str] | MarketOverrides | None = None,
    ) -> MarketRequest:
        """Construct a request from discrete parameters or legacy keyword arguments."""
        normalized = normalize_query(
            query,
            loan_term_years=loan_term_years,
            metro_id=metro_id,
            reference_year=reference_year,
        )
        typed_overrides: MarketOverrides | None
        if overrides is None:
            typed_overrides = None
        elif isinstance(overrides, MarketOverrides):
            typed_overrides = overrides
        else:
            typed_overrides = MarketOverrides.from_mapping(overrides)
        return cls(query=normalized, overrides=typed_overrides)

    def with_overrides(self, overrides: MarketOverrides) -> MarketRequest:
        """Return a copy with overrides replaced."""
        return replace(self, overrides=overrides)
