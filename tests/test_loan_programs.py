import pytest

from homeafford.check import PurchaseScenario, check_affordability
from homeafford.loan_programs import (
    available_loan_programs,
    compare_loan_program_dti,
    format_loan_program_dti_comparison,
    get_loan_program,
    resolve_program_dti_params,
)
from homeafford.model import min_down_payment_for_dti, model_down_payment_dti
from homeafford.pmi import compute_pmi_monthly


def _scenario(**overrides) -> PurchaseScenario:
    defaults = dict(
        home_price=500_000,
        down_payment=50_000,
        gross_annual_income=150_000,
        monthly_debt_payments=400,
    )
    defaults.update(overrides)
    return PurchaseScenario(**defaults)


def test_available_loan_programs_includes_conventional_fha_va():
    assert available_loan_programs() == ("conventional", "fha", "va")


def test_get_loan_program_unknown_raises():
    with pytest.raises(ValueError, match="unknown loan program"):
        get_loan_program("usda")


def test_fha_requires_higher_min_down_than_conventional():
    conventional = resolve_program_dti_params("conventional")
    fha = resolve_program_dti_params("fha")
    assert fha.min_down_payment_pct > conventional.min_down_payment_pct
    assert fha.mortgage_insurance_always
    assert not conventional.mortgage_insurance_always


def test_va_allows_zero_down_and_no_mortgage_insurance():
    va = resolve_program_dti_params("va")
    assert va.min_down_payment_pct == 0.0
    assert va.pmi_annual_rate == 0.0
    assert not va.mortgage_insurance_always


def test_fha_mip_applies_at_any_ltv():
    mip = compute_pmi_monthly(
        loan_amount=450_000,
        home_price=500_000,
        pmi_annual_rate=0.0055,
        pmi_ltv_threshold=1.0,
        always_apply=True,
    )
    assert mip == pytest.approx(450_000 * 0.0055 / 12, rel=1e-6)


def test_fha_min_down_higher_than_conventional_for_stretch_case():
    scenario = _scenario(
        home_price=600_000,
        gross_annual_income=120_000,
        monthly_debt_payments=450,
    )
    conventional_min = min_down_payment_for_dti(
        scenario,
        band_label="conservative",
        min_down_payment_pct=0.03,
    )
    fha_params = resolve_program_dti_params("fha")
    fha_min = min_down_payment_for_dti(
        scenario,
        band_label="conservative",
        min_down_payment_pct=fha_params.min_down_payment_pct,
        pmi_annual_rate=fha_params.pmi_annual_rate,
        pmi_ltv_threshold=fha_params.pmi_ltv_threshold,
        mortgage_insurance_always=fha_params.mortgage_insurance_always,
    )
    assert conventional_min is not None
    assert fha_min is not None
    assert fha_min >= fha_params.min_down_payment_pct * scenario.home_price
    assert fha_min >= conventional_min


def test_va_zero_down_floor_allows_lower_min_down():
    scenario = _scenario(
        home_price=550_000,
        gross_annual_income=140_000,
        monthly_debt_payments=350,
    )
    conventional_min = min_down_payment_for_dti(scenario, band_label="moderate")
    va_params = resolve_program_dti_params("va")
    va_min = min_down_payment_for_dti(
        scenario,
        band_label="moderate",
        min_down_payment_pct=va_params.min_down_payment_pct,
        pmi_annual_rate=va_params.pmi_annual_rate,
        pmi_ltv_threshold=va_params.pmi_ltv_threshold,
        mortgage_insurance_always=va_params.mortgage_insurance_always,
    )
    assert conventional_min is not None
    assert va_min is not None
    assert va_min <= conventional_min


def test_compare_loan_program_dti_returns_all_programs():
    comparison = compare_loan_program_dti(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        band_label="conservative",
    )
    assert comparison.home_price == 600_000
    assert len(comparison.rows) == 3
    labels = {row.program.name for row in comparison.rows}
    assert labels == {"conventional", "fha", "va"}


def test_compare_loan_program_dti_min_down_passes_verification():
    comparison = compare_loan_program_dti(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        band_label="conservative",
    )
    for row in comparison.rows:
        if row.min_down_payment is None:
            continue
        check = row.check_at_min_down
        assert check is not None
        assert check.passes_front_end
        assert check.passes_back_end


def test_model_down_payment_dti_with_fha_program():
    model = model_down_payment_dti(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        down_payment_pcts=(0.035, 0.10),
        loan_program="fha",
        band_label="conservative",
    )
    assert model.min_down_payment is not None
    assert model.min_down_payment >= 600_000 * 0.035
    low_row = model.rows[0]
    assert low_row.down_payment_pct == 0.035
    assert low_row.check.estimated_pmi_monthly > 0


def test_check_affordability_loan_program_fha_enforces_min_down():
    scenario = _scenario(home_price=500_000, down_payment=10_000)
    result = check_affordability(scenario, loan_program="fha", band_label="conservative")
    assert not result.passes_down_payment
    assert any("below minimum" in reason for reason in result.reasons)


def test_format_loan_program_dti_comparison_includes_program_names():
    comparison = compare_loan_program_dti(
        _scenario(home_price=600_000, gross_annual_income=120_000, monthly_debt_payments=450),
        band_label="conservative",
    )
    text = format_loan_program_dti_comparison(comparison)
    assert "Loan program DTI comparison" in text
    assert "Conventional" in text
    assert "FHA" in text
    assert "VA" in text
