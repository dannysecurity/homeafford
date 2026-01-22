"""CLI coverage for the range-report command."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from homeafford.cli import main


def test_cli_range_report_prints_affordable_range_table(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "range-report",
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
    assert "Affordable range $" in output
    assert "Spread $" in output
    assert "Year" in output
    assert "Income $" in output


def test_cli_range_report_respects_reference_year_with_csv_metro(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "range-report",
            "--income",
            "100000",
            "--years",
            "0",
            "--provider",
            "csv-metro",
            "--metro",
            "35620",
            "--reference-year",
            "2023",
        ],
    )
    main()
    output = capsys.readouterr().out
    assert "Affordable range $" in output
    assert "100,000" in output
