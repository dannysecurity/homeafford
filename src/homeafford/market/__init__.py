"""Market data provider subsystem for housing and investment assumptions."""

from homeafford.market.base import BaseMarketProvider, DelegatingMarketProvider
from homeafford.market.capabilities import ProviderCapabilities
from homeafford.market.composite import (
    CachedMarketProvider,
    FallbackMarketProvider,
    MarketDataError,
    MarketDataUnavailable,
)
from homeafford.market.csv_metro import CsvMetroMarketProvider, csv_metro_provider
from homeafford.market.metro_prices import MetroPriceTrendRow, load_metro_price_trends
from homeafford.market.overrides import OverrideMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import DEFAULT_QUERY, MarketQuery, market_query, normalize_query
from homeafford.market.registry import available_providers, get_provider, register_provider
from homeafford.market.request import MarketOverrides, MarketRequest
from homeafford.market.resolve import (
    apply_market_to_affordability_inputs,
    apply_market_to_purchase_scenario,
    effective_market_fields,
    effective_pmi_fields,
    resolve_market,
    resolve_request,
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
    "MarketSnapshot",
    "MetroPriceTrendRow",
    "OverrideMarketProvider",
    "ProviderCapabilities",
    "StaticMarketProvider",
    "TermAdjustedMarketProvider",
    "apply_market_to_affordability_inputs",
    "apply_market_to_purchase_scenario",
    "available_providers",
    "csv_metro_provider",
    "effective_market_fields",
    "effective_pmi_fields",
    "get_provider",
    "load_metro_price_trends",
    "market_query",
    "normalize_query",
    "register_provider",
    "resolve_market",
    "resolve_request",
]
