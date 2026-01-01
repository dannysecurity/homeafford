"""Tests for the market data provider subsystem."""

from __future__ import annotations

import pytest

from homeafford.affordability import AffordabilityInputs, affordability_bands, affordability_bands_from_provider
from homeafford.check import PurchaseScenario, check_against_band
from homeafford.market import (
    CachedMarketProvider,
    DEFAULT_MARKET,
    DEFAULT_QUERY,
    FallbackMarketProvider,
    MarketDataError,
    MarketDataUnavailable,
    MarketQuery,
    MarketSnapshot,
    OverrideMarketProvider,
    StaticMarketProvider,
    apply_market_to_affordability_inputs,
    apply_market_to_purchase_scenario,
    available_providers,
    get_provider,
    normalize_query,
    register_provider,
    resolve_market,
)
from homeafford.report import affordability_report_by_year


def test_default_market_includes_pmi_assumptions():
    assert DEFAULT_MARKET.pmi_annual_rate == 0.005
    assert DEFAULT_MARKET.pmi_ltv_threshold == 0.80


def test_default_market_matches_legacy_defaults():
    assert DEFAULT_MARKET.mortgage_rate == 0.065
    assert DEFAULT_MARKET.property_tax_rate == 0.012
    assert DEFAULT_MARKET.insurance_annual == 1_200.0
    assert DEFAULT_MARKET.savings_annual_return == 0.04


def test_static_provider_returns_snapshot():
    custom = MarketSnapshot(
        mortgage_rate=0.07,
        property_tax_rate=0.015,
        insurance_annual=1_500.0,
        savings_annual_return=0.05,
        source="test",
    )
    provider = StaticMarketProvider(custom)
    snapshot = provider.get_snapshot()
    assert snapshot is custom
    assert snapshot.source == "test"


def test_override_provider_applies_field_overrides():
    base = StaticMarketProvider()
    provider = OverrideMarketProvider(base, {"mortgage_rate": 0.055})
    snapshot = provider.get_snapshot()
    assert snapshot.mortgage_rate == 0.055
    assert snapshot.property_tax_rate == DEFAULT_MARKET.property_tax_rate


def test_normalize_query_defaults_to_thirty_year_term():
    assert normalize_query() == DEFAULT_QUERY
    assert normalize_query(loan_term_years=15) == MarketQuery(loan_term_years=15)


def test_cached_provider_reuses_snapshot():
    calls = 0

    class CountingProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            nonlocal calls
            calls += 1
            return DEFAULT_MARKET

    provider = CachedMarketProvider(CountingProvider())
    provider.get_snapshot()
    provider.get_snapshot()
    assert calls == 1


def test_cached_provider_keys_cache_by_loan_term():
    calls: list[int] = []

    class TermSensitiveProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            term = 30 if query is None else query.loan_term_years
            calls.append(term)
            return MarketSnapshot(
                mortgage_rate=0.05 + term / 1_000,
                property_tax_rate=0.012,
                insurance_annual=1_200.0,
                source=f"{term}-year",
            )

    provider = CachedMarketProvider(TermSensitiveProvider())
    snapshot_30 = provider.get_snapshot(query=MarketQuery(loan_term_years=30))
    snapshot_15 = provider.get_snapshot(query=MarketQuery(loan_term_years=15))
    provider.get_snapshot(query=MarketQuery(loan_term_years=30))

    assert snapshot_30.mortgage_rate != snapshot_15.mortgage_rate
    assert calls == [30, 15]


def test_cached_provider_invalidate_clears_entries():
    calls = 0

    class CountingProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            nonlocal calls
            calls += 1
            return DEFAULT_MARKET

    provider = CachedMarketProvider(CountingProvider())
    provider.get_snapshot()
    provider.invalidate()
    provider.get_snapshot()
    assert calls == 2


def test_fallback_provider_uses_first_successful_source():
    class FailingProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            raise MarketDataUnavailable("offline")

    provider = FallbackMarketProvider([FailingProvider(), StaticMarketProvider()])
    snapshot = provider.get_snapshot()
    assert snapshot.mortgage_rate == DEFAULT_MARKET.mortgage_rate


