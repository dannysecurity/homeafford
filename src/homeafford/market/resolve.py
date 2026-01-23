"""Helpers for applying market snapshots to calculator inputs."""

from __future__ import annotations

from collections.abc import Mapping

from homeafford.market.composite import MarketDataUnavailable
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.request import MarketOverrides, MarketRequest
from homeafford.market.snapshot import MarketSnapshot


def resolve_request(
    provider: MarketDataProvider,
    request: MarketRequest,
) -> MarketSnapshot:
    """Fetch a snapshot for a structured request and apply optional overrides."""
    unsupported = provider.capabilities.unsupported_query_fields(request.query)
    if unsupported:
        joined = ", ".join(unsupported)
        raise MarketDataUnavailable(
            f"provider {provider.name!r} does not support query field(s): {joined}"
        )
    snapshot = provider.get_snapshot(query=request.query)
    if request.overrides is None:
        return snapshot
    return request.overrides.apply_to(snapshot)


def resolve_market(
    provider: MarketDataProvider,
    *,
    query: MarketQuery | None = None,
    loan_term_years: int = 30,
    metro_id: str | None = None,
    reference_year: int | None = None,
    overrides: Mapping[str, float | str] | MarketOverrides | None = None,
) -> MarketSnapshot:
    """Fetch a snapshot for a query and apply optional field overrides."""
    request = MarketRequest.build(
        query=query,
        loan_term_years=loan_term_years,
        metro_id=metro_id,
        reference_year=reference_year,
        overrides=overrides,
    )
    return resolve_request(provider, request)


def apply_market_to_affordability_inputs(
    inputs,
    provider: MarketDataProvider,
    *,
    query: MarketQuery | None = None,
    metro_id: str | None = None,
    reference_year: int | None = None,
    overrides: Mapping[str, float | str] | MarketOverrides | None = None,
):
    """Return affordability inputs with market fields populated from a provider."""
    from homeafford.affordability import AffordabilityInputs

    resolved_query = normalize_query(
        query,
        loan_term_years=inputs.loan_term_years,
        metro_id=metro_id,
        reference_year=reference_year,
    )
    snapshot = resolve_market(provider, query=resolved_query, overrides=overrides)
    return AffordabilityInputs(
        gross_annual_income=inputs.gross_annual_income,
        monthly_debt_payments=inputs.monthly_debt_payments,
        down_payment=inputs.down_payment,
        property_tax_rate=snapshot.property_tax_rate,
        insurance_annual=snapshot.insurance_annual,
        hoa_monthly=inputs.hoa_monthly,
        loan_term_years=inputs.loan_term_years,
        mortgage_rate=snapshot.mortgage_rate,
        market=snapshot,
    )


def apply_market_to_purchase_scenario(
    scenario,
    provider: MarketDataProvider,
    *,
    query: MarketQuery | None = None,
    metro_id: str | None = None,
    reference_year: int | None = None,
    overrides: Mapping[str, float | str] | MarketOverrides | None = None,
):
    """Return a purchase scenario with market fields populated from a provider."""
    from homeafford.check import PurchaseScenario

    resolved_query = normalize_query(
        query,
        loan_term_years=scenario.loan_term_years,
        metro_id=metro_id,
        reference_year=reference_year,
    )
    snapshot = resolve_market(provider, query=resolved_query, overrides=overrides)
    return PurchaseScenario(
        home_price=scenario.home_price,
        down_payment=scenario.down_payment,
        gross_annual_income=scenario.gross_annual_income,
        monthly_debt_payments=scenario.monthly_debt_payments,
        property_tax_rate=snapshot.property_tax_rate,
        insurance_annual=snapshot.insurance_annual,
        hoa_monthly=scenario.hoa_monthly,
        loan_term_years=scenario.loan_term_years,
        mortgage_rate=snapshot.mortgage_rate,
        closing_costs=scenario.closing_costs,
        market=snapshot,
    )


def effective_market_fields(
    *,
    market: MarketSnapshot | None,
    mortgage_rate: float,
    property_tax_rate: float,
    insurance_annual: float,
) -> tuple[float, float, float]:
    """Prefer explicit snapshot values when a market snapshot is attached."""
    if market is None:
        return mortgage_rate, property_tax_rate, insurance_annual
    return market.mortgage_rate, market.property_tax_rate, market.insurance_annual


def effective_pmi_fields(
    *,
    market: MarketSnapshot | None,
    pmi_annual_rate: float | None = None,
    pmi_ltv_threshold: float | None = None,
) -> tuple[float, float]:
    """Return PMI rate and LTV threshold, preferring an attached market snapshot."""
    if market is None:
        rate = 0.005 if pmi_annual_rate is None else pmi_annual_rate
        threshold = 0.80 if pmi_ltv_threshold is None else pmi_ltv_threshold
        return rate, threshold
    return market.pmi_annual_rate, market.pmi_ltv_threshold
