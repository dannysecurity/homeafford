import json
from contextlib import redirect_stdout
from io import StringIO

import pytest

from homeafford.affordability_summary import (
    format_purchase_affordability_summary,
    format_purchase_affordability_summary_json,
    summarize_purchase_affordability,
)
from homeafford.check import PurchaseScenario, check_against_band
from homeafford.cli import main
from homeafford.model import min_down_payment_for_dti


def _scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=600_000,
        down_payment=30_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_summary_passing_purchase_includes_headroom_binding():
    summary = summarize_purchase_affordability(
        _scenario(down_payment=120_000, gross_annual_income=200_000, monthly_debt_payments=0),
        band_label="conservative",
    )
    assert summary.check.passes
    assert summary.binding_constraint in {"front_end", "back_end", "down_payment"}
    assert any("passes" in rec.lower() for rec in summary.recommendations)


def test_summary_failing_dti_reports_down_payment_gap():
    summary = summarize_purchase_affordability(_scenario(), band_label="conservative")
    assert not summary.check.passes
    assert summary.min_down_payment_for_dti is not None
    assert summary.down_payment_gap is not None
    assert summary.down_payment_gap > 0
    assert summary.down_payment_gap == summary.min_down_payment_for_dti - 30_000
    assert any("Increase down payment" in rec for rec in summary.recommendations)


def test_summary_min_down_matches_solver_at_boundary():
    scenario = _scenario()
    summary = summarize_purchase_affordability(scenario, band_label="conservative")
    min_down = min_down_payment_for_dti(scenario, band_label="conservative")
    assert summary.min_down_payment_for_dti == min_down

    just_below = min_down - 500
    below = check_against_band(
        PurchaseScenario(
            home_price=scenario.home_price,
            down_payment=just_below,
            gross_annual_income=scenario.gross_annual_income,
            monthly_debt_payments=scenario.monthly_debt_payments,
        ),
        band_label="conservative",
    )
    at_min = check_against_band(
        PurchaseScenario(
            home_price=scenario.home_price,
            down_payment=min_down,
            gross_annual_income=scenario.gross_annual_income,
            monthly_debt_payments=scenario.monthly_debt_payments,
        ),
        band_label="conservative",
    )
    assert not below.passes_front_end or not below.passes_back_end
    assert at_min.passes_front_end
    assert at_min.passes_back_end


def test_summary_unreachable_dti_reports_debt_message():
    summary = summarize_purchase_affordability(
        _scenario(monthly_debt_payments=5_000),
        band_label="conservative",
    )
    assert summary.min_down_payment_for_dti is None
    assert any("no down payment level" in rec for rec in summary.recommendations)


def test_summary_down_floor_only_suggests_minimum_down():
    summary = summarize_purchase_affordability(
        _scenario(
            home_price=500_000,
            down_payment=10_000,
            gross_annual_income=500_000,
            monthly_debt_payments=0,
        ),
        band_label="conservative",
    )
    assert summary.check.passes_front_end
    assert summary.check.passes_back_end
    assert not summary.check.passes_down_payment
    assert any("down payment floor" in rec for rec in summary.recommendations)


def test_format_summary_json_includes_recommendations():
    summary = summarize_purchase_affordability(_scenario(), band_label="conservative")
    payload = json.loads(format_purchase_affordability_summary_json(summary))
    assert payload["binding_constraint"] in {"front_end", "back_end", "down_payment", "pass"}
    assert payload["recommendations"]
    assert payload["check"]["passes"] is False


def test_format_summary_table_includes_key_fields():
    summary = summarize_purchase_affordability(_scenario(), band_label="conservative")
    text = format_purchase_affordability_summary(summary)
    assert "Affordability summary" in text
    assert "Min down for DTI" in text
    assert "Recommendations:" in text


def test_cli_check_recommend_flag(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "check",
            "--price",
            "600000",
            "--down",
            "30000",
            "--income",
            "120000",
            "--debt",
            "450",
            "--recommend",
        ],
    )
    buffer = StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Affordability summary" in output
    assert "Min down for DTI" in output
    assert "Recommendations:" in output


def test_cli_check_recommend_json(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "check",
            "--price",
            "600000",
            "--down",
            "30000",
            "--income",
            "120000",
            "--recommend",
            "--format",
            "json",
        ],
    )
    buffer = StringIO()
    with redirect_stdout(buffer):
        main()
    payload = json.loads(buffer.getvalue())
    assert payload["home_price"] == 600_000
    assert "recommendations" in payload
    assert "binding_constraint" in payload


def test_summarize_rejects_invalid_scenario():
    with pytest.raises(ValueError, match="home_price must be positive"):
        summarize_purchase_affordability(_scenario(home_price=-1))
