"""Edge-case coverage for mortgage, PITI, savings, purchase, and ARM calculators."""

import pytest

from homeafford.check import (
    check_affordability,
    check_against_band,
    check_purchase_readiness,
)
from homeafford.mortgage import (
    compare_fixed_vs_arm,
    format_arm_label,
    mortgage_payment,
    remaining_balance,
    total_interest,
)
from homeafford.mortgage_scenario import (
    analyze_fixed_arm_scenario,
    compare_fixed_arm_purchase,
    fixed_arm_inputs_from_purchase,
    format_fixed_arm_scenario,
)
from homeafford.piti import compute_dti_ratios, compute_piti
from homeafford.pmi import compute_pmi_monthly, pmi_required
from homeafford.savings import savings_trajectory
from tests.helpers.edge_case_catalog import EdgeCaseCatalog, fixed_arm_inputs, purchase_scenario


def test_mortgage_payment_rejects_non_positive_principal():
    with pytest.raises(ValueError, match="principal must be positive"):
        mortgage_payment(principal=0, annual_rate=0.05, term_years=30)
    with pytest.raises(ValueError, match="principal must be positive"):
        mortgage_payment(principal=-1, annual_rate=0.05, term_years=30)


def test_mortgage_payment_rejects_non_positive_term():
    with pytest.raises(ValueError, match="term_years must be positive"):
        mortgage_payment(principal=100_000, annual_rate=0.05, term_years=0)


def test_remaining_balance_at_start_equals_principal():
    balance = remaining_balance(
        principal=250_000,
        annual_rate=0.06,
        term_years=30,
        months_paid=0,
    )
    assert balance == 250_000


def test_remaining_balance_zero_after_full_term():
    balance = remaining_balance(
        principal=200_000,
        annual_rate=0.05,
        term_years=15,
        months_paid=15 * 12,
    )
    assert balance == 0.0


def test_remaining_balance_zero_beyond_full_term():
    balance = remaining_balance(
        principal=200_000,
        annual_rate=0.05,
        term_years=15,
        months_paid=15 * 12 + 6,
    )
    assert balance == 0.0


def test_remaining_balance_rejects_negative_months_paid():
    with pytest.raises(ValueError, match="months_paid must be non-negative"):
        remaining_balance(
            principal=200_000,
            annual_rate=0.05,
            term_years=30,
            months_paid=-1,
        )


def test_total_interest_zero_for_zero_rate():
    assert total_interest(principal=150_000, annual_rate=0.0, term_years=30) == 0.0


def test_compare_fixed_vs_arm_rejects_non_positive_intro_years():
    with pytest.raises(ValueError, match="intro_years must be positive"):
        compare_fixed_vs_arm(
            principal=400_000,
            term_years=30,
            fixed_rate=0.065,
            arm_intro_rate=0.055,
            arm_adjusted_rate=0.075,
            intro_years=0,
        )


def test_savings_trajectory_empty_when_zero_months():
    assert savings_trajectory(
        starting_balance=5_000,
        monthly_contribution=100,
        annual_return=0.04,
        months=0,
    ) == []


def test_savings_trajectory_rejects_negative_months():
    with pytest.raises(ValueError, match="months must be non-negative"):
        savings_trajectory(
            starting_balance=5_000,
            monthly_contribution=100,
            annual_return=0.04,
            months=-1,
        )


def test_savings_trajectory_rejects_negative_inputs():
    with pytest.raises(
        ValueError,
        match="starting_balance and monthly_contribution must be non-negative",
    ):
        savings_trajectory(
            starting_balance=-1,
            monthly_contribution=100,
            annual_return=0.04,
            months=12,
        )


def test_compute_piti_zero_loan_has_no_principal_and_interest():
    breakdown = compute_piti(
        loan_amount=0,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=50,
        mortgage_rate=0.065,
        loan_term_years=30,
    )
    assert breakdown.principal_and_interest == 0.0
    assert breakdown.piti == breakdown.insurance_monthly + breakdown.hoa_monthly


