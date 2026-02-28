"""Tests for the market data provider middleware pipeline."""

from __future__ import annotations

from datetime import timedelta

from homeafford.market import (
    DEFAULT_MARKET,
    CachedMarketProvider,
    CacheMiddleware,
    CsvMetroMarketProvider,
    InMemorySnapshotCache,
    MarketDataUnavailable,
    MarketQuery,
    MiddlewareStack,
    OverrideMiddleware,
    ProviderMiddleware,
    StaticMarketProvider,
    TermAdjustmentMiddleware,
    apply_middleware_stack,
    build_fallback_stack,
    cache_middleware,
    merge_source_capabilities,
    metro_source_capabilities,
    override_middleware,
    rate_source_capabilities,
    savings_source_capabilities,
    term_adjustment_middleware,
)
from homeafford.market.sources import (
    CsvMetroPriceSource,
    StaticRateSource,
    StaticSavingsReturnSource,
)
from homeafford.market.term_adjusted import TermAdjustedRateSource


def test_cache_middleware_wraps_provider():
    calls = 0

    class CountingProvider:
        name = "counting"

        def get_snapshot(self, *, query=None):
            nonlocal calls
            calls += 1
            return DEFAULT_MARKET

    provider = cache_middleware().wrap(CountingProvider())
    provider.get_snapshot()
    provider.get_snapshot()
    assert calls == 1
    assert isinstance(provider, CachedMarketProvider)
    assert provider.name == "cached:counting"


def test_term_adjustment_middleware_applies_spread():
    provider = term_adjustment_middleware().wrap(StaticMarketProvider())
    snapshot = provider.get_snapshot(query=MarketQuery(loan_term_years=15))
    assert snapshot.mortgage_rate < DEFAULT_MARKET.mortgage_rate
    assert provider.name == "term-adjusted:static"


def test_override_middleware_applies_overrides():
    provider = override_middleware({"mortgage_rate": 0.055}).wrap(StaticMarketProvider())
    snapshot = provider.get_snapshot()
    assert snapshot.mortgage_rate == 0.055


def test_apply_middleware_stack_orders_innermost_first():
    provider = apply_middleware_stack(
        StaticMarketProvider(),
        (
            term_adjustment_middleware(),
            cache_middleware(),
        ),
    )
    assert provider.name == "cached:term-adjusted:static"
    snapshot = provider.get_snapshot(query=MarketQuery(loan_term_years=15))
    assert snapshot.mortgage_rate < DEFAULT_MARKET.mortgage_rate


def test_middleware_stack_fluent_api():
    stack = (
        MiddlewareStack(CsvMetroMarketProvider())
        .with_term_adjustment()
        .with_cache()
    )
    assert len(stack.middleware) == 2
    assert isinstance(stack.middleware[0], TermAdjustmentMiddleware)
    assert isinstance(stack.middleware[1], CacheMiddleware)

    provider = stack.build()
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="31080", loan_term_years=15))
    assert snapshot.metro_id == "31080"
    assert snapshot.mortgage_rate < DEFAULT_MARKET.mortgage_rate


def test_middleware_stack_accepts_registry_name():
    provider = MiddlewareStack("static").with_cache().build()
    assert provider.name == "cached:static"


def test_build_fallback_stack_tries_alternatives():
    class FailingProvider:
        def get_snapshot(self, *, query=None):
            raise MarketDataUnavailable("offline")

    provider = build_fallback_stack(FailingProvider(), StaticMarketProvider())
    snapshot = provider.get_snapshot()
    assert snapshot.mortgage_rate == DEFAULT_MARKET.mortgage_rate


def test_provider_middleware_protocol_is_runtime_checkable():
    assert isinstance(CacheMiddleware(), ProviderMiddleware)
    assert isinstance(TermAdjustmentMiddleware(), ProviderMiddleware)
    assert isinstance(OverrideMiddleware({"mortgage_rate": 0.05}), ProviderMiddleware)


def test_rate_source_capabilities_detects_term_support():
    static_caps = rate_source_capabilities(StaticRateSource())
    term_caps = rate_source_capabilities(TermAdjustedRateSource(StaticRateSource()))
    assert not static_caps.supports_term_rates
    assert term_caps.supports_term_rates


def test_metro_source_capabilities_enable_metro_queries():
    caps = metro_source_capabilities(CsvMetroPriceSource())
    assert caps.supports_metro_pricing
    assert caps.supports_reference_year


def test_savings_source_capabilities_are_empty():
    caps = savings_source_capabilities(StaticSavingsReturnSource())
    assert caps == savings_source_capabilities(StaticSavingsReturnSource())


def test_merge_source_capabilities_combines_dimensions():
    caps = merge_source_capabilities(
        TermAdjustedRateSource(StaticRateSource()),
        CsvMetroPriceSource(),
        StaticSavingsReturnSource(),
    )
    assert caps.supports_term_rates
    assert caps.supports_metro_pricing
    assert caps.supports_reference_year


def test_cache_middleware_accepts_custom_cache_backend():
    shared = InMemorySnapshotCache()
    calls = 0

    class CountingProvider:
        def get_snapshot(self, *, query=None):
            nonlocal calls
            calls += 1
            return DEFAULT_MARKET

    provider = cache_middleware(cache=shared).wrap(CountingProvider())
    provider.get_snapshot()
    provider.get_snapshot()
    assert calls == 1
    assert provider.cache is shared


def test_cache_middleware_honors_ttl():
    provider = cache_middleware(ttl=timedelta(seconds=0)).wrap(StaticMarketProvider())
    assert isinstance(provider, CachedMarketProvider)
