"""Command-line interface for homeafford."""

from __future__ import annotations

import argparse

from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.affordability_summary import (
    evaluate_down_payment_dti_affordability,
    format_down_payment_dti_affordability_evaluation,
    format_down_payment_dti_affordability_evaluation_json,
    format_purchase_affordability_summary,
    format_purchase_affordability_summary_json,
    summarize_purchase_affordability,
)
from homeafford.check import (
    PurchaseScenario,
    check_affordability,
    check_against_band,
    check_purchase_readiness,
)
from homeafford.loan_programs import (
    compare_loan_program_dti,
    format_loan_program_dti_comparison,
)
from homeafford.affordability_frontier import (
    format_affordability_frontier,
    format_affordability_frontier_json,
    model_affordability_frontier,
)
from homeafford.dti_analysis import (
    diagnose_down_payment_affordability,
    format_down_payment_affordability_diagnostic,
    format_down_payment_affordability_diagnostic_json,
)
from homeafford.model import (
    format_down_payment_dti_model,
    format_down_payment_dti_model_json,
    format_purchase_affordability_plan,
    format_purchase_affordability_plan_json,
    model_down_payment_dti,
    plan_purchase_affordability,
)
from homeafford.market.errors import UnsupportedQueryError
from homeafford.market.registry import (
    available_providers,
    format_provider_choices,
    get_provider,
    validate_registry_query,
)
from homeafford.market.metro_trends import (
    default_metro_trend_catalog,
    format_metro_trend_projection,
    format_metro_trends_ranked,
    format_metro_trends_table,
)
from homeafford.market.resolve import apply_market_to_affordability_inputs, apply_market_to_purchase_scenario
from homeafford.mortgage import mortgage_payment, total_interest
from homeafford.arm_sensitivity import (
    format_arm_purchase_sensitivity,
    format_arm_rate_sensitivity,
    sweep_arm_adjusted_rates,
    sweep_arm_adjusted_rates_purchase,
)
from homeafford.fixed_arm_catalog import (
    default_fixed_arm_catalog,
    format_catalog_listing,
    format_loan_preset_detail,
    format_loan_preset_matrix,
    format_loan_preset_timeline,
    format_purchase_preset_detail,
    format_purchase_preset_matrix,
)
from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    analyze_fixed_arm_scenario,
    compare_fixed_arm_purchase,
    fixed_arm_decision_report,
    format_fixed_arm_decision_report,
    format_fixed_arm_decision_report_json,
    format_fixed_arm_purchase_comparison,
    format_fixed_arm_scenario,
)
from homeafford.fixed_arm_timeline import (
    build_fixed_arm_timeline,
    format_fixed_arm_timeline,
    format_fixed_arm_timeline_json,
)
from homeafford.report import (
    affordability_report_by_year,
    format_affordability_range_report,
    format_affordability_range_report_json,
    format_affordability_report,
    format_target_home_report,
    target_home_report_by_year,
)
from homeafford.savings import savings_trajectory


def _parse_adjusted_rates(raw: str | None) -> tuple[float, ...] | None:
    if raw is None:
        return None
    return tuple(float(part.strip()) for part in raw.split(",") if part.strip())


def _market_overrides(args: argparse.Namespace) -> dict[str, float] | None:
    """Build provider overrides from CLI flags that differ from static defaults."""
    overrides: dict[str, float] = {}
    if getattr(args, "rate", None) is not None and args.rate != 0.065:
        overrides["mortgage_rate"] = args.rate
    if getattr(args, "annual_return", None) is not None and args.annual_return != 0.04:
        overrides["savings_annual_return"] = args.annual_return
    return overrides or None


def _add_provider_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=available_providers(),
        default="static",
        help=f"Market data provider ({format_provider_choices()})",
    )
    parser.add_argument(
        "--metro",
        metavar="METRO_ID",
        help="Metro area ID for metro-aware providers (e.g. 31080 for Los Angeles)",
    )


def _validate_provider_args(
    args: argparse.Namespace,
    *,
    loan_term_years: int = 30,
) -> None:
    """Exit early when CLI flags request unsupported provider dimensions."""
    metro_id = getattr(args, "metro", None)
    reference_year = getattr(args, "reference_year", None)
    if loan_term_years == 30 and metro_id is None and reference_year is None:
        return
    try:
        validate_registry_query(
            args.provider,
            loan_term_years=loan_term_years,
            metro_id=metro_id,
            reference_year=reference_year,
        )
    except UnsupportedQueryError as exc:
        raise SystemExit(str(exc)) from exc


