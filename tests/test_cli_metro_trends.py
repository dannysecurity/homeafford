"""CLI tests for the metro-trends command."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from homeafford.cli import main


def test_metro_trends_lists_all_metros(monkeypatch):
    monkeypatch.setattr("sys.argv", ["homeafford", "metro-trends"])
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "33100" in output
    assert "Miami-Fort Lauderdale-West Palm Beach, FL" in output
    assert "42660" in output


def test_metro_trends_shows_single_metro_series(monkeypatch):
    monkeypatch.setattr("sys.argv", ["homeafford", "metro-trends", "--metro", "19740"])
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Denver-Aurora-Lakewood, CO (19740)" in output
    assert "2022" in output
    assert "2025" in output


def test_metro_trends_accepts_custom_csv(monkeypatch, metro_home_price_trends_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "metro-trends",
            "--metro",
            "12420",
            "--csv",
            str(metro_home_price_trends_path),
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Austin-Round Rock-Georgetown, TX (12420)" in output
