"""Tests for the market data provider subsystem."""

from __future__ import annotations

import pytest

from homeafford.affordability import AffordabilityInputs, affordability_bands, affordability_bands_from_provider
from homeafford.check import PurchaseScenario, check_against_band
from homeafford.market import (
    CachedMarketProvider,
    CsvMetroMarketProvider,
    DEFAULT_MARKET,
    DEFAULT_QUERY,
    DelegatingMarketProvider,
    FallbackMarketProvider,
    MarketDataError,
    MarketDataProvider,
    MarketDataUnavailable,
    MarketOverrides,
    MarketQuery,
    MarketRequest,
    MarketResolver,
    MarketSnapshot,
    OverrideMarketProvider,
    ProviderBuilder,
    ProviderCapabilities,
    ProviderSpec,
    QueryPlan,
    QuerySatisfiability,
    StaticMarketProvider,
    TermAdjustedMarketProvider,
    UnsupportedQueryError,
    apply_market_to_affordability_inputs,
    apply_market_to_purchase_scenario,
    available_providers,
    effective_pmi_fields,
    format_provider_choices,
    get_provider,
    market_query,
    normalize_query,
    plan_query,
    provider_descriptions,
    register_provider,
    resolve_market,
    resolve_request,
    validate_provider_contract,
)
from homeafford.market.base import validate_query_support, validate_provider_contract
from homeafford.market.composite import build_provider_stack
from homeafford.report import affordability_report_by_year


def test_default_market_includes_pmi_assumptions():
    assert DEFAULT_MARKET.pmi_annual_rate == 0.005
    assert DEFAULT_MARKET.pmi_ltv_threshold == 0.80


def test_default_market_matches_legacy_defaults():
    assert DEFAULT_MARKET.mortgage_rate == 0.065
    assert DEFAULT_MARKET.property_tax_rate == 0.012
    assert DEFAULT_MARKET.insurance_annual == 1_200.0
    assert DEFAULT_MARKET.savings_annual_return == 0.04


def test_static_provider_rejects_unsupported_loan_term():
    provider = StaticMarketProvider()
    with pytest.raises(MarketDataUnavailable, match="loan_term_years"):
        provider.get_snapshot(query=MarketQuery(loan_term_years=15))


def test_static_provider_rejects_unsupported_metro_query():
    provider = StaticMarketProvider()
    with pytest.raises(MarketDataUnavailable, match="metro_id"):
        provider.get_snapshot(query=MarketQuery(metro_id="31080"))


def test_cached_provider_is_delegating_wrapper():
    provider = CachedMarketProvider(StaticMarketProvider())
    assert isinstance(provider, DelegatingMarketProvider)


def test_provider_descriptions_include_all_registered_names():
    descriptions = provider_descriptions()
    assert set(descriptions) == set(available_providers())
    assert descriptions["static"]
    assert "csv-metro" in format_provider_choices()


def test_validate_query_support_uses_default_capabilities_for_duck_types():
    class MinimalProvider:
        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            return DEFAULT_MARKET

    with pytest.raises(MarketDataUnavailable, match="metro_id"):
        validate_query_support(MinimalProvider(), MarketQuery(metro_id="31080"))


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


def test_market_query_builds_explicit_context():
    assert market_query(metro_id="31080", reference_year=2023) == MarketQuery(
        loan_term_years=30,
        metro_id="31080",
        reference_year=2023,
    )


def test_normalize_query_merges_metro_and_year():
    base = MarketQuery(loan_term_years=15, metro_id="31080")
    assert normalize_query(base, reference_year=2024) == MarketQuery(
        loan_term_years=15,
        metro_id="31080",
        reference_year=2024,
    )


def test_csv_metro_provider_returns_latest_price_for_metro():
    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="31080"))
    assert snapshot.metro_id == "31080"
    assert snapshot.median_home_price == pytest.approx(990_360)
    assert snapshot.source == "csv-metro:31080:2024"


def test_csv_metro_provider_honors_reference_year():
    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(
        query=MarketQuery(metro_id="41860", reference_year=2022),
    )
    assert snapshot.median_home_price == pytest.approx(1_200_000)
    assert snapshot.source == "csv-metro:41860:2022"


def test_csv_metro_provider_includes_austin_metro():
    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="12420", reference_year=2024))
    assert snapshot.metro_name == "Austin-Round Rock-Georgetown, TX"
    assert snapshot.median_home_price == pytest.approx(580_800)


