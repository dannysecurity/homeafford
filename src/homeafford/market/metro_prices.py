"""Shared metro home price trend loading and selection."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from homeafford.market.errors import MarketDataError, MarketDataUnavailable

_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CSV_PATH = _DATA_DIR / "metro_home_price_trends.csv"
REQUIRED_TREND_COLUMNS = (
    "metro_id",
    "metro_name",
    "year",
    "median_home_price",
    "yoy_change_pct",
)
DEFAULT_YOY_PRICE_TOLERANCE = 0.01


@dataclass(frozen=True)
class MetroPriceTrendRow:
    """One metro-year observation from a home price trends file."""

    metro_id: str
    metro_name: str
    year: int
    median_home_price: float
    yoy_change_pct: float


class MetroPriceTrendValidationError(MarketDataError):
    """Raised when metro home price trend rows fail integrity checks."""


def validate_metro_price_trends(rows: list[MetroPriceTrendRow]) -> None:
    """Verify metro price trend rows meet data integrity constraints."""
    if not rows:
        raise MetroPriceTrendValidationError("metro price trends must contain at least one row")

    seen: set[tuple[str, int]] = set()
    names_by_metro: dict[str, str] = {}

    for row in rows:
        if not row.metro_id:
            raise MetroPriceTrendValidationError("metro_id must be non-empty")
        if not row.metro_name:
            raise MetroPriceTrendValidationError(
                f"metro_name must be non-empty for metro_id={row.metro_id!r}"
            )
        if row.median_home_price <= 0:
            raise MetroPriceTrendValidationError(
                "median_home_price must be positive for "
                f"metro_id={row.metro_id!r} year={row.year}"
            )
        if row.yoy_change_pct <= -1.0:
            raise MetroPriceTrendValidationError(
                "yoy_change_pct must be greater than -100% for "
                f"metro_id={row.metro_id!r} year={row.year}"
            )

        key = (row.metro_id, row.year)
        if key in seen:
            raise MetroPriceTrendValidationError(
                f"duplicate metro_id/year pair: metro_id={row.metro_id!r} year={row.year}"
            )
        seen.add(key)

        prior_name = names_by_metro.get(row.metro_id)
        if prior_name is None:
            names_by_metro[row.metro_id] = row.metro_name
        elif prior_name != row.metro_name:
            raise MetroPriceTrendValidationError(
                f"inconsistent metro_name for metro_id={row.metro_id!r}: "
                f"{prior_name!r} vs {row.metro_name!r}"
            )

    grouped = index_metro_rows(rows)
    for metro_id, metro_rows in grouped.items():
        years = [row.year for row in metro_rows]
        if years != sorted(years):
            raise MetroPriceTrendValidationError(
                f"years must be sorted for metro_id={metro_id!r}"
            )

    validate_yoy_price_consistency(rows)


def validate_yoy_price_consistency(
    rows: list[MetroPriceTrendRow],
    *,
    tolerance: float = DEFAULT_YOY_PRICE_TOLERANCE,
) -> None:
    """Verify each year's median price aligns with the prior year and YoY rate."""
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    grouped = index_metro_rows(rows)
    for metro_id, metro_rows in grouped.items():
        for prev, row in zip(metro_rows[:-1], metro_rows[1:], strict=True):
            expected = prev.median_home_price * (1.0 + row.yoy_change_pct)
            rel_error = abs(row.median_home_price - expected) / prev.median_home_price
            if rel_error > tolerance:
                raise MetroPriceTrendValidationError(
                    "yoy price inconsistency for "
                    f"metro_id={metro_id!r} year={row.year}: "
                    f"median {row.median_home_price:,.0f} vs expected "
                    f"{expected:,.0f} from prior year "
                    f"(relative error {rel_error:.2%}, tolerance {tolerance:.2%})"
                )


def load_metro_price_trends(path: Path = DEFAULT_CSV_PATH) -> list[MetroPriceTrendRow]:
    """Parse a metro home price trends CSV into typed rows."""
    rows: list[MetroPriceTrendRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows.append(
                MetroPriceTrendRow(
                    metro_id=record["metro_id"],
                    metro_name=record["metro_name"],
                    year=int(record["year"]),
                    median_home_price=float(record["median_home_price"]),
                    yoy_change_pct=float(record["yoy_change_pct"]),
                )
            )
    return rows


def index_metro_rows(rows: list[MetroPriceTrendRow]) -> dict[str, list[MetroPriceTrendRow]]:
    """Group price trend rows by metro ID, sorted by year within each metro."""
    grouped: dict[str, list[MetroPriceTrendRow]] = {}
    for row in rows:
        grouped.setdefault(row.metro_id, []).append(row)
    for metro_rows in grouped.values():
        metro_rows.sort(key=lambda row: row.year)
    return grouped


def select_metro_row(
    grouped: dict[str, list[MetroPriceTrendRow]],
    *,
    metro_id: str,
    reference_year: int | None,
) -> MetroPriceTrendRow:
    """Select a metro price row, optionally pinned to a reference year."""
    metro_rows = grouped.get(metro_id)
    if not metro_rows:
        raise MarketDataUnavailable(f"unknown metro_id {metro_id!r}")

    if reference_year is not None:
        for row in metro_rows:
            if row.year == reference_year:
                return row
        raise MarketDataUnavailable(
            f"no price data for metro_id {metro_id!r} in year {reference_year}"
        )

    return metro_rows[-1]


def list_metro_ids(grouped: dict[str, list[MetroPriceTrendRow]]) -> tuple[str, ...]:
    """Return sorted metro IDs present in an indexed price table."""
    return tuple(sorted(grouped))


def metro_years(grouped: dict[str, list[MetroPriceTrendRow]], metro_id: str) -> tuple[int, ...]:
    """Return sorted calendar years available for a metro."""
    metro_rows = grouped.get(metro_id)
    if not metro_rows:
        raise MarketDataUnavailable(f"unknown metro_id {metro_id!r}")
    return tuple(row.year for row in metro_rows)