def _market_query(args: argparse.Namespace, *, loan_term_years: int = 30):
    """Build a market query when the CLI supplies metro context."""
    from homeafford.market.query import MarketQuery

    metro_id = getattr(args, "metro", None)
    reference_year = getattr(args, "reference_year", None)
    if metro_id is None and reference_year is None:
        return None
    _validate_provider_args(args, loan_term_years=loan_term_years)
    return MarketQuery(
        loan_term_years=loan_term_years,
        metro_id=metro_id,
        reference_year=reference_year,
    )


def _add_yearly_affordability_args(parser: argparse.ArgumentParser) -> None:
    """Shared CLI flags for year-by-year affordability projections."""
    parser.add_argument("--income", type=float, required=True)
    parser.add_argument("--debt", type=float, default=0.0)
    parser.add_argument("--start", type=float, default=0.0, help="Starting savings balance")
    parser.add_argument("--monthly", type=float, default=0.0, help="Monthly savings contribution")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--return", dest="annual_return", type=float, default=0.04)
    parser.add_argument("--income-growth", type=float, default=0.0, help="Annual income growth rate")
    parser.add_argument("--rate", type=float, default=0.065)
    parser.add_argument(
        "--reference-year",
        type=int,
        default=None,
        help="Calendar year for metro market data (csv-metro provider)",
    )
    parser.add_argument("--hoa", type=float, default=0.0, help="Monthly HOA fee")
    parser.add_argument("--term", type=int, default=30, help="Loan term in years")
    parser.add_argument(
        "--base-year",
        type=int,
        default=None,
        help="Starting calendar year for projection labels",
    )
    _add_provider_arg(parser)


