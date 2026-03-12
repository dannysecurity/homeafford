"""Shared test helpers for homeafford calculator edge-case coverage."""

from tests.helpers.edge_case_catalog import (
    EdgeCaseCatalog,
    affordability_inputs,
    purchase_scenario,
)
from tests.helpers.metro_price_fixtures import (
    BUNDLED_METRO_HOME_PRICE_TRENDS_PATH,
    METRO_HOME_PRICE_TRENDS_PATH,
    METRO_HOME_PRICE_TRENDS_BUDGET_PATH,
    MetroPriceTrendRow,
    fixture_matches_bundled_csv,
    load_metro_home_price_trends,
    load_metro_home_price_trends_budget,
    median_home_price_for,
    metro_ids_in,
    metros_with_median_at_or_below,
    yoy_change_for,
)

__all__ = [
    "EdgeCaseCatalog",
    "BUNDLED_METRO_HOME_PRICE_TRENDS_PATH",
    "METRO_HOME_PRICE_TRENDS_PATH",
    "METRO_HOME_PRICE_TRENDS_BUDGET_PATH",
    "MetroPriceTrendRow",
    "affordability_inputs",
    "fixture_matches_bundled_csv",
    "load_metro_home_price_trends",
    "load_metro_home_price_trends_budget",
    "median_home_price_for",
    "metro_ids_in",
    "metros_with_median_at_or_below",
    "purchase_scenario",
    "yoy_change_for",
]