def test_compute_piti_rejects_negative_loan_amount():
    with pytest.raises(ValueError, match="loan_amount must be non-negative"):
        compute_piti(
            loan_amount=-1,
            property_tax_rate=0.012,
            insurance_annual=1_200,
            hoa_monthly=0,
            mortgage_rate=0.065,
            loan_term_years=30,
        )


def test_compute_dti_ratios_zero_when_income_non_positive():
    assert compute_dti_ratios(
        piti=2_000,
        gross_annual_income=0,
        monthly_debt_payments=500,
    ) == (0.0, 0.0)


def test_compute_dti_ratios_zero_when_income_negative():
    assert compute_dti_ratios(
        piti=2_000,
        gross_annual_income=-50_000,
        monthly_debt_payments=500,
    ) == (0.0, 0.0)


def test_remaining_balance_zero_rate_linear_paydown():
    balance = remaining_balance(
        principal=120_000,
        annual_rate=0.0,
        term_years=10,
        months_paid=60,
    )
    assert balance == pytest.approx(60_000)


def test_mortgage_payment_zero_rate_divides_evenly():
    payment = mortgage_payment(principal=360_000, annual_rate=0.0, term_years=30)
    assert payment == pytest.approx(1_000)


def test_savings_trajectory_compounds_annual_return():
    snaps = savings_trajectory(
        starting_balance=1_000,
        monthly_contribution=0,
        annual_return=0.12,
        months=12,
    )
    assert snaps[-1].balance == pytest.approx(1_120, rel=1e-9)
    assert snaps[-1].growth > 0


def test_savings_trajectory_rejects_negative_contribution():
    with pytest.raises(
        ValueError,
        match="starting_balance and monthly_contribution must be non-negative",
    ):
        savings_trajectory(
            starting_balance=1_000,
            monthly_contribution=-50,
            annual_return=0.04,
            months=6,
        )


def test_compute_piti_zero_rate_on_nonzero_loan():
    breakdown = compute_piti(
        loan_amount=240_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.0,
        loan_term_years=30,
    )
    assert breakdown.principal_and_interest == pytest.approx(666.67, rel=1e-3)
    assert breakdown.piti == pytest.approx(
        breakdown.principal_and_interest
        + breakdown.tax_monthly
        + breakdown.insurance_monthly,
        rel=1e-9,
    )


def test_compare_fixed_vs_arm_equal_intro_and_fixed_rates():
    comparison = compare_fixed_vs_arm(
        principal=300_000,
        term_years=30,
        fixed_rate=0.06,
        arm_intro_rate=0.06,
        arm_adjusted_rate=0.07,
        intro_years=5,
    )
    assert comparison.fixed_payment == pytest.approx(comparison.arm_intro_payment)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("home_price", 0, "home_price must be positive"),
        ("down_payment", -1, "down_payment must be non-negative"),
        ("gross_annual_income", 0, "gross_annual_income must be positive"),
        ("closing_costs", -100, "closing_costs must be non-negative"),
    ],
)
def test_purchase_scenario_validation(field, value, message):
    overrides = {field: value}
    if field == "down_payment" and value < 0:
        overrides["home_price"] = 500_000
    with pytest.raises(ValueError, match=message):
        check_affordability(purchase_scenario(**overrides))


def test_purchase_scenario_rejects_down_payment_exceeding_price():
    with pytest.raises(ValueError, match="down_payment cannot exceed home_price"):
        check_affordability(
            purchase_scenario(home_price=300_000, down_payment=350_000)
        )


def test_check_fails_front_end_while_back_end_passes(edge_cases: EdgeCaseCatalog):
    result = check_affordability(
        edge_cases.front_end_failure,
        front_end_cap=0.28,
        back_end_cap=0.43,
    )
    assert not result.passes_front_end
    assert result.passes_back_end
    assert any("front-end DTI" in reason for reason in result.reasons)


def test_check_all_cash_purchase_has_zero_loan(edge_cases: EdgeCaseCatalog):
    result = check_affordability(edge_cases.all_cash_purchase)
    assert result.loan_amount == 0.0
    assert result.estimated_piti == pytest.approx(
        edge_cases.all_cash_purchase.insurance_annual / 12
        + edge_cases.all_cash_purchase.hoa_monthly,
        rel=1e-6,
    )


