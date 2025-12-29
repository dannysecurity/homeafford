"""Pytest fixtures shared across calculator edge-case test modules."""

from __future__ import annotations

import pytest

from tests.helpers.edge_case_catalog import EdgeCaseCatalog


@pytest.fixture
def edge_cases() -> EdgeCaseCatalog:
    """Named boundary scenarios for affordability, purchase, and ARM calculators."""
    return EdgeCaseCatalog()
