"""Helpers for applying market snapshots to calculator inputs."""

from __future__ import annotations

from collections.abc import Mapping

from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import MarketQuery, normalize_query
from homeafford.market.snapshot import MarketSnapshot


def resolve_market(
    provider: MarketDataProvider,
    *,
    query: MarketQuery | None = None,
    loan_term_years: int = 30,
    overrides: Mapping[str, float | str] | None = None,
) -> MarketSnapshot:
    """Fetch a snapshot for a query and apply optional field overrides."""
    normalized = normalize_query(query, loan_term_years=loan_term_years)
    snapshot = provider.get_snapshot(query=normalized)
    if overrides:
        snapshot = snapshot.with_overrides(**overrides)
    return snapshot


def resolve_snapshot(
    provider: MarketDataProvider,
    *,
    query: MarketQuery | None = None,
    loan_term_years: int = 30,
    overrides: Mapping[str, float | str] | None = None,
) -> MarketSnapshot:
    """Fetch a snapshot and apply optional field overrides."""
    return resolve_market(
        provider,
        query=query,
        loan_term_years=loan_term_years,
        overrides=overrides,
    )


def apply_market_to_affordability_inputs(inputs, provider: MarketDataProvider, *, overrides=None):
    """Return affordability inputs with market fields populated from a provider."""
    from homeafford.affordability import AffordabilityInputs

    snapshot = resolve_market(
        provider,
        loan_term_years=inputs.loan_term_years,
        overrides=overrides,
    )
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


def apply_market_to_purchase_scenario(scenario, provider: MarketDataProvider, *, overrides=None):
    """Return a purchase scenario with market fields populated from a provider."""
    from homeafford.check import PurchaseScenario

    snapshot = resolve_market(
        provider,
        loan_term_years=scenario.loan_term_years,
        overrides=overrides,
    )
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