def test_check_pmi_not_required_at_exactly_eighty_percent_ltv(edge_cases: EdgeCaseCatalog):
    result = check_affordability(edge_cases.pmi_threshold_ltv)
    assert result.ltv == pytest.approx(0.8)
    assert not result.pmi_required


def test_purchase_readiness_already_funded_returns_zero_months():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=50_000, closing_costs=5_000),
        starting_balance=60_000,
        monthly_contribution=0,
    )
    assert readiness.passes_savings
    assert readiness.months_until_ready is None


def test_purchase_readiness_unreachable_goal_returns_none():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=200_000, closing_costs=20_000),
        starting_balance=1_000,
        monthly_contribution=100,
        annual_return=0.0,
    )
    assert not readiness.passes_savings
    assert readiness.months_until_ready is None


def test_purchase_readiness_with_target_months():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=60_000, closing_costs=10_000),
        starting_balance=20_000,
        monthly_contribution=5_000,
        annual_return=0.0,
        target_months=12,
    )
    assert readiness.projected_balance == pytest.approx(80_000)
    assert readiness.passes_savings
    assert readiness.cash_required == 70_000
    assert readiness.months_until_ready is None


def test_purchase_readiness_rejects_negative_savings_inputs():
    with pytest.raises(
        ValueError,
        match="starting_balance and monthly_contribution must be non-negative",
    ):
        check_purchase_readiness(
            purchase_scenario(),
            starting_balance=-1,
            monthly_contribution=500,
        )


def test_arm_scenario_no_break_even_when_arm_always_cheaper(edge_cases: EdgeCaseCatalog):
    result = analyze_fixed_arm_scenario(edge_cases.arm_always_cheaper)
    assert result.break_even_month is None
    assert result.cheaper_over_full_term == "arm"


def test_arm_scenario_tie_when_total_costs_equal(edge_cases: EdgeCaseCatalog):
    result = analyze_fixed_arm_scenario(edge_cases.flat_arm_rates)
    assert result.cheaper_over_full_term == "tie"
    assert result.arm_savings_during_intro == pytest.approx(0.0)


def test_arm_scenario_rejects_non_positive_term():
    with pytest.raises(ValueError, match="term_years must be positive"):
        analyze_fixed_arm_scenario(fixed_arm_inputs(term_years=0))


def test_arm_scenario_rejects_intro_years_not_shorter_than_term():
    with pytest.raises(ValueError, match="intro_years must be less than term_years"):
        analyze_fixed_arm_scenario(fixed_arm_inputs(intro_years=30, term_years=30))


def test_arm_seven_one_longer_intro_accumulates_more_savings(edge_cases: EdgeCaseCatalog):
    seven_one = analyze_fixed_arm_scenario(edge_cases.arm_seven_one)
    five_one = analyze_fixed_arm_scenario(
        fixed_arm_inputs(
            fixed_rate=0.0625,
            arm_intro_rate=0.0525,
            arm_adjusted_rate=0.0725,
            intro_years=5,
        )
    )
    assert seven_one.inputs.intro_years == 7
    assert seven_one.arm_savings_during_intro > five_one.arm_savings_during_intro
    assert seven_one.break_even_month is not None
    assert seven_one.break_even_month > five_one.break_even_month


def test_format_arm_scenario_without_break_even():
    result = analyze_fixed_arm_scenario(
        fixed_arm_inputs(
            fixed_rate=0.07,
            arm_intro_rate=0.05,
            arm_adjusted_rate=0.055,
        )
    )
    text = format_fixed_arm_scenario(result)
    assert "ARM never exceeds fixed cumulative cost" in text


def test_remaining_balance_monotonic_decrease():
    principal = 280_000
    annual_rate = 0.055
    term_years = 30
    prior = principal
    for months_paid in range(1, term_years * 12):
        balance = remaining_balance(
            principal=principal,
            annual_rate=annual_rate,
            term_years=term_years,
            months_paid=months_paid,
        )
        assert balance < prior
        prior = balance


