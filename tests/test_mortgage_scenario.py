from homeafford.check import PurchaseScenario
from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    analyze_fixed_arm_scenario,
    compare_fixed_arm_purchase,
    fixed_arm_decision_report,
    fixed_arm_inputs_from_purchase,
    format_fixed_arm_decision_report,
    format_fixed_arm_decision_report_json,
    format_fixed_arm_purchase_comparison,
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
    assert "5/1 ARM" in text


def test_format_uses_standard_arm_notation_for_seven_one():
    result = analyze_fixed_arm_scenario(_default_inputs(intro_years=7))
    text = format_fixed_arm_scenario(result)
    assert "7/1 ARM" in text
    assert "7/23" not in text


def test_fixed_arm_inputs_from_purchase_derives_loan_and_rates():
    scenario = PurchaseScenario(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
        loan_term_years=30,
        mortgage_rate=0.065,
    )
    inputs = fixed_arm_inputs_from_purchase(
        scenario,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        intro_years=7,
    )
    assert inputs.principal == 400_000
    assert inputs.term_years == 30
    assert inputs.fixed_rate == 0.065
    assert inputs.arm_intro_rate == 0.055
    assert inputs.arm_adjusted_rate == 0.075
    assert inputs.intro_years == 7


def test_fixed_arm_inputs_from_purchase_rejects_all_cash():
    scenario = PurchaseScenario(
        home_price=400_000,
        down_payment=400_000,
        gross_annual_income=150_000,
    )
    try:
        fixed_arm_inputs_from_purchase(
            scenario,
            arm_intro_rate=0.055,
            arm_adjusted_rate=0.075,
        )
    except ValueError as exc:
        assert "principal" in str(exc)
    else:
        raise AssertionError("expected ValueError for all-cash purchase")


def test_fixed_arm_inputs_from_purchase_runs_scenario_analysis():
    scenario = PurchaseScenario(
        home_price=500_000,
        down_payment=100_000,
        gross_annual_income=150_000,
        mortgage_rate=0.065,
    )
    inputs = fixed_arm_inputs_from_purchase(
        scenario,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
    )
    result = analyze_fixed_arm_scenario(inputs)
    assert result.arm_savings_during_intro > 0
    assert result.break_even_month is not None


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


def test_compare_fixed_arm_purchase_dti_rows_cover_all_phases():
    comparison = compare_fixed_arm_purchase(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        band_label="conservative",
    )
    labels = {row.label for row in comparison.dti_rows}
    assert labels == {"fixed", "arm_intro", "arm_post"}
    assert comparison.loan_result.arm_savings_during_intro > 0


def test_compare_fixed_arm_purchase_intro_passes_post_fails_on_high_adjusted_rate():
    comparison = compare_fixed_arm_purchase(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.11,
        band_label="conservative",
    )
    intro = next(row for row in comparison.dti_rows if row.label == "arm_intro")
    post = next(row for row in comparison.dti_rows if row.label == "arm_post")
    assert intro.passes_back_end
    assert not post.passes_back_end
    assert comparison.post_adjustment_fails_band


def test_format_fixed_arm_purchase_includes_dti_warning_when_post_fails():
    comparison = compare_fixed_arm_purchase(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.11,
        band_label="conservative",
    )
    text = format_fixed_arm_purchase_comparison(comparison)
    assert "DTI impact" in text
    assert "Warning: post-adjustment ARM payment exceeds DTI caps" in text


def test_fixed_arm_decision_report_recommends_arm_when_cost_and_dti_favor_it():
    report = fixed_arm_decision_report(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.065,
        band_label="conservative",
    )
    assert report.recommendation == "arm"
    assert report.sensitivity is None
    assert report.recommendation_reasons
    text = format_fixed_arm_decision_report(report)
    assert "Fixed vs ARM decision: ARM" in text
    assert "DTI impact" in text


def test_fixed_arm_decision_report_recommends_fixed_when_post_adjustment_fails_and_fixed_wins():
    report = fixed_arm_decision_report(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.11,
        band_label="conservative",
    )
    assert report.recommendation == "fixed"
    assert any("exceeds" in reason for reason in report.recommendation_reasons)


def test_fixed_arm_decision_report_with_sweep_includes_sensitivity():
    report = fixed_arm_decision_report(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.065,
        band_label="conservative",
        sweep_adjusted_rates=(0.07, 0.09, 0.11),
    )
    assert report.sensitivity is not None
    assert len(report.sensitivity.rows) == 3
    text = format_fixed_arm_decision_report(report)
    assert "ARM post-adjustment rate sensitivity (purchase)" in text


def test_format_fixed_arm_decision_report_json_includes_recommendation():
    report = fixed_arm_decision_report(
        _purchase_scenario(),
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.065,
        band_label="conservative",
        sweep_adjusted_rates=(0.07, 0.09),
    )
    import json

    payload = json.loads(format_fixed_arm_decision_report_json(report))
    assert payload["recommendation"] == report.recommendation
    assert "purchase" in payload
    assert "loan" in payload["purchase"]
    assert "sensitivity" in payload
    assert payload["sensitivity"]["max_rate_passing_dti"] is not None
