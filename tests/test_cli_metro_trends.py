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
    assert "2026" in output


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


def test_metro_trends_projects_forward_price(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "metro-trends",
            "--metro",
            "16980",
            "--project-years",
            "3",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Chicago-Naperville-Elgin, IL-IN-WI (16980)" in output
    assert "Projected (2029" in output


def test_metro_trends_rank_lists_metros_by_total_change(monkeypatch):
    monkeypatch.setattr("sys.argv", ["homeafford", "metro-trends", "--rank"])
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Rank" in output
    assert "CAGR %" in output
    assert "33100" in output
    assert "26420" in output


def test_metro_trends_max_price_filters_affordable_metros(monkeypatch, metro_home_price_trends_budget_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "metro-trends",
            "--csv",
            str(metro_home_price_trends_budget_path),
            "--max-price",
            "300000",
            "--year",
            "2026",
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Pittsburgh, PA" in output
    assert "Cleveland-Elyria, OH" in output
    assert "Indianapolis-Carmel-Anderson, IN" not in output


def test_metro_trends_recovering_fixture_shows_rebound_series(
    monkeypatch, metro_home_price_trends_recovering_path
):
    monkeypatch.setattr(
        "sys.argv",
        [
            "homeafford",
            "metro-trends",
            "--metro",
            "38060",
            "--csv",
            str(metro_home_price_trends_recovering_path),
        ],
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()
    assert "Phoenix-Mesa-Chandler, AZ (38060)" in output
    assert "406,125" in output
    assert "447,753" in output