def test_total_interest_matches_amortization_formula():
    principal = 220_000
    annual_rate = 0.0625
    term_years = 30
    payment = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    )
    interest = total_interest(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    )
    assert interest == pytest.approx(payment * term_years * 12 - principal)


def test_compare_fixed_vs_arm_rejects_intro_not_shorter_than_term():
    with pytest.raises(ValueError, match="intro_years must be less than term_years"):
        compare_fixed_vs_arm(
            principal=300_000,
            term_years=15,
            fixed_rate=0.06,
            arm_intro_rate=0.05,
            arm_adjusted_rate=0.07,
            intro_years=15,
        )


def test_compute_piti_uses_principal_and_interest_override():
    override_payment = 1_850.0
    breakdown = compute_piti(
        loan_amount=320_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=75,
        mortgage_rate=0.065,
        loan_term_years=30,
        principal_and_interest=override_payment,
    )
    assert breakdown.principal_and_interest == override_payment
    assert breakdown.piti == pytest.approx(
        override_payment
        + breakdown.tax_monthly
        + breakdown.insurance_monthly
        + breakdown.hoa_monthly,
        rel=1e-9,
    )


def test_compute_piti_mortgage_insurance_always_at_eighty_ltv():
    breakdown = compute_piti(
        loan_amount=400_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.005,
        pmi_ltv_threshold=0.80,
        mortgage_insurance_always=True,
    )
    assert breakdown.pmi_monthly == pytest.approx(400_000 * 0.005 / 12)


def test_compute_dti_ratios_front_end_equals_back_end_with_no_debt():
    piti = 2_400
    front_end, back_end = compute_dti_ratios(
        piti=piti,
        gross_annual_income=120_000,
        monthly_debt_payments=0,
    )
    assert front_end == pytest.approx(back_end)
    assert front_end == pytest.approx(piti / (120_000 / 12))


def test_check_back_end_failure_while_front_end_passes(edge_cases: EdgeCaseCatalog):
    result = check_affordability(
        edge_cases.back_end_failure,
        front_end_cap=0.28,
        back_end_cap=0.36,
    )
    assert result.passes_front_end
    assert not result.passes_back_end
    assert any("back-end DTI" in reason for reason in result.reasons)


def test_check_passes_at_exact_minimum_down_payment(edge_cases: EdgeCaseCatalog):
    result = check_affordability(edge_cases.minimum_down_payment)
    assert result.down_payment_pct == pytest.approx(0.03)
    assert result.passes_down_payment


def test_purchase_readiness_rejects_negative_target_months():
    with pytest.raises(ValueError, match="target_months must be non-negative"):
        check_purchase_readiness(
            purchase_scenario(),
            starting_balance=10_000,
            monthly_contribution=500,
            target_months=-1,
        )


def test_purchase_readiness_one_dollar_short_needs_one_month():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=50_000, closing_costs=5_000),
        starting_balance=54_999,
        monthly_contribution=1,
        annual_return=0.0,
    )
    assert readiness.cash_required == 55_000
    assert not readiness.passes_savings
    assert readiness.months_until_ready == 1


def test_savings_trajectory_negative_return_erodes_balance_without_contributions():
    snaps = savings_trajectory(
        starting_balance=10_000,
        monthly_contribution=0,
        annual_return=-0.12,
        months=12,
    )
    assert snaps[-1].balance < 10_000
    assert all(snap.growth <= 0 for snap in snaps)


def test_arm_scenario_break_even_when_adjusted_rate_spikes(edge_cases: EdgeCaseCatalog):
    result = analyze_fixed_arm_scenario(edge_cases.arm_rate_spike)
    assert result.break_even_month is not None
    assert result.break_even_month > edge_cases.arm_rate_spike.intro_years * 12
    assert result.cheaper_over_full_term == "fixed"
    assert result.arm_payment_shock_pct > 0.5


