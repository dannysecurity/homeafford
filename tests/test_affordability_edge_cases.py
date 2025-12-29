"""Edge-case coverage for affordability band calculations."""

import pytest

from homeafford.affordability import AffordabilityInputs, affordability_bands
from tests.helpers.edge_case_catalog import EdgeCaseCatalog, affordability_inputs


def test_affordability_rejects_non_positive_income():
    with pytest.raises(ValueError, match="gross_annual_income must be positive"):
        affordability_bands(affordability_inputs(gross_annual_income=0))
    with pytest.raises(ValueError, match="gross_annual_income must be positive"):
        affordability_bands(affordability_inputs(gross_annual_income=-1))


def test_affordability_zero_loan_when_debt_overwhelms_budget(edge_cases: EdgeCaseCatalog):
    bands = affordability_bands(edge_cases.debt_overwhelms_budget)
    for band in bands:
        assert band.max_loan_amount == 0.0
        assert band.max_home_price == edge_cases.debt_overwhelms_budget.down_payment
        assert band.estimated_piti == pytest.approx(
            edge_cases.debt_overwhelms_budget.hoa_monthly
            + edge_cases.debt_overwhelms_budget.insurance_annual / 12,
            rel=1e-6,
        )


def test_affordability_hoa_reduces_max_loan(edge_cases: EdgeCaseCatalog):
    without_hoa = affordability_bands(edge_cases.no_hoa)[0]
    with_hoa = affordability_bands(edge_cases.high_hoa)[0]
    assert with_hoa.max_loan_amount < without_hoa.max_loan_amount
    assert with_hoa.max_home_price < without_hoa.max_home_price
    assert with_hoa.estimated_piti <= without_hoa.estimated_piti


def test_affordability_bands_increase_from_conservative_to_stretch():
    bands = affordability_bands(affordability_inputs())
    by_label = {band.label: band for band in bands}
    assert (
        by_label["conservative"].max_home_price
        < by_label["moderate"].max_home_price
        < by_label["stretch"].max_home_price
    )


def test_affordability_dti_at_ceiling_stays_within_caps():
    inputs = affordability_inputs(monthly_debt_payments=200)
    caps = {
        "conservative": (0.28, 0.36),
        "moderate": (0.31, 0.43),
        "stretch": (0.33, 0.45),
    }
    for band in affordability_bands(inputs):
        front_cap, back_cap = caps[band.label]
        assert band.front_end_dti <= front_cap + 1e-9
        assert band.back_end_dti <= back_cap + 1e-9


def test_affordability_back_end_cap_binding_with_high_debt():
    """Back-end DTI should bind before front-end when monthly debts are elevated."""
    low_debt = affordability_bands(affordability_inputs(monthly_debt_payments=100))[0]
    high_debt = affordability_bands(affordability_inputs(monthly_debt_payments=1_800))[0]
    assert high_debt.max_home_price < low_debt.max_home_price
    assert high_debt.back_end_dti <= 0.36 + 1e-9
    assert high_debt.front_end_dti < 0.28


def test_affordability_insurance_only_budget_yields_zero_loan():
    """When housing budget covers insurance but nothing else, max loan is zero."""
    inputs = AffordabilityInputs(
        gross_annual_income=4_000,
        monthly_debt_payments=0,
        down_payment=5_000,
        insurance_annual=1_200,
        hoa_monthly=0,
    )
    conservative = affordability_bands(inputs)[0]
    monthly_income = inputs.gross_annual_income / 12
    housing_budget = monthly_income * 0.28
    assert housing_budget <= inputs.insurance_annual / 12 + 1e-9
    assert conservative.max_loan_amount == 0.0
    assert conservative.max_home_price == inputs.down_payment
