"""Pytest fixtures shared across calculator edge-case test modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.edge_case_catalog import EdgeCaseCatalog
from tests.helpers.metro_price_fixtures import (
    METRO_HOME_PRICE_TRENDS_PATH,
    MetroPriceTrendRow,
    load_metro_home_price_trends,
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
