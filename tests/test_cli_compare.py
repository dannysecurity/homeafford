"""CLI coverage for fixed vs ARM compare commands."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from homeafford.cli import main


def test_cli_compare_prints_loan_scenario(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare",
            "--principal",
            "400000",
            "--fixed-rate",
            "0.065",
            "--arm-intro",
            "0.055",
            "--arm-adjusted",
            "0.075",
            "--intro-years",
            "5",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Monthly P&I" in output
    assert "Break-even" in output
    assert "Cheaper over full term" in output


def test_cli_compare_purchase_prints_dti_table(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-purchase",
            "--price",
            "500000",
            "--down",
            "100000",
            "--income",
            "150000",
            "--arm-intro",
            "0.055",
            "--arm-adjusted",
            "0.095",
            "--band",
            "conservative",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Fixed vs ARM purchase" in output
    assert "DTI impact" in output
    assert "ARM after adj" in output
    assert "Warning: post-adjustment ARM payment exceeds DTI caps" in output


def test_cli_compare_sensitivity_prints_rate_table(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-sensitivity",
            "--principal",
            "400000",
            "--fixed-rate",
            "0.065",
            "--arm-intro",
            "0.055",
            "--adjusted-rates",
            "0.07,0.08,0.09",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "ARM post-adjustment rate sensitivity" in output
    assert "Fixed becomes cheaper" in output


def test_cli_compare_sensitivity_purchase_prints_dti_sweep(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-sensitivity-purchase",
            "--price",
            "500000",
            "--down",
            "100000",
            "--income",
            "150000",
            "--arm-intro",
            "0.055",
            "--adjusted-rates",
            "0.07,0.09,0.11",
            "--band",
            "conservative",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "ARM post-adjustment rate sensitivity (purchase)" in output
    assert "Highest adjusted rate passing DTI" in output


def test_cli_compare_report_prints_decision_summary(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-report",
            "--price",
            "500000",
            "--down",
            "100000",
            "--income",
            "150000",
            "--arm-intro",
            "0.055",
            "--arm-adjusted",
            "0.075",
            "--adjusted-rates",
            "0.07,0.09,0.11",
            "--band",
            "conservative",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Fixed vs ARM decision:" in output
    assert "DTI impact" in output
    assert "ARM post-adjustment rate sensitivity (purchase)" in output


def test_cli_compare_report_json_output(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-report",
            "--price",
            "500000",
            "--down",
            "100000",
            "--income",
            "150000",
            "--arm-intro",
            "0.055",
            "--arm-adjusted",
            "0.075",
            "--format",
            "json",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert '"recommendation"' in output
    assert '"purchase"' in output


def test_cli_compare_catalog_lists_presets(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["homeafford", "compare-catalog", "--list"],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Fixed vs ARM scenario catalog" in output
    assert "five_one_standard" in output
    assert "dti_tight" in output


def test_cli_compare_catalog_runs_loan_preset(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["homeafford", "compare-catalog", "--loan", "five_one_standard"],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Loan preset: five_one_standard" in output
    assert "Break-even" in output


def test_cli_compare_catalog_runs_purchase_preset(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["homeafford", "compare-catalog", "--purchase", "dti_tight"],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Purchase preset: dti_tight" in output
    assert "Warning: post-adjustment ARM payment exceeds DTI caps" in output


def test_cli_compare_catalog_loan_matrix(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["homeafford", "compare-catalog", "--loan-matrix"],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Loan preset comparison matrix" in output
    assert "arm_wins_full_term" in output


def test_cli_compare_catalog_purchase_matrix(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["homeafford", "compare-catalog", "--purchase-matrix"],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Purchase preset comparison matrix" in output
    assert "low_down_starter" in output
    assert "dti_tight" in output


def test_cli_compare_timeline_prints_year_table(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-timeline",
            "--principal",
            "400000",
            "--fixed-rate",
            "0.065",
            "--arm-intro",
            "0.055",
            "--arm-adjusted",
            "0.075",
            "--intro-years",
            "5",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Fixed vs ARM timeline" in output
    assert "Adjustment year: 6" in output
    assert "post_adjustment" in output


def test_cli_compare_timeline_json_output(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-timeline",
            "--principal",
            "400000",
            "--fixed-rate",
            "0.065",
            "--arm-intro",
            "0.055",
            "--arm-adjusted",
            "0.075",
            "--format",
            "json",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert '"adjustment_year": 6' in output
    assert '"yearly_rows"' in output


def test_cli_compare_catalog_loan_timeline(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "compare-catalog",
            "--loan-timeline",
            "five_one_standard",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Loan preset timeline: five_one_standard" in output
    assert "Peak ARM savings" in output
