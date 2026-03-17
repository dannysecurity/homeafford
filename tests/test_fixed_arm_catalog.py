"""Tests for preset fixed vs ARM scenario catalog."""

from __future__ import annotations

import pytest

from homeafford.fixed_arm_catalog import (
    analyze_loan_preset,
    compare_purchase_preset,
    default_fixed_arm_catalog,
    format_catalog_listing,
    format_loan_preset_detail,
    format_loan_preset_matrix,
    format_loan_preset_timeline,
    format_purchase_preset_detail,
    format_purchase_preset_matrix,
    purchase_preset_decision_report,
)


def test_default_catalog_lists_six_loan_and_four_purchase_presets():
    catalog = default_fixed_arm_catalog()
    assert catalog.list_loan_ids() == (
        "five_one_standard",
        "seven_one_hold",
        "rate_shock_plus_three",
        "flat_rates",
        "arm_wins_full_term",
        "ten_one_jumbo",
    )
    assert catalog.list_purchase_ids() == (
        "starter_home",
        "dti_tight",
        "high_equity",
        "low_down_starter",
    )


def test_catalog_rejects_unknown_loan_preset():
    catalog = default_fixed_arm_catalog()
    with pytest.raises(ValueError, match="unknown loan preset"):
        catalog.loan_preset("missing")


def test_catalog_rejects_unknown_purchase_preset():
    catalog = default_fixed_arm_catalog()
    with pytest.raises(ValueError, match="unknown purchase preset"):
        catalog.purchase_preset("missing")


def test_analyze_loan_preset_by_id_matches_direct_inputs():
    catalog = default_fixed_arm_catalog()
    preset = catalog.loan_preset("five_one_standard")
    by_id = analyze_loan_preset("five_one_standard", catalog=catalog)
    by_preset = analyze_loan_preset(preset, catalog=catalog)
    assert by_id.arm_savings_during_intro == by_preset.arm_savings_during_intro
    assert by_id.cheaper_over_full_term == by_preset.cheaper_over_full_term


def test_flat_rates_preset_has_zero_intro_savings():
    result = analyze_loan_preset("flat_rates")
    assert result.arm_savings_during_intro == 0.0


def test_arm_wins_full_term_preset_favors_arm():
    result = analyze_loan_preset("arm_wins_full_term")
    assert result.cheaper_over_full_term == "arm"
    assert result.break_even_month is None


def test_rate_shock_preset_has_large_payment_shock():
    result = analyze_loan_preset("rate_shock_plus_three")
    assert result.arm_payment_shock_pct >= 0.25
    assert result.cheaper_over_full_term == "fixed"


def test_dti_tight_purchase_preset_fails_post_adjustment():
    result = compare_purchase_preset("dti_tight")
    assert result.post_adjustment_fails_band is True
    intro_row = next(row for row in result.dti_rows if row.label == "arm_intro")
    assert intro_row.passes_front_end and intro_row.passes_back_end


def test_high_equity_purchase_preset_passes_all_phases():
    result = compare_purchase_preset("high_equity")
    assert result.post_adjustment_fails_band is False
    for row in result.dti_rows:
        assert row.passes_front_end and row.passes_back_end


def test_format_catalog_listing_includes_preset_ids():
    text = format_catalog_listing()
    assert "five_one_standard" in text
    assert "starter_home" in text
    assert "Purchase presets:" in text


def test_format_loan_preset_matrix_lists_all_presets():
    text = format_loan_preset_matrix()
    assert "Loan preset comparison matrix" in text
    for preset_id in default_fixed_arm_catalog().list_loan_ids():
        assert preset_id in text


def test_format_loan_preset_detail_includes_scenario_output():
    text = format_loan_preset_detail("seven_one_hold")
    assert "7/1 ARM" in text
    assert "Monthly P&I" in text


def test_format_purchase_preset_detail_includes_dti_table():
    text = format_purchase_preset_detail("starter_home")
    assert "Fixed vs ARM purchase" in text
    assert "DTI impact" in text


def test_ten_one_jumbo_preset_has_longer_intro_window():
    result = analyze_loan_preset("ten_one_jumbo")
    assert result.inputs.intro_years == 10
    assert result.arm_savings_during_intro > 0


def test_low_down_starter_preset_fails_post_adjustment_dti():
    result = compare_purchase_preset("low_down_starter")
    assert result.post_adjustment_fails_band is True
    intro_row = next(row for row in result.dti_rows if row.label == "arm_intro")
    assert intro_row.passes_front_end and intro_row.passes_back_end


def test_purchase_preset_decision_report_recommends_fixed_for_dti_tight():
    report = purchase_preset_decision_report("dti_tight")
    assert report.recommendation in {"fixed", "arm_with_caution"}


def test_format_purchase_preset_matrix_lists_all_presets():
    text = format_purchase_preset_matrix()
    assert "Purchase preset comparison matrix" in text
    for preset_id in default_fixed_arm_catalog().list_purchase_ids():
        assert preset_id in text
    assert "Decision" in text


def test_format_loan_preset_timeline_includes_year_rows():
    text = format_loan_preset_timeline("five_one_standard")
    assert "Loan preset timeline: five_one_standard" in text
    assert "Fixed vs ARM timeline" in text
    assert "post_adjustment" in text