def test_csv_metro_provider_without_metro_returns_base_snapshot():
    provider = CsvMetroMarketProvider()
    snapshot = provider.get_snapshot()
    assert snapshot == DEFAULT_MARKET


def test_csv_metro_provider_raises_for_unknown_metro():
    provider = CsvMetroMarketProvider()
    with pytest.raises(MarketDataUnavailable, match="unknown metro_id"):
        provider.get_snapshot(query=MarketQuery(metro_id="99999"))


def test_cached_provider_keys_cache_by_metro():
    calls: list[str | None] = []

    class MetroSensitiveProvider:
        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(supports_metro_pricing=True)

        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            metro_id = None if query is None else query.metro_id
            calls.append(metro_id)
            return MarketSnapshot(
                mortgage_rate=0.065,
                property_tax_rate=0.012,
                insurance_annual=1_200.0,
                metro_id=metro_id,
                source=f"metro:{metro_id}",
            )

    provider = CachedMarketProvider(MetroSensitiveProvider())
    la = provider.get_snapshot(query=MarketQuery(metro_id="31080"))
    sf = provider.get_snapshot(query=MarketQuery(metro_id="41860"))
    provider.get_snapshot(query=MarketQuery(metro_id="31080"))

    assert la.metro_id == "31080"
    assert sf.metro_id == "41860"
    assert calls == ["31080", "41860"]


def test_registry_lists_csv_metro_provider():
    assert "csv-metro" in available_providers()
    snapshot = get_provider("csv-metro").get_snapshot(
        query=MarketQuery(metro_id="35620", reference_year=2023),
    )
    assert snapshot.median_home_price == pytest.approx(676_000)


def test_apply_market_to_affordability_inputs_passes_metro_query():
    base = AffordabilityInputs(gross_annual_income=120_000)
    resolved = apply_market_to_affordability_inputs(
        base,
        CsvMetroMarketProvider(),
        metro_id="31080",
        reference_year=2023,
    )
    assert resolved.market is not None
    assert resolved.market.median_home_price == pytest.approx(918_000)


def test_effective_pmi_fields_prefers_market_snapshot():
    snapshot = MarketSnapshot(
        mortgage_rate=0.065,
        property_tax_rate=0.012,
        insurance_annual=1_200.0,
        pmi_annual_rate=0.007,
        pmi_ltv_threshold=0.85,
        source="test",
    )
    rate, threshold = effective_pmi_fields(market=snapshot, pmi_annual_rate=0.005)
    assert rate == 0.007
    assert threshold == 0.85


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
        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(supports_term_rates=True)

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


def test_static_provider_exposes_name_and_capabilities():
    provider = StaticMarketProvider()
    assert provider.name == "static"
    assert provider.capabilities == ProviderCapabilities()
    assert provider.list_metros() is None


def test_csv_metro_provider_lists_available_metros():
    provider = CsvMetroMarketProvider()
    assert provider.capabilities.supports_metro_pricing
    assert provider.capabilities.supports_reference_year
    assert "31080" in provider.list_metros()
    assert "12420" in provider.list_metros()


def test_market_overrides_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unknown market override field"):
        MarketOverrides.from_mapping({"not_a_field": 1.0})


def test_market_overrides_apply_to_snapshot():
    overrides = MarketOverrides(mortgage_rate=0.05, insurance_annual=900.0)
    adjusted = overrides.apply_to(DEFAULT_MARKET)
    assert adjusted.mortgage_rate == 0.05
    assert adjusted.insurance_annual == 900.0
    assert adjusted.property_tax_rate == DEFAULT_MARKET.property_tax_rate


def test_market_request_builds_from_legacy_kwargs():
    request = MarketRequest.build(metro_id="31080", reference_year=2023, overrides={"mortgage_rate": 0.05})
    assert request.query.metro_id == "31080"
    assert request.query.reference_year == 2023
    assert request.overrides is not None
    assert request.overrides.mortgage_rate == 0.05


def test_resolve_request_applies_typed_overrides():
    provider = StaticMarketProvider()
    request = MarketRequest.build(overrides=MarketOverrides(mortgage_rate=0.055))
    snapshot = resolve_request(provider, request)
    assert snapshot.mortgage_rate == 0.055


def test_term_adjusted_provider_lowers_rate_for_shorter_terms():
    provider = TermAdjustedMarketProvider(StaticMarketProvider())
    snapshot_30 = provider.get_snapshot(query=MarketQuery(loan_term_years=30))
    snapshot_15 = provider.get_snapshot(query=MarketQuery(loan_term_years=15))
    assert provider.capabilities.supports_term_rates
    assert snapshot_15.mortgage_rate < snapshot_30.mortgage_rate
    assert snapshot_15.mortgage_rate == pytest.approx(DEFAULT_MARKET.mortgage_rate - 0.005)