def test_fallback_provider_raises_when_all_fail():
    class FailingProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            raise MarketDataUnavailable("offline")

    provider = FallbackMarketProvider([FailingProvider()])
    with pytest.raises(MarketDataError):
        provider.get_snapshot()


def test_fallback_provider_propagates_unexpected_errors():
    class BrokenProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            raise RuntimeError("programming error")

    provider = FallbackMarketProvider([BrokenProvider(), StaticMarketProvider()])
    with pytest.raises(RuntimeError, match="programming error"):
        provider.get_snapshot()


def test_resolve_market_applies_overrides_to_query_result():
    provider = StaticMarketProvider()
    snapshot = resolve_market(provider, query=MarketQuery(loan_term_years=30), overrides={"mortgage_rate": 0.05})
    assert snapshot.mortgage_rate == 0.05


def test_registry_lists_and_instantiates_static_provider():
    assert "static" in available_providers()
    provider = get_provider("static")
    assert isinstance(provider, StaticMarketProvider)


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("missing")


def test_register_custom_provider():
    custom = StaticMarketProvider(
        MarketSnapshot(
            mortgage_rate=0.05,
            property_tax_rate=0.01,
            insurance_annual=900.0,
            source="custom",
        )
    )

    register_provider("custom-test", lambda: custom)
    try:
        snapshot = get_provider("custom-test").get_snapshot()
        assert snapshot.mortgage_rate == 0.05
    finally:
        from homeafford.market import registry

        registry._REGISTRY.pop("custom-test", None)


def test_apply_market_to_affordability_inputs_attaches_snapshot():
    base = AffordabilityInputs(gross_annual_income=120_000)
    resolved = apply_market_to_affordability_inputs(base, StaticMarketProvider())
    assert resolved.market is not None
    assert resolved.mortgage_rate == DEFAULT_MARKET.mortgage_rate


def test_apply_market_to_purchase_scenario_attaches_snapshot():
    base = PurchaseScenario(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
    )
    resolved = apply_market_to_purchase_scenario(base, StaticMarketProvider())
    assert resolved.market is not None
    assert resolved.insurance_annual == DEFAULT_MARKET.insurance_annual


def test_affordability_bands_from_provider_matches_static_defaults():
    inputs = AffordabilityInputs(gross_annual_income=120_000, down_payment=20_000)
    direct = affordability_bands(inputs)
    from_provider = affordability_bands_from_provider(inputs, StaticMarketProvider())
    assert len(from_provider) == len(direct)
    for left, right in zip(direct, from_provider, strict=True):
        assert left.label == right.label
        assert left.max_home_price == pytest.approx(right.max_home_price)
        assert left.estimated_piti == pytest.approx(right.estimated_piti)


def test_market_snapshot_overrides_scalar_fields():
    snapshot = MarketSnapshot(
        mortgage_rate=0.08,
        property_tax_rate=0.02,
        insurance_annual=2_000.0,
        source="override",
    )
    inputs = AffordabilityInputs(
        gross_annual_income=120_000,
        mortgage_rate=0.05,
        market=snapshot,
    )
    bands = affordability_bands(inputs)
    explicit = affordability_bands(
        AffordabilityInputs(
            gross_annual_income=120_000,
            mortgage_rate=0.08,
            property_tax_rate=0.02,
            insurance_annual=2_000.0,
        )
    )
    assert bands[0].max_home_price == pytest.approx(explicit[0].max_home_price)


def test_check_against_band_with_market_snapshot():
    scenario = PurchaseScenario(
        home_price=400_000,
        down_payment=80_000,
        gross_annual_income=120_000,
        market=DEFAULT_MARKET,
    )
    result = check_against_band(scenario, band_label="conservative")
    assert result.estimated_piti > 0


def test_report_by_year_with_provider():
    rows = affordability_report_by_year(
        gross_annual_income=100_000,
        starting_balance=10_000,
        monthly_contribution=1_000,
        years=2,
        provider=StaticMarketProvider(),
    )
    assert len(rows) == 3
    assert rows[0].down_payment == 10_000
    assert rows[-1].down_payment > rows[0].down_payment