def test_mortgage_payment_shorter_term_raises_monthly_payment():
    principal = 300_000
    annual_rate = 0.06
    thirty_year = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=30
    )
    fifteen_year = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=15
    )
    assert fifteen_year > thirty_year
    assert total_interest(
        principal=principal, annual_rate=annual_rate, term_years=15
    ) < total_interest(principal=principal, annual_rate=annual_rate, term_years=30)


def test_purchase_readiness_projects_months_until_goal(edge_cases: EdgeCaseCatalog):
    readiness = check_purchase_readiness(
        edge_cases.savings_reachable,
        starting_balance=5_000,
        monthly_contribution=2_000,
        annual_return=0.0,
    )
    assert readiness.cash_required == 43_000
    assert not readiness.passes_savings
    assert readiness.months_until_ready == 19


def test_mortgage_payment_rejects_negative_term_years():
    with pytest.raises(ValueError, match="term_years must be positive"):
        mortgage_payment(principal=100_000, annual_rate=0.05, term_years=-1)


def test_remaining_balance_one_month_before_payoff_still_positive():
    balance = remaining_balance(
        principal=200_000,
        annual_rate=0.05,
        term_years=15,
        months_paid=15 * 12 - 1,
    )
    assert balance > 0
    assert balance < mortgage_payment(
        principal=200_000, annual_rate=0.05, term_years=15
    )


def test_compute_piti_omits_pmi_without_home_price():
    breakdown = compute_piti(
        loan_amount=450_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
        pmi_annual_rate=0.005,
    )
    assert breakdown.pmi_monthly == 0.0


def test_compute_dti_ratios_zero_piti_yields_zero_ratios():
    assert compute_dti_ratios(
        piti=0,
        gross_annual_income=120_000,
        monthly_debt_payments=500,
    ) == (0.0, pytest.approx(500 / 10_000))


def test_purchase_readiness_target_months_zero_uses_current_balance():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=50_000, closing_costs=5_000),
        starting_balance=54_999,
        monthly_contribution=10_000,
        annual_return=0.12,
        target_months=0,
    )
    assert readiness.projected_balance == 54_999
    assert not readiness.passes_savings


def test_compare_fixed_vs_arm_zero_adjusted_rate_lowers_post_payment():
    comparison = compare_fixed_vs_arm(
        principal=300_000,
        term_years=30,
        fixed_rate=0.06,
        arm_intro_rate=0.05,
        arm_adjusted_rate=0.0,
        intro_years=5,
    )
    assert comparison.arm_post_adjustment_payment < comparison.arm_intro_payment


def test_savings_trajectory_month_indices_are_one_based():
    snaps = savings_trajectory(
        starting_balance=1_000,
        monthly_contribution=100,
        annual_return=0.0,
        months=3,
    )
    assert [snap.month for snap in snaps] == [1, 2, 3]
    assert snaps[0].balance == pytest.approx(1_100)


def test_arm_scenario_rejects_non_positive_principal():
    with pytest.raises(ValueError, match="principal must be positive"):
        analyze_fixed_arm_scenario(fixed_arm_inputs(principal=0))


def test_format_arm_label_supports_common_hybrid_variants():
    assert format_arm_label(5) == "5/1 ARM"
    assert format_arm_label(7) == "7/1 ARM"
    assert format_arm_label(10, adjustment_years=6) == "10/6 ARM"


def test_pmi_required_at_borderline_ltv(edge_cases: EdgeCaseCatalog):
    scenario = edge_cases.borderline_pmi_ltv
    loan_amount = scenario.home_price - scenario.down_payment
    ltv = loan_amount / scenario.home_price
    assert ltv == pytest.approx(0.8001, rel=1e-6)
    assert pmi_required(loan_amount=loan_amount, home_price=scenario.home_price)
    assert compute_pmi_monthly(
        loan_amount=loan_amount,
        home_price=scenario.home_price,
        pmi_annual_rate=0.005,
    ) == pytest.approx(loan_amount * 0.005 / 12)


