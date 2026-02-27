"""CLI coverage for the report command."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from homeafford.cli import main


def test_cli_report_prints_affordability_bands_table(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "report",
            "--income",
            "120000",
            "--debt",
            "450",
            "--start",
            "15000",
            "--monthly",
            "800",
            "--years",
            "2",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Conservative" in output
    assert "Moderate" in output
    assert "Stretch" in output
    assert "Year" in output
    assert "Income $" in output


def test_cli_report_calendar_labels(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "report",
            "--income",
            "100000",
            "--years",
            "1",
            "--base-year",
            "2026",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Calendar" in output
    assert "2026" in output
    assert "2027" in output
