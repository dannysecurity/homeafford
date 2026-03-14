"""CLI coverage for the range-report command."""

from __future__ import annotations

import io
import json
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


def test_cli_range_report_json_format(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "range-report",
            "--income",
            "120000",
            "--start",
            "15000",
            "--years",
            "1",
            "--format",
            "json",
            "--base-year",
            "2026",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    payload = json.loads(buffer.getvalue())
    assert len(payload) == 2
    assert payload[0]["calendar_year"] == 2026
    assert "conservative_max_price" in payload[0]
    assert "moderate_max_price" in payload[0]
    assert "stretch_max_price" in payload[0]


def test_cli_range_report_includes_range_growth_summary(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "range-report",
            "--income",
            "120000",
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
    assert "Range growth (0 → 2):" in output
    assert "conservative +" in output
    assert "stretch +" in output


def test_cli_range_report_calendar_labels(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "range-report",
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


def test_cli_range_report_rejects_metro_with_static_provider(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "range-report",
            "--income",
            "100000",
            "--years",
            "1",
            "--provider",
            "static",
            "--metro",
            "31080",
        ],
    )
    try:
        main()
        raised = False
    except SystemExit as exc:
        raised = True
        assert "metro_id" in str(exc)
    assert raised


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
