"""Market data provider subsystem for housing and investment assumptions."""

from homeafford.market.base import (
    BaseMarketProvider,
    DelegatingMarketProvider,
    provider_capabilities,
    provider_list_metros,
    provider_name,
    validate_provider_contract,
)
from homeafford.market.builder import ProviderBuilder
from homeafford.market.cache import (
    InMemorySnapshotCache,
    NullSnapshotCache,
    SnapshotCache,
    cache_key_for_query,
)
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.composite import (
    CachedMarketProvider,
    FallbackMarketProvider,
    build_provider_stack,
)
from homeafford.market.errors import MarketDataError, MarketDataUnavailable, UnsupportedQueryError
from homeafford.market.csv_metro import CsvMetroMarketProvider, csv_metro_provider
from homeafford.market.metro_prices import MetroPriceTrendRow, load_metro_price_trends
from homeafford.market.metro_trends import (
    MetroTrendCatalog,
    MetroTrendSummary,
    default_metro_trend_catalog,
    format_metro_trends_table,
    project_median_price,
)
from homeafford.market.overrides import OverrideMarketProvider
from homeafford.market.planner import QueryPlan, QuerySatisfiability, plan_query
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import DEFAULT_QUERY, MarketQuery, market_query, normalize_query
from homeafford.market.registry import (
    ProviderSpec,
    available_providers,
    format_provider_choices,
    get_provider,
    provider_descriptions,
    register_provider,
)
from homeafford.market.request import MarketOverrides, MarketRequest
from homeafford.market.resolved import ResolvedMarket
from homeafford.market.resolve import (
    MarketResolver,
    apply_market_to_affordability_inputs,
    apply_market_to_purchase_scenario,
    effective_market_fields,
    effective_pmi_fields,
    resolve_market,
    resolve_market_detailed,
    resolve_request,
    resolve_request_detailed,
)
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot
from homeafford.market.static import StaticMarketProvider
from homeafford.market.term_adjusted import TermAdjustedMarketProvider

__all__ = [
    "BaseMarketProvider",
    "CachedMarketProvider",
    "CsvMetroMarketProvider",
    "DEFAULT_MARKET",
    "DEFAULT_QUERY",
    "DelegatingMarketProvider",
    "FallbackMarketProvider",
    "MarketDataError",
    "MarketDataUnavailable",
    "MarketDataProvider",
    "MarketOverrides",
    "MarketQuery",
    "MarketRequest",
    "MarketResolver",
    "MarketSnapshot",
    "MetroPriceTrendRow",
    "MetroTrendCatalog",
    "MetroTrendSummary",
    "InMemorySnapshotCache",
    "NullSnapshotCache",
    "OverrideMarketProvider",
    "ProviderBuilder",
    "ProviderCapabilities",
    "ProviderSpec",
    "QueryPlan",
    "QuerySatisfiability",
    "ResolvedMarket",
    "SnapshotCache",
    "StaticMarketProvider",
    "TermAdjustedMarketProvider",
    "UnsupportedQueryError",
    "apply_market_to_affordability_inputs",
    "apply_market_to_purchase_scenario",
    "available_providers",
    "build_provider_stack",
    "cache_key_for_query",
    "csv_metro_provider",
    "default_metro_trend_catalog",
    "effective_market_fields",
    "effective_pmi_fields",
    "format_metro_trends_table",
    "format_provider_choices",
    "get_provider",
    "load_metro_price_trends",
    "market_query",
    "project_median_price",
    "normalize_query",
    "plan_query",
    "provider_capabilities",
    "provider_descriptions",
    "provider_list_metros",
    "provider_name",
    "register_provider",
    "resolve_market",
    "resolve_market_detailed",
    "resolve_request",
    "resolve_request_detailed",
    "validate_provider_contract",
]
