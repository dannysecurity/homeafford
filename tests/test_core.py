from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.mortgage import (
    compare_fixed_vs_arm,
    mortgage_payment,
    remaining_balance,
    total_interest,
)
from homeafford.savings import savings_trajectory


def test_savings_trajectory_zero_contribution():
    snaps = savings_trajectory(
        starting_balance=10_000,
        monthly_contribution=0,
        annual_return=0.0,
        months=12,
    )
    assert len(snaps) == 12
    assert snaps[-1].balance == 10_000


def test_savings_trajectory_grows_with_contributions():
    snaps = savings_trajectory(
        starting_balance=0,
        monthly_contribution=100,
        annual_return=0.0,
        months=10,
    )
    assert snaps[-1].balance == 1_000


def test_mortgage_payment_zero_rate():
    payment = mortgage_payment(principal=120_000, annual_rate=0.0, term_years=30)
    assert payment == 120_000 / 360


def test_mortgage_payment_positive_rate():
    payment = mortgage_payment(principal=300_000, annual_rate=0.06, term_years=30)
    assert 1_700 < payment < 1_900


def test_remaining_balance_decreases():
    balance = remaining_balance(
        principal=300_000,
        annual_rate=0.06,
        term_years=30,
        months_paid=60,
    )
    assert 0 < balance < 300_000


def test_total_interest():
    interest = total_interest(principal=100_000, annual_rate=0.05, term_years=30)
    assert interest > 0


def test_compare_fixed_vs_arm_intro_rate_lower():
    result = compare_fixed_vs_arm(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        intro_years=5,
    )
    assert result.arm_intro_payment < result.fixed_payment
    assert result.arm_post_adjustment_payment > result.arm_intro_payment
    assert 0 < result.arm_balance_at_adjustment < 400_000
    assert result.intro_years == 5


def test_compare_fixed_vs_arm_rejects_invalid_intro():
    try:
        compare_fixed_vs_arm(
            principal=400_000,
            term_years=30,
            fixed_rate=0.065,
            arm_intro_rate=0.055,
            arm_adjusted_rate=0.075,
            intro_years=30,
        )
    except ValueError as exc:
        assert "intro_years" in str(exc)
    else:
        raise AssertionError("expected ValueError for intro_years >= term_years")


def test_affordability_bands_ordering():
    bands = affordability_bands(
        AffordabilityInputs(gross_annual_income=100_000, monthly_debt_payments=200)
    )
    assert [b.label for b in bands] == ["conservative", "moderate", "stretch"]
    assert bands[0].max_home_price <= bands[1].max_home_price <= bands[2].max_home_price


def test_affordability_respects_down_payment():
    base = affordability_bands(AffordabilityInputs(gross_annual_income=120_000, down_payment=0))
    with_down = affordability_bands(
        AffordabilityInputs(gross_annual_income=120_000, down_payment=50_000)
    )
    assert with_down[0].max_home_price > base[0].max_home_price
