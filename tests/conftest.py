"""Pytest fixtures shared across calculator edge-case test modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.edge_case_catalog import EdgeCaseCatalog
from tests.helpers.metro_price_fixtures import (
    METRO_HOME_PRICE_TRENDS_PATH,
    METRO_HOME_PRICE_TRENDS_BUDGET_PATH,
    METRO_HOME_PRICE_TRENDS_DECLINING_PATH,
    METRO_HOME_PRICE_TRENDS_PREMIUM_PATH,
    METRO_HOME_PRICE_TRENDS_STABLE_PATH,
    METRO_HOME_PRICE_TRENDS_RECOVERING_PATH,
    MetroPriceTrendRow,
    load_metro_home_price_trends,
    load_metro_home_price_trends_budget,
    load_metro_home_price_trends_declining,
    load_metro_home_price_trends_premium,
    load_metro_home_price_trends_recovering,
    load_metro_home_price_trends_stable,
)
from homeafford.market.metro_trends import MetroTrendCatalog


@pytest.fixture
def edge_cases() -> EdgeCaseCatalog:
    """Named boundary scenarios for affordability, purchase, and ARM calculators."""
    return EdgeCaseCatalog()


@pytest.fixture
def metro_home_price_trends_path() -> Path:
    """Path to the shared metro home price trends CSV fixture."""
    return METRO_HOME_PRICE_TRENDS_PATH


@pytest.fixture
def metro_home_price_trends() -> list[MetroPriceTrendRow]:
    """Parsed metro home price trend rows from the shared CSV fixture."""
    return load_metro_home_price_trends()


@pytest.fixture
def metro_trend_catalog(metro_home_price_trends_path: Path) -> MetroTrendCatalog:
    """Metro trend catalog loaded from the shared CSV fixture."""
    return MetroTrendCatalog.from_csv(metro_home_price_trends_path)


@pytest.fixture
def metro_home_price_trends_budget_path() -> Path:
    """Path to the budget-metro home price trends CSV fixture."""
    return METRO_HOME_PRICE_TRENDS_BUDGET_PATH


@pytest.fixture
def metro_home_price_trends_budget() -> list[MetroPriceTrendRow]:
    """Parsed budget-metro home price trend rows from the CSV fixture."""
    return load_metro_home_price_trends_budget()


@pytest.fixture
def metro_trend_budget_catalog(metro_home_price_trends_budget_path: Path) -> MetroTrendCatalog:
    """Metro trend catalog loaded from the budget CSV fixture."""
    return MetroTrendCatalog.from_csv(metro_home_price_trends_budget_path)


@pytest.fixture
def metro_home_price_trends_premium_path() -> Path:
    """Path to the premium-metro home price trends CSV fixture."""
    return METRO_HOME_PRICE_TRENDS_PREMIUM_PATH


@pytest.fixture
def metro_home_price_trends_premium() -> list[MetroPriceTrendRow]:
    """Parsed premium-metro home price trend rows from the CSV fixture."""
    return load_metro_home_price_trends_premium()


@pytest.fixture
def metro_trend_premium_catalog(metro_home_price_trends_premium_path: Path) -> MetroTrendCatalog:
    """Metro trend catalog loaded from the premium CSV fixture."""
    return MetroTrendCatalog.from_csv(metro_home_price_trends_premium_path)


@pytest.fixture
def metro_home_price_trends_declining_path() -> Path:
    """Path to the declining-metro home price trends CSV fixture."""
    return METRO_HOME_PRICE_TRENDS_DECLINING_PATH


@pytest.fixture
def metro_home_price_trends_declining() -> list[MetroPriceTrendRow]:
    """Parsed declining-metro home price trend rows from the CSV fixture."""
    return load_metro_home_price_trends_declining()


@pytest.fixture
def metro_trend_declining_catalog(metro_home_price_trends_declining_path: Path) -> MetroTrendCatalog:
    """Metro trend catalog loaded from the declining CSV fixture."""
    return MetroTrendCatalog.from_csv(metro_home_price_trends_declining_path)


@pytest.fixture
def metro_home_price_trends_stable_path() -> Path:
    """Path to the stable-metro home price trends CSV fixture."""
    return METRO_HOME_PRICE_TRENDS_STABLE_PATH


@pytest.fixture
def metro_home_price_trends_stable() -> list[MetroPriceTrendRow]:
    """Parsed stable-metro home price trend rows from the CSV fixture."""
    return load_metro_home_price_trends_stable()


@pytest.fixture
def metro_trend_stable_catalog(metro_home_price_trends_stable_path: Path) -> MetroTrendCatalog:
    """Metro trend catalog loaded from the stable CSV fixture."""
    return MetroTrendCatalog.from_csv(metro_home_price_trends_stable_path)


@pytest.fixture
def metro_home_price_trends_recovering_path() -> Path:
    """Path to the recovering-metro home price trends CSV fixture."""
    return METRO_HOME_PRICE_TRENDS_RECOVERING_PATH


@pytest.fixture
def metro_home_price_trends_recovering() -> list[MetroPriceTrendRow]:
    """Parsed recovering-metro home price trend rows from the CSV fixture."""
    return load_metro_home_price_trends_recovering()


@pytest.fixture
def metro_trend_recovering_catalog(metro_home_price_trends_recovering_path: Path) -> MetroTrendCatalog:
    """Metro trend catalog loaded from the recovering CSV fixture."""
    return MetroTrendCatalog.from_csv(metro_home_price_trends_recovering_path)
