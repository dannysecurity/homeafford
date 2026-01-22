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
