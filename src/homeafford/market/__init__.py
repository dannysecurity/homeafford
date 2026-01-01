"""Market data provider subsystem for housing and investment assumptions."""

from homeafford.market.composite import (
    CachedMarketProvider,
    FallbackMarketProvider,
    MarketDataError,
    MarketDataUnavailable,
)
from homeafford.market.overrides import OverrideMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.query import DEFAULT_QUERY, MarketQuery, normalize_query
from homeafford.market.registry import available_providers, get_provider, register_provider
from homeafford.market.resolve import (
    apply_market_to_affordability_inputs,
    apply_market_to_purchase_scenario,
    effective_market_fields,
    resolve_market,
    resolve_snapshot,
)
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot
from homeafford.market.static import StaticMarketProvider

__all__ = [
    "CachedMarketProvider",
    "DEFAULT_MARKET",
    "DEFAULT_QUERY",
    "FallbackMarketProvider",
    "MarketDataError",
    "MarketDataUnavailable",
    "MarketDataProvider",
    "MarketQuery",
    "MarketSnapshot",
    "OverrideMarketProvider",
    "StaticMarketProvider",
    "apply_market_to_affordability_inputs",
    "apply_market_to_purchase_scenario",
    "available_providers",
    "effective_market_fields",
    "get_provider",
    "normalize_query",
    "register_provider",
    "resolve_market",
    "resolve_snapshot",
]