def test_term_adjusted_provider_preserves_metro_context():
    provider = TermAdjustedMarketProvider(CsvMetroMarketProvider())
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="31080", loan_term_years=15))
    assert snapshot.metro_id == "31080"
    assert snapshot.median_home_price == pytest.approx(990_360)
    assert snapshot.mortgage_rate < DEFAULT_MARKET.mortgage_rate


def test_fallback_provider_merges_capabilities():
    provider = FallbackMarketProvider([CsvMetroMarketProvider(), StaticMarketProvider()])
    caps = provider.capabilities
    assert caps.supports_metro_pricing
    assert caps.supports_reference_year


def test_market_query_cache_key():
    query = MarketQuery(loan_term_years=15, metro_id="31080", reference_year=2023)
    assert query.cache_key() == (15, "31080", 2023)


def test_provider_capabilities_satisfies_query():
    metro_caps = ProviderCapabilities(supports_metro_pricing=True)
    assert metro_caps.satisfies(MarketQuery(metro_id="31080"))
    assert not metro_caps.satisfies(MarketQuery(metro_id="31080", reference_year=2023))

    full_caps = ProviderCapabilities(supports_metro_pricing=True, supports_reference_year=True)
    assert full_caps.satisfies(MarketQuery(metro_id="31080", reference_year=2023))


def test_provider_capabilities_unsupported_query_fields():
    caps = ProviderCapabilities()
    assert caps.unsupported_query_fields(MarketQuery()) == ()
    assert caps.unsupported_query_fields(MarketQuery(metro_id="31080")) == ("metro_id",)
    assert caps.unsupported_query_fields(MarketQuery(reference_year=2023)) == ("reference_year",)
    assert caps.unsupported_query_fields(MarketQuery(loan_term_years=15)) == ("loan_term_years",)


def test_resolve_request_rejects_unsupported_loan_term():
    provider = StaticMarketProvider()
    request = MarketRequest.build(loan_term_years=15)
    with pytest.raises(MarketDataUnavailable, match="loan_term_years"):
        resolve_request(provider, request)


def test_market_resolver_applies_request_overrides():
    resolver = MarketResolver(StaticMarketProvider())
    request = MarketRequest.build(overrides=MarketOverrides(mortgage_rate=0.0525))
    snapshot = resolver.resolve(request)
    assert snapshot.mortgage_rate == 0.0525


def test_market_resolver_applies_to_affordability_inputs():
    base = AffordabilityInputs(gross_annual_income=120_000, loan_term_years=30)
    resolver = MarketResolver(CsvMetroMarketProvider())
    resolved = resolver.apply_to_affordability_inputs(
        base,
        metro_id="31080",
        reference_year=2023,
    )
    assert resolved.market is not None
    assert resolved.market.median_home_price == pytest.approx(918_000)


def test_market_resolver_applies_to_purchase_scenario():
    base = PurchaseScenario(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
    )
    resolved = MarketResolver(StaticMarketProvider()).apply_to_purchase_scenario(base)
    assert resolved.market is not None
    assert resolved.insurance_annual == DEFAULT_MARKET.insurance_annual


def test_build_provider_stack_wraps_with_cache():
    calls = 0

    class CountingProvider:
        name = "counting"

        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            nonlocal calls
            calls += 1
            return DEFAULT_MARKET

    provider = build_provider_stack(CountingProvider())
    provider.get_snapshot()
    provider.get_snapshot()
    assert calls == 1
    assert provider.name.startswith("cached:")


def test_term_adjusted_metro_provider_uses_cache():
    provider = get_provider("term-adjusted-metro")
    assert provider.name.startswith("cached:term-adjusted:csv-metro")


def test_resolve_request_rejects_unsupported_metro_query():
    provider = StaticMarketProvider()
    request = MarketRequest.build(metro_id="31080")
    with pytest.raises(MarketDataUnavailable, match="does not support query field"):
        resolve_request(provider, request)


def test_delegating_provider_forwards_capabilities():
    provider = OverrideMarketProvider(CsvMetroMarketProvider(), {"mortgage_rate": 0.05})
    assert provider.capabilities.supports_metro_pricing
    assert "31080" in provider.list_metros()


