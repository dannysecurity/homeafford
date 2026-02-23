"""Tests for dimension-based market data source and assembler interfaces."""

from __future__ import annotations

import pytest

from homeafford.market import (
    AssembledMarketProvider,
    CsvMetroMarketProvider,
    CsvMetroPriceSource,
    DEFAULT_MARKET,
    MarketDataProvider,
    MarketQuery,
    MarketSnapshot,
    ProviderCapabilities,
    QUERY_DIMENSIONS,
    QueryDimension,
    RateDataSource,
    SnapshotAssembler,
    StaticMarketProvider,
    StaticRateSource,
    StaticSavingsReturnSource,
    TermAdjustedMarketProvider,
    TermAdjustedRateSource,
    assembled_csv_metro_provider,
    assembled_term_adjusted_metro_provider,
    rate_source_from_provider,
    validate_provider_contract,
)
from homeafford.market.dimensions import unsupported_query_fields
from homeafford.market.errors import MarketDataUnavailable
from homeafford.market.sources import (
    MetroPriceDataSource,
    MetroPriceAssumptions,
    ProviderRateAdapter,
    RateAssumptions,
    SavingsReturnAssumptions,
)


def test_query_dimensions_cover_all_capability_fields():
    assert {dimension.field_name for dimension in QUERY_DIMENSIONS} == {
        "metro_id",
        "reference_year",
        "loan_term_years",
    }


def test_query_dimension_detects_non_default_values():
    metro = QueryDimension("metro_id", "supports_metro_pricing")
    assert not metro.is_set(MarketQuery())
    assert metro.is_set(MarketQuery(metro_id="31080"))


def test_unsupported_query_fields_uses_dimension_registry():
    caps = ProviderCapabilities()
    fields = unsupported_query_fields(MarketQuery(metro_id="31080", loan_term_years=15), caps)
    assert fields == ("metro_id", "loan_term_years")


def test_static_rate_source_returns_fixed_assumptions():
    source = StaticRateSource()
    rates = source.fetch_rates(query=MarketQuery())
    assert rates.mortgage_rate == DEFAULT_MARKET.mortgage_rate
    assert rates.property_tax_rate == DEFAULT_MARKET.property_tax_rate
    assert isinstance(rates, RateAssumptions)


def test_static_savings_source_returns_fixed_return():
    source = StaticSavingsReturnSource()
    savings = source.fetch_savings_return(query=MarketQuery())
    assert savings.savings_annual_return == DEFAULT_MARKET.savings_annual_return


def test_csv_metro_price_source_lists_metros():
    source = CsvMetroPriceSource()
    metros = source.list_metros()
    assert "31080" in metros
    assert "41860" in metros


def test_csv_metro_price_source_resolves_reference_year():
    source = CsvMetroPriceSource()
    price = source.fetch_metro_price(metro_id="41860", reference_year=2022)
    assert price.median_home_price == pytest.approx(1_200_000)
    assert price.source == "csv-metro:41860:2022"


def test_snapshot_assembler_merges_dimension_sources():
    assembler = SnapshotAssembler(
        rates=StaticRateSource(),
        metro=CsvMetroPriceSource(),
        savings=StaticSavingsReturnSource(),
    )
    snapshot = assembler.assemble(query=MarketQuery(metro_id="31080"))
    assert snapshot.mortgage_rate == DEFAULT_MARKET.mortgage_rate
    assert snapshot.median_home_price == pytest.approx(1_068_301)
    assert snapshot.metro_id == "31080"


def test_snapshot_assembler_without_metro_returns_base_fields():
    assembler = SnapshotAssembler(rates=StaticRateSource())
    snapshot = assembler.assemble(query=MarketQuery())
    assert snapshot == MarketSnapshot(
        mortgage_rate=DEFAULT_MARKET.mortgage_rate,
        property_tax_rate=DEFAULT_MARKET.property_tax_rate,
        insurance_annual=DEFAULT_MARKET.insurance_annual,
        savings_annual_return=DEFAULT_MARKET.savings_annual_return,
        pmi_annual_rate=DEFAULT_MARKET.pmi_annual_rate,
        pmi_ltv_threshold=DEFAULT_MARKET.pmi_ltv_threshold,
        source="static",
    )


def test_snapshot_assembler_raises_without_metro_source():
    assembler = SnapshotAssembler(rates=StaticRateSource())
    with pytest.raises(MarketDataUnavailable, match="no metro price source"):
        assembler.assemble(query=MarketQuery(metro_id="31080"))


def test_assembled_provider_exposes_metro_capabilities():
    provider = AssembledMarketProvider(
        SnapshotAssembler(rates=StaticRateSource(), metro=CsvMetroPriceSource()),
    )
    assert provider.capabilities.supports_metro_pricing
    assert provider.capabilities.supports_reference_year
    assert "31080" in provider.list_metros()