def test_check_affordability_includes_pmi_for_borderline_ltv(edge_cases: EdgeCaseCatalog):
    result = check_affordability(edge_cases.borderline_pmi_ltv)
    assert result.pmi_required
    assert result.estimated_pmi_monthly > 0
    assert result.estimated_piti > result.estimated_pmi_monthly


def test_check_against_band_unknown_label_raises():
    with pytest.raises(ValueError, match="unknown band"):
        check_against_band(purchase_scenario(), band_label="ultra-stretch")


def test_check_affordability_band_label_overrides_explicit_caps(edge_cases: EdgeCaseCatalog):
    custom = check_affordability(
        edge_cases.exact_front_end_cap,
        front_end_cap=0.10,
        back_end_cap=0.10,
    )
    conservative = check_affordability(
        edge_cases.exact_front_end_cap,
        band_label="conservative",
    )
    assert custom.front_end_dti == conservative.front_end_dti
    assert custom.passes_front_end != conservative.passes_front_end


def test_high_hoa_increases_piti_without_changing_loan(edge_cases: EdgeCaseCatalog):
    baseline = check_affordability(
        purchase_scenario(
            home_price=edge_cases.high_hoa_purchase.home_price,
            down_payment=edge_cases.high_hoa_purchase.down_payment,
            gross_annual_income=edge_cases.high_hoa_purchase.gross_annual_income,
            hoa_monthly=0,
        )
    )
    with_hoa = check_affordability(edge_cases.high_hoa_purchase)
    assert with_hoa.loan_amount == baseline.loan_amount
    assert with_hoa.estimated_piti == pytest.approx(
        baseline.estimated_piti + edge_cases.high_hoa_purchase.hoa_monthly
    )


def test_fixed_arm_inputs_from_purchase_derives_principal_and_rates():
    scenario = purchase_scenario(
        home_price=480_000,
        down_payment=96_000,
        mortgage_rate=0.0625,
        loan_term_years=15,
    )
    inputs = fixed_arm_inputs_from_purchase(
        scenario,
        arm_intro_rate=0.0525,
        arm_adjusted_rate=0.0725,
        intro_years=7,
    )
    assert inputs.principal == 384_000
    assert inputs.fixed_rate == scenario.mortgage_rate
    assert inputs.term_years == 15
    assert inputs.intro_years == 7


def test_fixed_arm_inputs_from_purchase_rejects_all_cash():
    with pytest.raises(ValueError, match="principal must be positive"):
        fixed_arm_inputs_from_purchase(
            purchase_scenario(home_price=300_000, down_payment=300_000),
            arm_intro_rate=0.05,
            arm_adjusted_rate=0.07,
        )


def test_compare_fixed_arm_purchase_flags_post_adjustment_dti_failure(
    edge_cases: EdgeCaseCatalog,
):
    comparison = compare_fixed_arm_purchase(
        edge_cases.arm_post_dti_failure,
        arm_intro_rate=0.0525,
        arm_adjusted_rate=0.095,
        intro_years=5,
        band_label="conservative",
    )
    intro_row = next(row for row in comparison.dti_rows if row.label == "arm_intro")
    post_row = next(row for row in comparison.dti_rows if row.label == "arm_post")
    assert intro_row.passes_front_end
    assert not post_row.passes_front_end
    assert comparison.post_adjustment_fails_band


def test_format_arm_scenario_includes_break_even_when_arm_overtakes_fixed(
    edge_cases: EdgeCaseCatalog,
):
    result = analyze_fixed_arm_scenario(edge_cases.arm_rate_spike)
    text = format_fixed_arm_scenario(result)
    assert result.break_even_month is not None
    assert f"month {result.break_even_month}" in text
    assert "Break-even" in text


def test_remaining_balance_midpoint_matches_amortization_identity():
    principal = 315_000
    annual_rate = 0.0575
    term_years = 30
    months_paid = 180
    payment = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    )
    balance = remaining_balance(
        principal=principal,
        annual_rate=annual_rate,
        term_years=term_years,
        months_paid=months_paid,
    )
    assert balance == pytest.approx(
        principal * (1 + annual_rate / 12) ** months_paid
        - payment * ((1 + annual_rate / 12) ** months_paid - 1) / (annual_rate / 12)
    )


