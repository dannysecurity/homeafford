"""Tests for ARM post-adjustment rate sensitivity sweeps."""

from __future__ import annotations

from homeafford.arm_sensitivity import (
    format_arm_purchase_sensitivity,
    format_arm_rate_sensitivity,
    sweep_arm_adjusted_rates,
    sweep_arm_adjusted_rates_purchase,
)
from homeafford.check import PurchaseScenario


def test_sweep_arm_adjusted_rates_sorted_and_complete():
    rates = (0.08, 0.06, 0.07)
    result = sweep_arm_adjusted_rates(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        adjusted_rates=rates,
    )
    assert result.adjusted_rates == (0.06, 0.07, 0.08)
    assert len(result.rows) == 3
    assert result.rows[0].arm_adjusted_rate == 0.06
    assert result.rows[-1].post_adjustment_pi >= result.rows[0].post_adjustment_pi


def test_sweep_finds_fixed_wins_from_rate():
    result = sweep_arm_adjusted_rates(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        adjusted_rates=(0.06, 0.07, 0.08, 0.09, 0.10, 0.12),
    )
    assert result.fixed_wins_from_rate is not None
    assert result.arm_always_cheaper is False
    for row in result.rows:
        if row.arm_adjusted_rate < result.fixed_wins_from_rate:
            assert row.cheaper_over_full_term == "arm"
        elif row.arm_adjusted_rate >= result.fixed_wins_from_rate:
            assert row.cheaper_over_full_term == "fixed"


def test_sweep_arm_always_cheaper_when_adjusted_rates_low():
    result = sweep_arm_adjusted_rates(
        principal=400_000,
        term_years=30,
        fixed_rate=0.07,
        arm_intro_rate=0.05,
        adjusted_rates=(0.05, 0.055, 0.06),
    )
    assert result.fixed_wins_from_rate is None
    assert result.arm_always_cheaper is True


def test_sweep_rejects_empty_rates():
    try:
        sweep_arm_adjusted_rates(
            principal=400_000,
            term_years=30,
            fixed_rate=0.065,
            arm_intro_rate=0.055,
            adjusted_rates=(),
        )
    except ValueError as exc:
        assert "adjusted_rates" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty adjusted_rates")


def test_format_arm_rate_sensitivity_includes_summary():
    result = sweep_arm_adjusted_rates(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        adjusted_rates=(0.07, 0.08, 0.09),
    )
    text = format_arm_rate_sensitivity(result)
    assert "ARM post-adjustment rate sensitivity" in text
    assert "Fixed becomes cheaper" in text
    assert "7.00%" in text


def _purchase_scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
        monthly_debt_payments=450.0,
        mortgage_rate=0.065,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_sweep_purchase_tracks_max_rate_passing_dti():
    result = sweep_arm_adjusted_rates_purchase(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        adjusted_rates=(0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12),
        band_label="conservative",
    )
    assert result.max_rate_passing_dti is not None
    assert result.max_rate_passing_dti < 0.12
    passing_rows = [row for row in result.rows if row.post_adjustment_passes_dti]
    failing_rows = [row for row in result.rows if not row.post_adjustment_passes_dti]
    assert passing_rows
    assert failing_rows
    assert max(row.arm_adjusted_rate for row in passing_rows) == result.max_rate_passing_dti


def test_sweep_purchase_post_adjustment_pi_increases_with_rate():
    result = sweep_arm_adjusted_rates_purchase(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        adjusted_rates=(0.07, 0.08, 0.09),
        band_label="conservative",
    )
    payments = [row.post_adjustment_pi for row in result.rows]
    assert payments == sorted(payments)


def test_format_arm_purchase_sensitivity_includes_dti_summary():
    result = sweep_arm_adjusted_rates_purchase(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        adjusted_rates=(0.07, 0.09, 0.11),
        band_label="conservative",
    )
    text = format_arm_purchase_sensitivity(result)
    assert "ARM post-adjustment rate sensitivity (purchase)" in text
    assert "Highest adjusted rate passing DTI" in text
    assert "Back DTI" in text