def test_assembled_provider_satisfies_market_data_contract():
    provider = assembled_csv_metro_provider()
    validate_provider_contract(provider)
    assert isinstance(provider, MarketDataProvider)


def test_assembled_csv_metro_matches_monolithic_provider():
    assembled = assembled_csv_metro_provider()
    monolithic = CsvMetroMarketProvider()
    query = MarketQuery(metro_id="31080", reference_year=2023)

    assembled_snapshot = assembled.get_snapshot(query=query)
    monolithic_snapshot = monolithic.get_snapshot(query=query)

    assert assembled_snapshot.mortgage_rate == monolithic_snapshot.mortgage_rate
    assert assembled_snapshot.median_home_price == monolithic_snapshot.median_home_price
    assert assembled_snapshot.metro_id == monolithic_snapshot.metro_id
    assert assembled_snapshot.metro_name == monolithic_snapshot.metro_name


def test_provider_rate_adapter_delegates_to_inner_provider():
    inner = StaticMarketProvider()
    adapter = ProviderRateAdapter(inner)
    rates = adapter.fetch_rates(query=MarketQuery())
    assert rates.mortgage_rate == DEFAULT_MARKET.mortgage_rate
    assert isinstance(adapter, RateDataSource)


def test_rate_source_from_provider_wraps_existing_provider():
    inner = StaticMarketProvider()
    source = rate_source_from_provider(inner)
    rates = source.fetch_rates(query=MarketQuery())
    assert rates.mortgage_rate == DEFAULT_MARKET.mortgage_rate


def test_assembled_provider_rejects_unsupported_loan_term():
    provider = assembled_csv_metro_provider()
    with pytest.raises(MarketDataUnavailable, match="loan_term_years"):
        provider.get_snapshot(query=MarketQuery(loan_term_years=15))


def test_metro_price_data_source_protocol_is_runtime_checkable():
    source = CsvMetroPriceSource()
    assert isinstance(source, MetroPriceDataSource)


def test_custom_metro_source_plugs_into_assembler():
    class FixedMetroSource:
        def list_metros(self) -> tuple[str, ...]:
            return ("99999",)

        def fetch_metro_price(
            self,
            *,
            metro_id: str,
            reference_year: int | None,
        ) -> MetroPriceAssumptions:
            return MetroPriceAssumptions(
                metro_id=metro_id,
                metro_name="Test Metro",
                median_home_price=500_000.0,
                source="test-metro",
            )

    provider = AssembledMarketProvider(
        SnapshotAssembler(rates=StaticRateSource(), metro=FixedMetroSource()),
        name="test-assembled",
    )
    snapshot = provider.get_snapshot(query=MarketQuery(metro_id="99999"))
    assert snapshot.median_home_price == pytest.approx(500_000)
    assert snapshot.metro_name == "Test Metro"
    assert snapshot.source == "static+test-metro"


def test_term_adjusted_rate_source_applies_spreads():
    source = TermAdjustedRateSource(StaticRateSource())
    rates_30 = source.fetch_rates(query=MarketQuery(loan_term_years=30))
    rates_15 = source.fetch_rates(query=MarketQuery(loan_term_years=15))
    assert rates_30.mortgage_rate == DEFAULT_MARKET.mortgage_rate
    assert rates_15.mortgage_rate == pytest.approx(DEFAULT_MARKET.mortgage_rate - 0.005)
    assert rates_15.source == "static+15yr"
    assert isinstance(source, RateDataSource)


def test_term_adjusted_rate_source_exposes_term_capabilities():
    assembler = SnapshotAssembler(rates=TermAdjustedRateSource(StaticRateSource()))
    assert assembler.capabilities.supports_term_rates
    assert not assembler.capabilities.supports_metro_pricing


def test_assembled_term_adjusted_metro_supports_loan_term():
    provider = assembled_term_adjusted_metro_provider()
    snapshot = provider.get_snapshot(
        query=MarketQuery(metro_id="31080", loan_term_years=15),
    )
    assert snapshot.metro_id == "31080"
    assert snapshot.mortgage_rate == pytest.approx(DEFAULT_MARKET.mortgage_rate - 0.005)


def test_assembled_term_adjusted_metro_matches_wrapper_provider():
    assembled = assembled_term_adjusted_metro_provider()
    wrapped = TermAdjustedMarketProvider(CsvMetroMarketProvider())
    query = MarketQuery(metro_id="31080", loan_term_years=15, reference_year=2023)

    assembled_snapshot = assembled.get_snapshot(query=query)
    wrapped_snapshot = wrapped.get_snapshot(query=query)

    assert assembled_snapshot.mortgage_rate == wrapped_snapshot.mortgage_rate
    assert assembled_snapshot.median_home_price == wrapped_snapshot.median_home_price
    assert assembled_snapshot.metro_id == wrapped_snapshot.metro_id
