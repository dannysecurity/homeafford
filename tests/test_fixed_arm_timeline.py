"""Tests for year-by-year fixed vs ARM timeline analysis."""

from __future__ import annotations

import json

import pytest

from homeafford.fixed_arm_catalog import default_fixed_arm_catalog
from homeafford.fixed_arm_timeline import (
    build_fixed_arm_timeline,
    format_fixed_arm_timeline,
    format_fixed_arm_timeline_json,
)
from homeafford.mortgage_scenario import FixedArmScenarioInputs


def _default_inputs(**overrides) -> FixedArmScenarioInputs:
    defaults = dict(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        intro_years=5,
    )
    defaults.update(overrides)
    return FixedArmScenarioInputs(**defaults)


def test_timeline_row_count_matches_term():
    inputs = _default_inputs(term_years=15)
    result = build_fixed_arm_timeline(inputs)
    assert len(result.yearly_rows) == 15
    assert result.yearly_rows[0].year == 1
    assert result.yearly_rows[-1].year == 15


def test_timeline_intro_phase_before_adjustment_year():
    inputs = _default_inputs(intro_years=5)
    result = build_fixed_arm_timeline(inputs)
    assert result.adjustment_year == 6
    for row in result.yearly_rows[:5]:
        assert row.arm_phase == "intro"
    for row in result.yearly_rows[5:]:
        assert row.arm_phase == "post_adjustment"


def test_timeline_arm_payment_jumps_at_adjustment_year():
    result = build_fixed_arm_timeline(_default_inputs())
    intro_row = result.yearly_rows[4]
    post_row = result.yearly_rows[5]
    assert intro_row.arm_monthly_payment < post_row.arm_monthly_payment
    assert intro_row.arm_monthly_payment == result.scenario.comparison.arm_intro_payment
    assert (
        post_row.arm_monthly_payment
        == result.scenario.comparison.arm_post_adjustment_payment
    )


def test_timeline_cumulative_costs_match_scenario_totals():
    inputs = _default_inputs()
    result = build_fixed_arm_timeline(inputs)
    last = result.yearly_rows[-1]
    assert last.fixed_cumulative_cost == pytest.approx(result.scenario.fixed_total_cost)
    assert last.arm_cumulative_cost == pytest.approx(result.scenario.arm_total_cost)


def test_timeline_years_arm_leads_positive_when_arm_cheaper_early():
    result = build_fixed_arm_timeline(_default_inputs())
    assert result.years_arm_leads > 0
    assert result.peak_arm_savings_amount > 0
    assert result.peak_arm_savings_year is not None


def test_timeline_break_even_year_aligns_with_scenario_month():
    result = build_fixed_arm_timeline(_default_inputs())
    assert result.break_even_year is not None
    month = result.scenario.break_even_month
    assert month is not None
    year = result.break_even_year
    assert (year - 1) * 12 + 1 <= month <= year * 12


def test_timeline_arm_leads_full_term_when_arm_wins():
    inputs = _default_inputs(
        fixed_rate=0.07,
        arm_intro_rate=0.05,
        arm_adjusted_rate=0.055,
    )
    result = build_fixed_arm_timeline(inputs)
    assert result.scenario.cheaper_over_full_term == "arm"
    assert result.years_arm_leads == inputs.term_years
    assert result.break_even_year is None


def test_timeline_fixed_leads_from_year_one_when_no_intro_savings():
    result = build_fixed_arm_timeline(
        _default_inputs(
            arm_intro_rate=0.065,
            arm_adjusted_rate=0.085,
        )
    )
    assert result.years_arm_leads == 0
    assert result.peak_arm_savings_amount == 0.0
    assert not result.yearly_rows[0].arm_still_leads


def test_timeline_rejects_invalid_intro_years():
    try:
        build_fixed_arm_timeline(_default_inputs(intro_years=30))
    except ValueError as exc:
        assert "intro_years" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_format_timeline_includes_markers_and_summary():
    result = build_fixed_arm_timeline(_default_inputs())
    text = format_fixed_arm_timeline(result)
    assert "Fixed vs ARM timeline" in text
    assert "Adjustment year: 6" in text
    assert "Peak ARM savings" in text
    assert "intro" in text
    assert "post_adjustment" in text
    assert "*" in text


def test_format_timeline_json_round_trip():
    result = build_fixed_arm_timeline(_default_inputs())
    payload = json.loads(format_fixed_arm_timeline_json(result))
    assert payload["summary"]["adjustment_year"] == 6
    assert len(payload["yearly_rows"]) == 30
    assert payload["yearly_rows"][4]["arm_phase"] == "intro"
    assert payload["yearly_rows"][5]["arm_phase"] == "post_adjustment"
    assert payload["summary"]["cheaper_over_full_term"] in {"fixed", "arm", "tie"}


def test_timeline_works_with_catalog_preset():
    catalog = default_fixed_arm_catalog()
    preset = catalog.loan_preset("five_one_standard")
    result = build_fixed_arm_timeline(preset.inputs)
    assert len(result.yearly_rows) == preset.inputs.term_years
    assert result.adjustment_year == preset.inputs.intro_years + 1