def test_savings_trajectory_accumulates_contributions_separately_from_growth():
    snaps = savings_trajectory(
        starting_balance=2_500,
        monthly_contribution=250,
        annual_return=0.06,
        months=6,
    )
    assert snaps[-1].contributions == 250
    assert sum(snap.contributions for snap in snaps) == pytest.approx(1_500)
    assert snaps[-1].balance > 2_500 + 1_500


def test_compute_piti_zero_home_price_skips_pmi_even_with_rate():
    breakdown = compute_piti(
        loan_amount=420_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
        home_price=0,
        pmi_annual_rate=0.005,
    )
    assert breakdown.pmi_monthly == 0.0


def test_compare_fixed_vs_arm_balance_at_adjustment_less_than_principal():
    comparison = compare_fixed_vs_arm(
        principal=350_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        intro_years=5,
    )
    assert 0 < comparison.arm_balance_at_adjustment < 350_000
    assert comparison.arm_post_adjustment_payment > comparison.arm_intro_payment


def test_purchase_readiness_zero_closing_costs_equals_down_payment_only():
    readiness = check_purchase_readiness(
        purchase_scenario(down_payment=40_000, closing_costs=0),
        starting_balance=39_500,
        monthly_contribution=500,
        annual_return=0.0,
    )
    assert readiness.cash_required == 40_000
    assert readiness.months_until_ready == 1


def test_pmi_helpers_ignore_non_positive_home_price():
    assert not pmi_required(loan_amount=400_000, home_price=0)
    assert not pmi_required(loan_amount=400_000, home_price=-500_000)
    assert compute_pmi_monthly(
        loan_amount=450_000,
        home_price=0,
        pmi_annual_rate=0.005,
    ) == 0.0
    assert compute_pmi_monthly(
        loan_amount=450_000,
        home_price=-500_000,
        pmi_annual_rate=0.005,
    ) == 0.0


def test_compute_piti_skips_pmi_when_annual_rate_non_positive():
    breakdown = compute_piti(
        loan_amount=450_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.0,
    )
    assert breakdown.pmi_monthly == 0.0
    assert breakdown.piti == pytest.approx(
        breakdown.principal_and_interest
        + breakdown.tax_monthly
        + breakdown.insurance_monthly,
        rel=1e-9,
    )


def test_compute_piti_custom_ltv_threshold_defers_pmi():
    breakdown = compute_piti(
        loan_amount=410_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.005,
        pmi_ltv_threshold=0.85,
    )
    assert 410_000 / 500_000 == pytest.approx(0.82)
    assert breakdown.pmi_monthly == 0.0


def test_savings_trajectory_zero_return_records_zero_growth_each_month():
    snaps = savings_trajectory(
        starting_balance=5_000,
        monthly_contribution=200,
        annual_return=0.0,
        months=4,
    )
    assert all(snap.growth == 0.0 for snap in snaps)
    assert snaps[-1].balance == pytest.approx(5_800)


def test_remaining_balance_never_negative_over_full_amortization():
    principal = 275_000
    annual_rate = 0.0475
    term_years = 30
    for months_paid in range(term_years * 12 + 3):
        balance = remaining_balance(
            principal=principal,
            annual_rate=annual_rate,
            term_years=term_years,
            months_paid=months_paid,
        )
        assert balance >= 0.0


def test_mortgage_payment_one_year_term_amortizes_fully():
    principal = 60_000
    annual_rate = 0.06
    term_years = 1
    payment = mortgage_payment(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    )
    balance_before_last = remaining_balance(
        principal=principal,
        annual_rate=annual_rate,
        term_years=term_years,
        months_paid=11,
    )
    assert balance_before_last > 0
    assert balance_before_last < payment
    assert remaining_balance(
        principal=principal,
        annual_rate=annual_rate,
        term_years=term_years,
        months_paid=12,
    ) == 0.0
    assert total_interest(
        principal=principal, annual_rate=annual_rate, term_years=term_years
    ) == pytest.approx(payment * 12 - principal)
