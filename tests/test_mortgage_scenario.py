from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    analyze_fixed_arm_scenario,
    format_fixed_arm_scenario,
)


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


def test_scenario_arm_saves_during_intro_when_intro_rate_lower():
    result = analyze_fixed_arm_scenario(_default_inputs())
    assert result.arm_savings_during_intro > 0
    assert result.comparison.arm_intro_payment < result.comparison.fixed_payment


def test_scenario_payment_shock_positive_when_adjusted_rate_higher():
    result = analyze_fixed_arm_scenario(_default_inputs())
    assert result.arm_payment_shock_dollars > 0
    assert result.arm_payment_shock_pct > 0
    assert (
        result.comparison.arm_post_adjustment_payment
        > result.comparison.arm_intro_payment
    )


def test_scenario_total_costs_match_payment_schedule():
    inputs = _default_inputs()
    result = analyze_fixed_arm_scenario(inputs)
    intro_months = inputs.intro_years * 12
    total_months = inputs.term_years * 12
    expected_arm = (
        result.comparison.arm_intro_payment * intro_months
        + result.comparison.arm_post_adjustment_payment * (total_months - intro_months)
    )
    assert result.arm_total_cost == expected_arm
    assert result.fixed_total_cost == result.comparison.fixed_payment * total_months


def test_scenario_break_even_occurs_after_intro_when_rates_rise():
    result = analyze_fixed_arm_scenario(_default_inputs())
    assert result.break_even_month is not None
    assert result.break_even_month > _default_inputs().intro_years * 12


def test_scenario_fixed_cheaper_when_adjusted_rate_extreme():
    result = analyze_fixed_arm_scenario(
        _default_inputs(arm_adjusted_rate=0.12, arm_intro_rate=0.05)
    )
    assert result.cheaper_over_full_term == "fixed"
    assert result.arm_total_cost > result.fixed_total_cost


def test_scenario_arm_cheaper_when_adjusted_rate_stays_low():
    result = analyze_fixed_arm_scenario(
        _default_inputs(
            fixed_rate=0.07,
            arm_intro_rate=0.05,
            arm_adjusted_rate=0.055,
        )
    )
    assert result.cheaper_over_full_term == "arm"


def test_scenario_rejects_invalid_principal():
    try:
        analyze_fixed_arm_scenario(_default_inputs(principal=0))
    except ValueError as exc:
        assert "principal" in str(exc)
    else:
        raise AssertionError("expected ValueError for zero principal")


def test_format_includes_key_labels():
    result = analyze_fixed_arm_scenario(_default_inputs())
    text = format_fixed_arm_scenario(result)
    assert "Monthly P&I" in text
    assert "Break-even" in text
    assert "Cheaper over full term" in text


def test_format_break_even_calendar_label_uses_one_indexed_year_and_month():
    result = analyze_fixed_arm_scenario(_default_inputs())
    assert result.break_even_month is not None
    text = format_fixed_arm_scenario(result)
    year_num = (result.break_even_month - 1) // 12 + 1
    month_num = (result.break_even_month - 1) % 12 + 1
    assert (
        f"month {result.break_even_month} (year {year_num}, month {month_num})"
        in text
    )