def _run_affordability_report_by_year(args: argparse.Namespace):
    _validate_provider_args(args, loan_term_years=args.term)
    provider = get_provider(args.provider)
    return affordability_report_by_year(
        gross_annual_income=args.income,
        monthly_debt_payments=args.debt,
        starting_balance=args.start,
        monthly_contribution=args.monthly,
        annual_return=args.annual_return,
        years=args.years,
        income_growth_rate=args.income_growth,
        hoa_monthly=args.hoa,
        loan_term_years=args.term,
        mortgage_rate=args.rate,
        provider=provider,
        metro_id=args.metro,
        reference_year=args.reference_year,
        market_overrides=_market_overrides(args),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="homeafford",
        description="Savings, mortgage, and affordability planning tools",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    savings = sub.add_parser("savings", help="Project savings growth")
    savings.add_argument("--start", type=float, required=True)
    savings.add_argument("--monthly", type=float, required=True)
    savings.add_argument("--years", type=int, required=True)
    savings.add_argument("--return", dest="annual_return", type=float, default=0.04)

    mortgage = sub.add_parser("mortgage", help="Compute mortgage payment")
    mortgage.add_argument("--principal", type=float, required=True)
    mortgage.add_argument("--rate", type=float, required=True)
    mortgage.add_argument("--years", type=int, default=30)

    compare = sub.add_parser(
        "compare",
        help="Compare fixed-rate vs ARM mortgage scenario",
    )
    compare.add_argument("--principal", type=float, required=True)
    compare.add_argument("--fixed-rate", type=float, required=True)
    compare.add_argument("--arm-intro", type=float, required=True, help="ARM intro rate")
    compare.add_argument(
        "--arm-adjusted",
        type=float,
        required=True,
        help="ARM rate after intro period",
    )
    compare.add_argument("--years", type=int, default=30)
    compare.add_argument(
        "--intro-years",
        type=int,
        default=5,
        help="Intro period length (e.g. 5 for a 5/1 ARM)",
    )

    compare_timeline = sub.add_parser(
        "compare-timeline",
        help="Year-by-year fixed vs ARM payment timeline",
    )
    compare_timeline.add_argument("--principal", type=float, required=True)
    compare_timeline.add_argument("--fixed-rate", type=float, required=True)
    compare_timeline.add_argument(
        "--arm-intro",
        type=float,
        required=True,
        help="ARM intro rate",
    )
    compare_timeline.add_argument(
        "--arm-adjusted",
        type=float,
        required=True,
        help="ARM rate after intro period",
    )
    compare_timeline.add_argument("--years", type=int, default=30)
    compare_timeline.add_argument(
        "--intro-years",
        type=int,
        default=5,
        help="Intro period length (e.g. 5 for a 5/1 ARM)",
    )
    compare_timeline.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the payment timeline",
    )

    compare_purchase = sub.add_parser(
        "compare-purchase",
        help="Compare fixed vs ARM for a home purchase including DTI impact",
    )
    compare_purchase.add_argument("--price", type=float, required=True)
    compare_purchase.add_argument("--down", type=float, required=True)
    compare_purchase.add_argument("--income", type=float, required=True)
    compare_purchase.add_argument("--debt", type=float, default=0.0)
    compare_purchase.add_argument(
        "--rate",
        type=float,
        default=0.065,
        help="Fixed mortgage rate (also used as scenario baseline)",
    )
    compare_purchase.add_argument(
        "--arm-intro",
        type=float,
        required=True,
        help="ARM intro rate",
    )
    compare_purchase.add_argument(
        "--arm-adjusted",
        type=float,
        required=True,
        help="ARM rate after intro period",
    )
    compare_purchase.add_argument("--years", type=int, default=30)
    compare_purchase.add_argument(
        "--intro-years",
        type=int,
        default=5,
        help="Intro period length (e.g. 5 for a 5/1 ARM)",
    )
    compare_purchase.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    _add_provider_arg(compare_purchase)

    compare_report = sub.add_parser(
        "compare-report",
        help="Unified fixed vs ARM purchase report with recommendation and optional rate sweep",
    )
    compare_report.add_argument("--price", type=float, required=True)
    compare_report.add_argument("--down", type=float, required=True)
    compare_report.add_argument("--income", type=float, required=True)
    compare_report.add_argument("--debt", type=float, default=0.0)
    compare_report.add_argument(
        "--rate",
        type=float,
        default=0.065,
        help="Fixed mortgage rate (also used as scenario baseline)",
    )
    compare_report.add_argument(
        "--arm-intro",
        type=float,
        required=True,
        help="ARM intro rate",
    )
    compare_report.add_argument(
        "--arm-adjusted",
        type=float,
        required=True,
        help="ARM rate after intro period",
    )
    compare_report.add_argument("--years", type=int, default=30)
    compare_report.add_argument(
        "--intro-years",
        type=int,
        default=5,
        help="Intro period length (e.g. 5 for a 5/1 ARM)",
    )
    compare_report.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    compare_report.add_argument(
        "--adjusted-rates",
        type=str,
        default=None,
        help="Optional comma-separated post-adjustment rates for DTI sensitivity sweep",
    )
    compare_report.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the decision report",
    )
    _add_provider_arg(compare_report)

    compare_sensitivity = sub.add_parser(
        "compare-sensitivity",
        help="Sweep ARM post-adjustment rates vs a fixed-rate loan",
    )
    compare_sensitivity.add_argument("--principal", type=float, required=True)
    compare_sensitivity.add_argument("--fixed-rate", type=float, required=True)
    compare_sensitivity.add_argument(
        "--arm-intro",
        type=float,
        required=True,
        help="ARM intro rate",
    )
    compare_sensitivity.add_argument("--years", type=int, default=30)
    compare_sensitivity.add_argument(
        "--intro-years",
        type=int,
        default=5,
        help="Intro period length (e.g. 5 for a 5/1 ARM)",
    )
    compare_sensitivity.add_argument(
        "--adjusted-rates",
        type=str,
        default=None,
        help="Comma-separated post-adjustment rates (e.g. 0.06,0.07,0.08,0.09)",
    )

    compare_sensitivity_purchase = sub.add_parser(
        "compare-sensitivity-purchase",
        help="Sweep ARM post-adjustment rates for a purchase including DTI",
    )
    compare_sensitivity_purchase.add_argument("--price", type=float, required=True)
    compare_sensitivity_purchase.add_argument("--down", type=float, required=True)
    compare_sensitivity_purchase.add_argument("--income", type=float, required=True)
    compare_sensitivity_purchase.add_argument("--debt", type=float, default=0.0)
    compare_sensitivity_purchase.add_argument(
        "--rate",
        type=float,
        default=0.065,
        help="Fixed mortgage rate (also used as scenario baseline)",
    )
    compare_sensitivity_purchase.add_argument(
        "--arm-intro",
        type=float,
        required=True,
        help="ARM intro rate",
    )
    compare_sensitivity_purchase.add_argument("--years", type=int, default=30)
    compare_sensitivity_purchase.add_argument(
        "--intro-years",
        type=int,
        default=5,
        help="Intro period length (e.g. 5 for a 5/1 ARM)",
    )
    compare_sensitivity_purchase.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    compare_sensitivity_purchase.add_argument(
        "--adjusted-rates",
        type=str,
        default=None,
        help="Comma-separated post-adjustment rates (e.g. 0.06,0.07,0.08,0.09)",
    )
    _add_provider_arg(compare_sensitivity_purchase)

    bands = sub.add_parser("bands", help="Estimate affordability bands")
    bands.add_argument("--income", type=float, required=True)
    bands.add_argument("--debt", type=float, default=0.0)
    bands.add_argument("--down", type=float, default=0.0)
    bands.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(bands)

    check = sub.add_parser("check", help="Check DTI and down payment for a purchase")
    check.add_argument("--price", type=float, required=True)
    check.add_argument("--down", type=float, required=True)
    check.add_argument("--income", type=float, required=True)
    check.add_argument("--debt", type=float, default=0.0)
    check.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(check)
    check.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    check.add_argument("--min-down-pct", type=float, default=0.03)
    check.add_argument(
        "--program",
        choices=["conventional", "fha", "va"],
        default=None,
        help="Loan program rules for down payment floor and mortgage insurance",
    )
    check.add_argument("--savings", type=float, default=None, help="Current savings balance")
    check.add_argument("--monthly-save", type=float, default=0.0)
    check.add_argument("--closing", type=float, default=0.0)
    check.add_argument(
        "--recommend",
        action="store_true",
        help="Include minimum down/income hints and remediation recommendations",
    )
    check.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format when --recommend is set (includes savings when --savings is given)",
    )

    report = sub.add_parser(
        "report",
        help="Show affordability bands by year as savings grow",
    )
    _add_yearly_affordability_args(report)

    range_report = sub.add_parser(
        "range-report",
        help="Show affordable price range (conservative–stretch) by year",
    )
    _add_yearly_affordability_args(range_report)
    range_report.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the range report",
    )

    model = sub.add_parser(
        "model",
        help="Model down payment levels vs DTI for a fixed home price",
    )
    model.add_argument("--price", type=float, required=True)
    model.add_argument("--income", type=float, required=True)
    model.add_argument("--debt", type=float, default=0.0)
    model.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(model)
    model.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    model.add_argument("--min-down-pct", type=float, default=0.03)
    model.add_argument(
        "--program",
        choices=["conventional", "fha", "va"],
        default=None,
        help="Loan program rules for down payment floor and mortgage insurance",
    )
    model.add_argument(
        "--down-pcts",
        type=str,
        default="3,5,10,15,20",
        help="Comma-separated down payment percentages to evaluate",
    )
    model.add_argument("--savings", type=float, default=None, help="Current savings balance")
    model.add_argument("--monthly-save", type=float, default=0.0)
    model.add_argument("--closing", type=float, default=0.0)
    model.add_argument("--return", dest="annual_return", type=float, default=0.04)
    model.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the down payment vs DTI model",
    )

    plan = sub.add_parser(
        "plan",
        help="Plan purchase: DTI min down payment plus savings timeline",
    )
    plan.add_argument("--price", type=float, required=True)
    plan.add_argument("--income", type=float, required=True)
    plan.add_argument("--debt", type=float, default=0.0)
    plan.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(plan)
    plan.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    plan.add_argument("--min-down-pct", type=float, default=0.03)
    plan.add_argument(
        "--program",
        choices=["conventional", "fha", "va"],
        default=None,
        help="Loan program rules for down payment floor and mortgage insurance",
    )
    plan.add_argument("--savings", type=float, required=True)
    plan.add_argument("--monthly-save", type=float, default=0.0)
    plan.add_argument("--closing", type=float, default=0.0)
    plan.add_argument("--return", dest="annual_return", type=float, default=0.04)
    plan.add_argument("--target-months", type=int, default=None, help="Horizon for savings projection")
    plan.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the purchase plan",
    )

    target = sub.add_parser(
        "target-report",
        help="Year-by-year readiness for a fixed target home price",
    )
    target.add_argument("--price", type=float, required=True)
    target.add_argument("--income", type=float, required=True)
    target.add_argument("--debt", type=float, default=0.0)
    target.add_argument("--start", type=float, default=0.0, help="Starting savings balance")
    target.add_argument("--monthly", type=float, default=0.0, help="Monthly savings contribution")
    target.add_argument("--years", type=int, default=5)
    target.add_argument("--return", dest="annual_return", type=float, default=0.04)
    target.add_argument("--income-growth", type=float, default=0.0, help="Annual income growth rate")
    target.add_argument("--closing", type=float, default=0.0)
    target.add_argument("--rate", type=float, default=0.065)
    target.add_argument(
        "--reference-year",
        type=int,
        default=None,
        help="Calendar year for metro market data (csv-metro provider)",
    )
    _add_provider_arg(target)
    target.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )

    programs = sub.add_parser(
        "programs",
        help="Compare DTI minimum down payment across loan programs",
    )
    programs.add_argument("--price", type=float, required=True)
    programs.add_argument("--income", type=float, required=True)
    programs.add_argument("--debt", type=float, default=0.0)
    programs.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(programs)
    programs.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )

    analyze_dti = sub.add_parser(
        "analyze-dti",
        help="Diagnose down payment vs DTI with binding constraints and income sensitivity",
    )
    analyze_dti.add_argument("--price", type=float, required=True)
    analyze_dti.add_argument("--income", type=float, required=True)
    analyze_dti.add_argument("--debt", type=float, default=0.0)
    analyze_dti.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(analyze_dti)
    analyze_dti.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    analyze_dti.add_argument("--min-down-pct", type=float, default=0.03)
    analyze_dti.add_argument(
        "--program",
        choices=["conventional", "fha", "va"],
        default=None,
        help="Loan program rules for down payment floor and mortgage insurance",
    )
    analyze_dti.add_argument(
        "--down-pcts",
        type=str,
        default="3,5,10,15,20",
        help="Comma-separated down payment percentages to evaluate",
    )
    analyze_dti.add_argument(
        "--income-mults",
        type=str,
        default="0.75,0.85,1.0,1.15,1.30",
        help="Comma-separated income multipliers for sensitivity sweep",
    )
    analyze_dti.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the DTI diagnostic",
    )

    frontier = sub.add_parser(
        "frontier",
        help="Model down payment × income affordability tradeoffs for a fixed home price",
    )
    frontier.add_argument("--price", type=float, required=True)
    frontier.add_argument("--income", type=float, required=True)
    frontier.add_argument("--debt", type=float, default=0.0)
    frontier.add_argument("--down", type=float, default=0.0, help="Current down payment in dollars")
    frontier.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(frontier)
    frontier.add_argument(
        "--band",
        choices=["conservative", "moderate", "stretch"],
        default="conservative",
    )
    frontier.add_argument("--min-down-pct", type=float, default=0.03)
    frontier.add_argument(
        "--program",
        choices=["conventional", "fha", "va"],
        default=None,
        help="Loan program rules for down payment floor and mortgage insurance",
    )
    frontier.add_argument(
        "--down-pcts",
        type=str,
        default="3,5,10,15,20",
        help="Comma-separated down payment percentages to evaluate",
    )
    frontier.add_argument(
        "--income-mults",
        type=str,
        default="0.75,0.85,1.0,1.15,1.30",
        help="Comma-separated income multipliers for the frontier grid",
    )
    frontier.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for the affordability frontier",
    )

    compare_catalog = sub.add_parser(
        "compare-catalog",
        help="Run preset fixed vs ARM calculator scenarios",
    )
    compare_catalog.add_argument(
        "--list",
        action="store_true",
        help="List available loan and purchase presets",
    )
    compare_catalog.add_argument(
        "--loan",
        metavar="PRESET_ID",
        help="Run one loan-only preset (e.g. five_one_standard)",
    )
    compare_catalog.add_argument(
        "--purchase",
        metavar="PRESET_ID",
        help="Run one purchase preset (e.g. starter_home)",
    )
    compare_catalog.add_argument(
        "--loan-matrix",
        action="store_true",
        help="Compare all loan presets in a summary table",
    )
    compare_catalog.add_argument(
        "--purchase-matrix",
        action="store_true",
        help="Compare all purchase presets with DTI outcomes and recommendations",
    )
    compare_catalog.add_argument(
        "--loan-timeline",
        metavar="PRESET_ID",
        help="Show year-by-year timeline for one loan preset",
    )

    metro_trends = sub.add_parser(
        "metro-trends",
        help="Browse metro median home price trends from bundled CSV data",
    )
    metro_trends.add_argument(
        "--metro",
        metavar="METRO_ID",
        help="Show year-by-year trend for one metro (omit to list all metros)",
    )
    metro_trends.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Optional path to a metro home price trends CSV file",
    )
    metro_trends.add_argument(
        "--project-years",
        type=int,
        default=None,
        metavar="N",
        help="Project median price N years forward from the latest observation (requires --metro)",
    )
    metro_trends.add_argument(
        "--rank",
        action="store_true",
        help="Rank metros by total price change with compound annual growth rate",
    )
    metro_trends.add_argument(
        "--max-price",
        type=float,
        default=None,
        metavar="PRICE",
        help="Only include metros at or below this median price (latest year unless --year is set)",
    )
    metro_trends.add_argument(
        "--year",
        type=int,
        default=None,
        metavar="YEAR",
        help="Calendar year used with --max-price filtering",
    )

    args = parser.parse_args()

    if args.command == "savings":
        snaps = savings_trajectory(
            starting_balance=args.start,
            monthly_contribution=args.monthly,
            annual_return=args.annual_return,
            months=args.years * 12,
        )
        final = snaps[-1]
        print(f"Month {final.month}: balance ${final.balance:,.2f}")
    elif args.command == "mortgage":
        payment = mortgage_payment(
            principal=args.principal,
            annual_rate=args.rate,
            term_years=args.years,
        )
        interest = total_interest(
            principal=args.principal,
            annual_rate=args.rate,
            term_years=args.years,
        )
        print(f"Monthly P&I: ${payment:,.2f}")
        print(f"Total interest: ${interest:,.2f}")
    elif args.command == "compare":
        result = analyze_fixed_arm_scenario(
            FixedArmScenarioInputs(
                principal=args.principal,
                term_years=args.years,
                fixed_rate=args.fixed_rate,
                arm_intro_rate=args.arm_intro,
                arm_adjusted_rate=args.arm_adjusted,
                intro_years=args.intro_years,
            )
        )
        print(format_fixed_arm_scenario(result))
    elif args.command == "compare-timeline":
        timeline = build_fixed_arm_timeline(
            FixedArmScenarioInputs(
                principal=args.principal,
                term_years=args.years,
                fixed_rate=args.fixed_rate,
                arm_intro_rate=args.arm_intro,
                arm_adjusted_rate=args.arm_adjusted,
                intro_years=args.intro_years,
            )
        )
        if args.format == "json":
            print(format_fixed_arm_timeline_json(timeline))
        else:
            print(format_fixed_arm_timeline(timeline))
    elif args.command == "compare-purchase":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=args.down,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            loan_term_years=args.years,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args, loan_term_years=args.years),
            overrides=_market_overrides(args),
        )
        comparison = compare_fixed_arm_purchase(
            scenario,
            arm_intro_rate=args.arm_intro,
            arm_adjusted_rate=args.arm_adjusted,
            intro_years=args.intro_years,
            band_label=args.band,
        )
        print(format_fixed_arm_purchase_comparison(comparison))
    elif args.command == "compare-report":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=args.down,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            loan_term_years=args.years,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args, loan_term_years=args.years),
            overrides=_market_overrides(args),
        )
        report_kwargs: dict = dict(
            scenario=scenario,
            arm_intro_rate=args.arm_intro,
            arm_adjusted_rate=args.arm_adjusted,
            intro_years=args.intro_years,
            band_label=args.band,
        )
        report_adjusted_rates = _parse_adjusted_rates(args.adjusted_rates)
        if report_adjusted_rates is not None:
            report_kwargs["sweep_adjusted_rates"] = report_adjusted_rates
        report = fixed_arm_decision_report(**report_kwargs)
        if args.format == "json":
            print(format_fixed_arm_decision_report_json(report))
        else:
            print(format_fixed_arm_decision_report(report))
    elif args.command == "compare-sensitivity":
        kwargs: dict = dict(
            principal=args.principal,
            term_years=args.years,
            fixed_rate=args.fixed_rate,
            arm_intro_rate=args.arm_intro,
            intro_years=args.intro_years,
        )
        adjusted_rates = _parse_adjusted_rates(args.adjusted_rates)
        if adjusted_rates is not None:
            kwargs["adjusted_rates"] = adjusted_rates
        sensitivity = sweep_arm_adjusted_rates(**kwargs)
        print(format_arm_rate_sensitivity(sensitivity))
    elif args.command == "compare-sensitivity-purchase":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=args.down,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            loan_term_years=args.years,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args, loan_term_years=args.years),
            overrides=_market_overrides(args),
        )
        purchase_kwargs: dict = dict(
            scenario=scenario,
            arm_intro_rate=args.arm_intro,
            intro_years=args.intro_years,
            band_label=args.band,
        )
        purchase_adjusted_rates = _parse_adjusted_rates(args.adjusted_rates)
        if purchase_adjusted_rates is not None:
            purchase_kwargs["adjusted_rates"] = purchase_adjusted_rates
        purchase_sensitivity = sweep_arm_adjusted_rates_purchase(**purchase_kwargs)
        print(format_arm_purchase_sensitivity(purchase_sensitivity))
    elif args.command == "bands":
        provider = get_provider(args.provider)
        base_inputs = AffordabilityInputs(
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            down_payment=args.down,
            mortgage_rate=args.rate,
        )
        inputs = apply_market_to_affordability_inputs(
            base_inputs,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        for band in affordability_bands(inputs):
            print(
                f"{band.label:12} price ${band.max_home_price:,.0f}  "
                f"PITI ${band.estimated_piti:,.0f}/mo  "
                f"back-end DTI {band.back_end_dti:.1%}"
            )
    elif args.command == "check":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=args.down,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            closing_costs=args.closing,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        if args.recommend:
            if args.savings is not None:
                evaluation = evaluate_down_payment_dti_affordability(
                    scenario,
                    starting_balance=args.savings,
                    monthly_contribution=args.monthly_save,
                    min_down_payment_pct=args.min_down_pct,
                    loan_program=args.program,
                    band_label=args.band,
                )
                if args.format == "json":
                    print(format_down_payment_dti_affordability_evaluation_json(evaluation))
                else:
                    print(format_down_payment_dti_affordability_evaluation(evaluation))
            else:
                summary = summarize_purchase_affordability(
                    scenario,
                    min_down_payment_pct=args.min_down_pct,
                    loan_program=args.program,
                    band_label=args.band,
                )
                if args.format == "json":
                    print(format_purchase_affordability_summary_json(summary))
                else:
                    print(format_purchase_affordability_summary(summary))
        elif args.savings is not None:
            readiness = check_purchase_readiness(
                scenario,
                starting_balance=args.savings,
                monthly_contribution=args.monthly_save,
                min_down_payment_pct=args.min_down_pct,
                loan_program=args.program,
                band_label=args.band,
            )
            result = readiness.affordability
            print(f"Overall: {'PASS' if readiness.passes else 'FAIL'}")
            print(f"  DTI check: {'PASS' if readiness.passes_dti else 'FAIL'}")
            print(f"  Savings check: {'PASS' if readiness.passes_savings else 'FAIL'}")
            print(f"  Cash required: ${readiness.cash_required:,.0f}")
            if readiness.months_until_ready is not None:
                print(f"  Months until down payment saved: {readiness.months_until_ready}")
            print(f"  PITI: ${result.estimated_piti:,.0f}/mo")
            if result.estimated_pmi_monthly > 0:
                print(f"  PMI: ${result.estimated_pmi_monthly:,.0f}/mo")
            print(f"  Front-end DTI: {result.front_end_dti:.1%}")
            print(f"  Back-end DTI: {result.back_end_dti:.1%}")
            print(f"  Down payment: {result.down_payment_pct:.1%}  LTV: {result.ltv:.1%}")
            if result.pmi_required:
                if result.estimated_pmi_monthly > 0:
                    print(f"  PMI: ${result.estimated_pmi_monthly:,.0f}/mo (LTV > 80%)")
                else:
                    print("  PMI likely required (LTV > 80%)")
            for reason in result.reasons:
                print(f"  - {reason}")
        else:
            result = check_against_band(scenario, band_label=args.band)
            if args.program is not None:
                result = check_affordability(
                    scenario,
                    loan_program=args.program,
                    band_label=args.band,
                )
            print(f"Result: {'PASS' if result.passes else 'FAIL'} ({args.band} band)")
            print(f"  PITI: ${result.estimated_piti:,.0f}/mo")
            if result.estimated_pmi_monthly > 0:
                print(f"  PMI: ${result.estimated_pmi_monthly:,.0f}/mo")
            print(f"  Front-end DTI: {result.front_end_dti:.1%}")
            print(f"  Back-end DTI: {result.back_end_dti:.1%}")
            print(f"  Down payment: {result.down_payment_pct:.1%}  LTV: {result.ltv:.1%}")
            if result.pmi_required:
                if result.estimated_pmi_monthly > 0:
                    print(f"  PMI: ${result.estimated_pmi_monthly:,.0f}/mo (LTV > 80%)")
                else:
                    print("  PMI likely required (LTV > 80%)")
            for reason in result.reasons:
                print(f"  - {reason}")
    elif args.command == "model":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=0.0,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            closing_costs=args.closing,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        down_pcts = tuple(float(x.strip()) / 100 for x in args.down_pcts.split(","))
        if args.savings is not None:
            purchase_plan = plan_purchase_affordability(
                scenario,
                starting_balance=args.savings,
                monthly_contribution=args.monthly_save,
                annual_return=args.annual_return,
                min_down_payment_pct=args.min_down_pct,
                loan_program=args.program,
                band_label=args.band,
                down_payment_pcts=down_pcts,
            )
            if args.format == "json":
                print(format_purchase_affordability_plan_json(purchase_plan))
            else:
                print(format_purchase_affordability_plan(purchase_plan))
        else:
            result = model_down_payment_dti(
                scenario,
                down_payment_pcts=down_pcts,
                min_down_payment_pct=args.min_down_pct,
                loan_program=args.program,
                band_label=args.band,
            )
            if args.format == "json":
                print(format_down_payment_dti_model_json(result))
            else:
                print(format_down_payment_dti_model(result))
    elif args.command == "plan":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=0.0,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            closing_costs=args.closing,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        purchase_plan = plan_purchase_affordability(
            scenario,
            starting_balance=args.savings,
            monthly_contribution=args.monthly_save,
            annual_return=args.annual_return,
            target_months=args.target_months,
            min_down_payment_pct=args.min_down_pct,
            loan_program=args.program,
            band_label=args.band,
        )
        if args.format == "json":
            print(format_purchase_affordability_plan_json(purchase_plan))
        else:
            print(format_purchase_affordability_plan(purchase_plan))
    elif args.command == "target-report":
        provider = get_provider(args.provider)
        rows = target_home_report_by_year(
            home_price=args.price,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            starting_balance=args.start,
            monthly_contribution=args.monthly,
            annual_return=args.annual_return,
            years=args.years,
            income_growth_rate=args.income_growth,
            closing_costs=args.closing,
            mortgage_rate=args.rate,
            band_label=args.band,
            provider=provider,
            metro_id=args.metro,
            reference_year=args.reference_year,
            market_overrides=_market_overrides(args),
        )
        print(format_target_home_report(rows, home_price=args.price, band_label=args.band))
    elif args.command == "analyze-dti":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=0.0,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        down_pcts = tuple(float(x.strip()) / 100 for x in args.down_pcts.split(","))
        income_mults = tuple(float(x.strip()) for x in args.income_mults.split(","))
        diagnostic = diagnose_down_payment_affordability(
            scenario,
            down_payment_pcts=down_pcts,
            income_multipliers=income_mults,
            min_down_payment_pct=args.min_down_pct,
            loan_program=args.program,
            band_label=args.band,
        )
        if args.format == "json":
            print(format_down_payment_affordability_diagnostic_json(diagnostic))
        else:
            print(format_down_payment_affordability_diagnostic(diagnostic))
    elif args.command == "frontier":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=args.down,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        down_pcts = tuple(float(x.strip()) / 100 for x in args.down_pcts.split(","))
        income_mults = tuple(float(x.strip()) for x in args.income_mults.split(","))
        frontier_result = model_affordability_frontier(
            scenario,
            down_payment_pcts=down_pcts,
            income_multipliers=income_mults,
            min_down_payment_pct=args.min_down_pct,
            loan_program=args.program,
            band_label=args.band,
        )
        if args.format == "json":
            print(format_affordability_frontier_json(frontier_result))
        else:
            print(format_affordability_frontier(frontier_result))
    elif args.command == "programs":
        provider = get_provider(args.provider)
        base_scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=0.0,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            query=_market_query(args),
            overrides=_market_overrides(args),
        )
        comparison = compare_loan_program_dti(
            scenario,
            band_label=args.band,
        )
        print(format_loan_program_dti_comparison(comparison))
    elif args.command == "report":
        rows = _run_affordability_report_by_year(args)
        print(format_affordability_report(rows, base_year=args.base_year))
    elif args.command == "range-report":
        rows = _run_affordability_report_by_year(args)
        if args.format == "json":
            print(format_affordability_range_report_json(rows, base_year=args.base_year))
        else:
            print(format_affordability_range_report(rows, base_year=args.base_year))
    elif args.command == "compare-catalog":
        catalog = default_fixed_arm_catalog()
        selected = sum(
            bool(flag)
            for flag in (
                args.list,
                args.loan,
                args.purchase,
                args.loan_matrix,
                args.purchase_matrix,
                args.loan_timeline,
            )
        )
        if selected != 1:
            parser.error(
                "compare-catalog requires exactly one of "
                "--list, --loan, --purchase, --loan-matrix, --purchase-matrix, "
                "or --loan-timeline"
            )
        if args.list:
            print(format_catalog_listing(catalog))
        elif args.loan is not None:
            print(format_loan_preset_detail(args.loan, catalog=catalog))
        elif args.loan_timeline is not None:
            print(format_loan_preset_timeline(args.loan_timeline, catalog=catalog))
        elif args.purchase is not None:
            print(format_purchase_preset_detail(args.purchase, catalog=catalog))
        elif args.loan_matrix:
            print(format_loan_preset_matrix(catalog))
        else:
            print(format_purchase_preset_matrix(catalog))
    elif args.command == "metro-trends":
        from pathlib import Path

        from homeafford.market.metro_trends import MetroTrendCatalog

        if args.csv is not None:
            catalog = MetroTrendCatalog.from_csv(Path(args.csv))
        else:
            catalog = default_metro_trend_catalog()
        if args.project_years is not None:
            if args.metro is None:
                parser.error("--project-years requires --metro")
            if args.project_years < 0:
                parser.error("--project-years must be non-negative")
            print(
                format_metro_trend_projection(
                    catalog,
                    metro_id=args.metro,
                    years_forward=args.project_years,
                )
            )
        elif args.rank:
            print(
                format_metro_trends_ranked(
                    catalog,
                    max_price=args.max_price,
                    year=args.year,
                )
            )
        else:
            print(
                format_metro_trends_table(
                    catalog,
                    metro_id=args.metro,
                    max_price=args.max_price,
                    year=args.year,
                )
            )


if __name__ == "__main__":
    main()
