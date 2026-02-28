"""Tests for down payment × income affordability frontier modeling."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from homeafford.affordability_frontier import (
    format_affordability_frontier,
    format_affordability_frontier_json,
    model_affordability_frontier,
)
from homeafford.check import PurchaseScenario
from homeafford.cli import main
from homeafford.dti_analysis import min_income_for_dti
from homeafford.model import min_down_payment_for_dti


def _scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=500_000,
        down_payment=50_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_frontier_grid_dimensions_match_sweeps():
    down_pcts = (0.05, 0.10, 0.20)
    income_mults = (0.85, 1.0, 1.15)
    result = model_affordability_frontier(
        _scenario(),
        down_payment_pcts=down_pcts,
        income_multipliers=income_mults,
        band_label="conservative",
    )
    assert len(result.cells) == len(down_pcts) * len(income_mults)
    assert result.down_payment_pcts == down_pcts
    assert result.income_multipliers == income_mults


def test_frontier_high_income_and_down_passes():
    result = model_affordability_frontier(
        _scenario(home_price=500_000, gross_annual_income=150_000, monthly_debt_payments=400),
        down_payment_pcts=(0.05, 0.20),
        income_multipliers=(0.75, 1.30),
        band_label="conservative",
    )
    by_key = {
        (cell.down_payment_pct, cell.income_multiplier): cell for cell in result.cells
    }
    high = by_key[(0.20, 1.30)]
    assert high.passes_all

    low = by_key[(0.05, 0.75)]
    assert not low.passes_all or not low.passes_dti


def test_frontier_min_down_matches_solver():
    scenario = _scenario(
        home_price=600_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        down_payment=60_000,
    )
    result = model_affordability_frontier(
        scenario,
        down_payment_pcts=(0.05, 0.15, 0.20),
        income_multipliers=(1.0,),
        band_label="conservative",
    )
    expected = min_down_payment_for_dti(scenario, band_label="conservative")
    assert result.min_down_at_base_income == expected


def test_frontier_min_income_matches_solver():
    scenario = _scenario(
        home_price=600_000,
        down_payment=120_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
    )
    result = model_affordability_frontier(
        scenario,
        down_payment_pcts=(0.20,),
        income_multipliers=(0.8, 1.0, 1.2),
        band_label="conservative",
    )
    expected = min_income_for_dti(scenario, band_label="conservative")
    assert result.min_income_at_base_down == expected


def test_frontier_boundary_is_monotonic_in_tradeoff():
    result = model_affordability_frontier(
        _scenario(
            home_price=500_000,
            gross_annual_income=180_000,
            monthly_debt_payments=200,
        ),
        down_payment_pcts=(0.05, 0.10, 0.15, 0.20),
        income_multipliers=(0.85, 1.0, 1.15),
        band_label="conservative",
    )
    assert result.boundary_cells
    sorted_boundary = sorted(
        result.boundary_cells,
        key=lambda c: (c.down_payment_pct, c.income_multiplier),
    )
    for left, right in zip(sorted_boundary, sorted_boundary[1:]):
        if left.down_payment_pct < right.down_payment_pct:
            assert left.gross_annual_income >= right.gross_annual_income


def test_format_affordability_frontier_includes_grid_and_boundary():
    result = model_affordability_frontier(
        _scenario(),
        down_payment_pcts=(0.05, 0.20),
        income_multipliers=(1.0,),
        band_label="conservative",
    )
    text = format_affordability_frontier(result)
    assert "Down × income affordability frontier" in text
    assert "Base income" in text
    assert "1.00x" in text
    assert "5.0%" in text


def test_format_affordability_frontier_json_is_machine_readable():
    result = model_affordability_frontier(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        down_payment_pcts=(0.05, 0.15),
        income_multipliers=(1.0, 1.15),
        band_label="conservative",
    )
    payload = json.loads(format_affordability_frontier_json(result))
    assert payload["home_price"] == 600_000
    assert payload["band_label"] == "conservative"
    assert len(payload["cells"]) == 4
    assert payload["cells"][0]["check"]["front_end_dti"] > 0
    assert "boundary_cells" in payload


def test_model_affordability_frontier_rejects_invalid_scenario():
    with pytest.raises(ValueError, match="home_price must be positive"):
        model_affordability_frontier(_scenario(home_price=0))


def test_model_affordability_frontier_rejects_empty_sweeps():
    with pytest.raises(ValueError, match="down_payment_pcts must contain"):
        model_affordability_frontier(_scenario(), down_payment_pcts=())
    with pytest.raises(ValueError, match="income_multipliers must contain"):
        model_affordability_frontier(_scenario(), income_multipliers=())


def test_cli_frontier_prints_grid(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "frontier",
            "--price",
            "500000",
            "--income",
            "180000",
            "--debt",
            "200",
            "--band",
            "conservative",
            "--down-pcts",
            "5,15,20",
            "--income-mults",
            "0.85,1.0,1.15",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Down × income affordability frontier" in output
    assert "Minimum down at base income" in output
    assert "Affordability boundary" in output


def test_cli_frontier_json_format(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "frontier",
            "--price",
            "500000",
            "--income",
            "150000",
            "--format",
            "json",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    payload = json.loads(buffer.getvalue())
    assert payload["home_price"] == 500_000
    assert len(payload["cells"]) > 0
