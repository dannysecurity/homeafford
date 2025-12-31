"""Tests for PMI integration in down payment and DTI affordability checks."""

from __future__ import annotations

import pytest

from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.check import PurchaseScenario, check_affordability, check_against_band
from homeafford.market.snapshot import DEFAULT_MARKET, MarketSnapshot
from homeafford.model import model_down_payment_dti, min_down_payment_for_dti
from homeafford.piti import compute_piti
from homeafford.pmi import compute_pmi_monthly, pmi_required


def test_compute_pmi_monthly_zero_at_or_below_ltv_threshold():
    assert compute_pmi_monthly(
        loan_amount=400_000,
        home_price=500_000,
        pmi_annual_rate=0.005,
        pmi_ltv_threshold=0.80,
    ) == 0.0


def test_compute_pmi_monthly_applies_rate_above_threshold():
    pmi = compute_pmi_monthly(
        loan_amount=450_000,
        home_price=500_000,
        pmi_annual_rate=0.005,
        pmi_ltv_threshold=0.80,
    )
    assert pmi == pytest.approx(450_000 * 0.005 / 12)


def test_compute_pmi_monthly_zero_for_zero_rate_or_loan():
    assert compute_pmi_monthly(
        loan_amount=450_000,
        home_price=500_000,
        pmi_annual_rate=0.0,
    ) == 0.0
    assert compute_pmi_monthly(
        loan_amount=0,
        home_price=500_000,
        pmi_annual_rate=0.005,
    ) == 0.0


def test_pmi_required_flag():
    assert pmi_required(loan_amount=405_000, home_price=500_000)
    assert not pmi_required(loan_amount=400_000, home_price=500_000)
    assert not pmi_required(loan_amount=400_000, home_price=500_000, pmi_ltv_threshold=0.85)


def test_compute_piti_includes_pmi_when_home_price_provided():
    without = compute_piti(
        loan_amount=450_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
    )
    with_pmi = compute_piti(
        loan_amount=450_000,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        hoa_monthly=0,
        mortgage_rate=0.065,
        loan_term_years=30,
        home_price=500_000,
        pmi_annual_rate=0.005,
    )
    assert with_pmi.pmi_monthly > 0
    assert with_pmi.piti == pytest.approx(
        without.piti + with_pmi.pmi_monthly
    )


def test_check_affordability_includes_pmi_in_dti():
    scenario = PurchaseScenario(
        home_price=500_000,
        down_payment=50_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    with_pmi = check_affordability(scenario, pmi_annual_rate=0.005)
    without_pmi = check_affordability(scenario, pmi_annual_rate=0.0)
    assert with_pmi.estimated_pmi_monthly > 0
    assert with_pmi.pmi_required
    assert with_pmi.estimated_piti > without_pmi.estimated_piti
    assert with_pmi.front_end_dti > without_pmi.front_end_dti
    assert with_pmi.back_end_dti > without_pmi.back_end_dti


def test_pmi_increases_min_down_payment_for_dti():
    scenario = PurchaseScenario(
        home_price=600_000,
        down_payment=0,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
    )
    with_pmi = min_down_payment_for_dti(
        scenario,
        band_label="conservative",
        pmi_annual_rate=0.005,
    )
    without_pmi = min_down_payment_for_dti(
        scenario,
        band_label="conservative",
        pmi_annual_rate=0.0,
    )
    assert with_pmi is not None
    assert without_pmi is not None
    assert with_pmi >= without_pmi


def test_model_sweep_shows_pmi_at_low_down_levels():
    model = model_down_payment_dti(
        PurchaseScenario(
            home_price=500_000,
            down_payment=0,
            gross_annual_income=150_000,
            monthly_debt_payments=400,
        ),
        down_payment_pcts=(0.05, 0.20),
        band_label="conservative",
    )
    low, high = model.rows
    assert low.check.estimated_pmi_monthly > 0
    assert high.check.estimated_pmi_monthly == 0.0


def test_affordability_bands_account_for_pmi_with_low_down():
    no_pmi_market = MarketSnapshot(
        mortgage_rate=0.065,
        property_tax_rate=0.012,
        insurance_annual=1_200,
        pmi_annual_rate=0.0,
    )
    with_pmi = affordability_bands(
        AffordabilityInputs(
            gross_annual_income=120_000,
            down_payment=20_000,
            market=DEFAULT_MARKET,
        )
    )
    without_pmi = affordability_bands(
        AffordabilityInputs(
            gross_annual_income=120_000,
            down_payment=20_000,
            market=no_pmi_market,
        )
    )
    assert with_pmi[0].max_home_price <= without_pmi[0].max_home_price


def test_check_at_twenty_percent_down_has_no_pmi_cost():
    result = check_against_band(
        PurchaseScenario(
            home_price=500_000,
            down_payment=100_000,
            gross_annual_income=150_000,
        ),
        band_label="conservative",
    )
    assert not result.pmi_required
    assert result.estimated_pmi_monthly == 0.0
