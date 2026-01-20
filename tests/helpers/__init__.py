"""Shared test helpers for homeafford calculator edge-case coverage."""

from tests.helpers.edge_case_catalog import (
    EdgeCaseCatalog,
    affordability_inputs,
    purchase_scenario,
)
from tests.helpers.metro_price_fixtures import (
    METRO_HOME_PRICE_TRENDS_PATH,
    MetroPriceTrendRow,
    load_metro_home_price_trends,
    median_home_price_for,
    yoy_change_for,
)

__all__ = [
    "EdgeCaseCatalog",
    "METRO_HOME_PRICE_TRENDS_PATH",
    "MetroPriceTrendRow",
    "affordability_inputs",
    "load_metro_home_price_trends",
    "median_home_price_for",
    "purchase_scenario",
    "yoy_change_for",
]