def test_registry_includes_term_adjusted_providers():
    assert "term-adjusted" in available_providers()
    assert "term-adjusted-metro" in available_providers()
    term_provider = get_provider("term-adjusted")
    assert isinstance(term_provider, TermAdjustedMarketProvider)
    assert isinstance(term_provider, MarketDataProvider)


@pytest.mark.parametrize("provider_name", available_providers())
def test_registered_providers_satisfy_market_data_contract(provider_name: str):
    provider = get_provider(provider_name)
    validate_provider_contract(provider)
    assert provider.name
    snapshot = provider.get_snapshot()
    assert isinstance(snapshot, MarketSnapshot)


@pytest.mark.parametrize("provider_name", available_providers())
def test_cached_registry_providers_wrap_with_cache(provider_name: str):
    from homeafford.market.registry import _REGISTRY

    spec = _REGISTRY[provider_name]
    provider = get_provider(provider_name)
    if spec.cache:
        assert provider.name.startswith("cached:")
    else:
        assert not provider.name.startswith("cached:")


def test_register_provider_applies_cache_flag():
    calls = 0

    class CountingProvider:
        name = "counting"

        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities()

        def list_metros(self) -> tuple[str, ...] | None:
            return None

        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            nonlocal calls
            calls += 1
            return DEFAULT_MARKET

    register_provider("cached-counting", lambda: CountingProvider(), cache=True)
    try:
        provider = get_provider("cached-counting")
        assert provider.name.startswith("cached:")
        provider.get_snapshot()
        provider.get_snapshot()
        assert calls == 1
    finally:
        from homeafford.market import registry

        registry._REGISTRY.pop("cached-counting", None)


def test_plan_query_full_support():
    caps = ProviderCapabilities(supports_metro_pricing=True, supports_reference_year=True)
    query = MarketQuery(metro_id="31080", reference_year=2023)
    query_plan = plan_query(query, caps)
    assert query_plan.is_fully_supported
    assert query_plan.satisfiability == QuerySatisfiability.FULL
    assert query_plan.effective == query
    assert query_plan.dropped_fields == ()


def test_plan_query_partial_support_drops_reference_year():
    caps = ProviderCapabilities(supports_metro_pricing=True)
    query = MarketQuery(metro_id="31080", reference_year=2023)
    query_plan = plan_query(query, caps)
    assert query_plan.satisfiability == QuerySatisfiability.PARTIAL
    assert query_plan.dropped_fields == ("reference_year",)
    assert query_plan.effective == MarketQuery(metro_id="31080")


def test_plan_query_none_when_only_unsupported_dimensions():
    caps = ProviderCapabilities()
    query = MarketQuery(metro_id="31080")
    query_plan = plan_query(query, caps)
    assert query_plan.satisfiability == QuerySatisfiability.NONE
    assert query_plan.dropped_fields == ("metro_id",)


def test_unsupported_query_error_carries_structured_fields():
    provider = StaticMarketProvider()
    query = MarketQuery(metro_id="31080")
    with pytest.raises(UnsupportedQueryError) as exc_info:
        provider.get_snapshot(query=query)
    error = exc_info.value
    assert error.provider_name == "static"
    assert error.query == query
    assert error.unsupported_fields == ("metro_id",)


def test_provider_builder_composes_term_adjusted_metro_stack():
    provider = (
        ProviderBuilder(CsvMetroMarketProvider())
        .with_term_adjustment()
        .cached()
        .build()
    )
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="31080", loan_term_years=15))
    assert snapshot.metro_id == "31080"
    assert snapshot.mortgage_rate < DEFAULT_MARKET.mortgage_rate
    assert provider.name.startswith("cached:term-adjusted:")


def test_provider_builder_with_fallback():
    class FailingProvider:
        name = "failing"

        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities()

        def list_metros(self) -> tuple[str, ...] | None:
            return None

        def get_snapshot(self, *, query=None) -> MarketSnapshot:
            raise MarketDataUnavailable("offline")

    provider = ProviderBuilder(FailingProvider()).with_fallback(StaticMarketProvider()).build()
    snapshot = provider.get_snapshot()
    assert snapshot.mortgage_rate == DEFAULT_MARKET.mortgage_rate


def test_fallback_provider_skips_unsatisfiable_sources():
    provider = FallbackMarketProvider([StaticMarketProvider(), CsvMetroMarketProvider()])
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="31080"))
    assert snapshot.metro_id == "31080"
    assert snapshot.median_home_price == pytest.approx(990_360)
