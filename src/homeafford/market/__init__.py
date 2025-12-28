"""Market data provider subsystem for housing and investment assumptions."""

from homeafford.market.composite import (
    CachedMarketProvider,
    FallbackMarketProvider,
    MarketDataError,
)
from homeafford.market.overrides import OverrideMarketProvider
from homeafford.market.protocol import MarketDataProvider
from homeafford.market.registry import available_providers, get_provider, register_provider
from homeafford.market.resolve import (
    apply_market_to_affordability_inputs,
    apply_market_to_purchase_scenario,
    effective_market_fields,
    resolve_snapshot,
)
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot
from homeafford.market.static import StaticMarketProvider

__all__ = [
    "CachedMarketProvider",
    "DEFAULT_MARKET",
    "FallbackMarketProvider",
    "MarketDataError",
    "MarketDataProvider",
    "MarketSnapshot",
    "OverrideMarketProvider",
    "StaticMarketProvider",
    "apply_market_to_affordability_inputs",
    "apply_market_to_purchase_scenario",
    "available_providers",
    "effective_market_fields",
    "get_provider",
    "register_provider",
    "resolve_snapshot",
]
