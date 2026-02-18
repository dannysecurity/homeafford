"""Tests for DTI binding analysis and income sensitivity."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from homeafford.check import PurchaseScenario, check_against_band
from homeafford.cli import main
from homeafford.dti_analysis import (
    analyze_dti_binding,
    diagnose_down_payment_affordability,
    format_dti_binding_analysis,
    format_down_payment_affordability_diagnostic,
    format_income_dti_sensitivity,
    min_income_for_dti,
    model_income_dti_sensitivity,
)


def _scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=500_000,
        down_payment=50_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_binding_marks_front_end_when_housing_costs_dominate():
    binding = analyze_dti_binding(
        _scenario(home_price=600_000, gross_annual_income=100_000, monthly_debt_payments=200),
        down_payment_pcts=(0.05, 0.20),
        band_label="conservative",
    )
    low = binding.rows[0]
    assert low.binding in ("front_end", "back_end")
    assert low.margins.front_end_headroom < low.margins.back_end_headroom or not low.check.passes_front_end


def test_binding_marks_down_payment_when_dti_passes_but_floor_fails():
    binding = analyze_dti_binding(
        _scenario(
            home_price=400_000,
            gross_annual_income=200_000,
            monthly_debt_payments=0,
        ),
        down_payment_pcts=(0.02, 0.20),
        band_label="conservative",
    )
    low, high = binding.rows
    assert low.check.passes_front_end and low.check.passes_back_end
    assert not low.check.passes
    assert low.binding == "down_payment"
    assert high.binding in ("front_end", "back_end", "down_payment", "pass")


def test_binding_reports_first_dti_pass_down_pct():
    binding = analyze_dti_binding(
        _scenario(home_price=500_000, gross_annual_income=150_000, monthly_debt_payments=400),
        down_payment_pcts=(0.05, 0.10, 0.20),
        band_label="conservative",
    )
    assert binding.first_dti_pass_down_pct is not None
    assert binding.binding_at_min_down is not None


def test_format_dti_binding_analysis_includes_headroom_columns():
    binding = analyze_dti_binding(_scenario(), down_payment_pcts=(0.05, 0.20))
    text = format_dti_binding_analysis(binding)
    assert "DTI binding analysis" in text
    assert "Front Δ" in text
    assert "Binding" in text
    assert "5.0%" in text


def test_min_income_for_dti_at_boundary():
    scenario = _scenario(
        home_price=600_000,
        down_payment=120_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
    )
    min_income = min_income_for_dti(scenario, band_label="conservative")
    assert min_income is not None
    just_below = min_income - 500
    result_below = check_against_band(
        PurchaseScenario(
            home_price=scenario.home_price,
            down_payment=scenario.down_payment,
            gross_annual_income=just_below,
            monthly_debt_payments=scenario.monthly_debt_payments,
        ),
        band_label="conservative",
    )
    assert not result_below.passes_front_end or not result_below.passes_back_end
    result_at = check_against_band(
        PurchaseScenario(
            home_price=scenario.home_price,
            down_payment=scenario.down_payment,
            gross_annual_income=min_income,
            monthly_debt_payments=scenario.monthly_debt_payments,
        ),
        band_label="conservative",
    )
    assert result_at.passes_front_end
    assert result_at.passes_back_end


def test_model_income_dti_sensitivity_reports_min_income():
    sensitivity = model_income_dti_sensitivity(
        _scenario(home_price=600_000, down_payment=60_000, gross_annual_income=120_000),
        income_multipliers=(0.8, 1.0, 1.2),
        band_label="conservative",
    )
    assert len(sensitivity.rows) == 3
    assert sensitivity.min_income is not None
    assert sensitivity.min_income_multiplier is not None
    low_income_row = sensitivity.rows[0]
    assert low_income_row.income_multiplier == 0.8


def test_format_income_dti_sensitivity_includes_multiplier_and_min():
    sensitivity = model_income_dti_sensitivity(
        _scenario(),
        income_multipliers=(1.0,),
        band_label="conservative",
    )
    text = format_income_dti_sensitivity(sensitivity)
    assert "Income DTI sensitivity" in text
    assert "Minimum income for DTI pass" in text
    assert "1.00x" in text


def test_diagnose_down_payment_affordability_combines_sections():
    diagnostic = diagnose_down_payment_affordability(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        down_payment_pcts=(0.05, 0.15, 0.20),
        band_label="conservative",
    )
    assert diagnostic.dti_model.min_down_payment is not None
    assert diagnostic.binding.rows
    assert diagnostic.income_sensitivity is not None
    text = format_down_payment_affordability_diagnostic(diagnostic)
    assert "Down payment vs DTI model" in text
    assert "DTI binding analysis" in text
    assert "Income DTI sensitivity" in text


def test_diagnose_unreachable_skips_income_sensitivity():
    diagnostic = diagnose_down_payment_affordability(
        _scenario(gross_annual_income=60_000, monthly_debt_payments=2_500),
        band_label="conservative",
    )
    assert diagnostic.dti_model.min_down_payment is None
    assert diagnostic.income_sensitivity is None


def test_analyze_dti_binding_rejects_invalid_scenario():
    with pytest.raises(ValueError, match="home_price must be positive"):
        analyze_dti_binding(_scenario(home_price=0))


def test_cli_analyze_dti_prints_binding_and_income_sections(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "analyze-dti",
            "--price",
            "600000",
            "--income",
            "120000",
            "--debt",
            "450",
            "--band",
            "conservative",
            "--down-pcts",
            "5,15,20",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Down payment vs DTI model" in output
    assert "DTI binding analysis" in output
    assert "Income DTI sensitivity" in output
    assert "Binding" in output
