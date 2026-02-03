"""Command-line interface for homeafford."""

from __future__ import annotations

import argparse

from homeafford.affordability import AffordabilityInputs, affordability_bands
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
from homeafford.model import (
    format_down_payment_dti_model,
    format_purchase_affordability_plan,
    model_down_payment_dti,
    plan_purchase_affordability,
)
from homeafford.market.registry import available_providers, format_provider_choices, get_provider
from homeafford.market.resolve import apply_market_to_affordability_inputs, apply_market_to_purchase_scenario
from homeafford.mortgage import mortgage_payment, total_interest
from homeafford.arm_sensitivity import (
    format_arm_purchase_sensitivity,
    format_arm_rate_sensitivity,
    sweep_arm_adjusted_rates,
    sweep_arm_adjusted_rates_purchase,
)
from homeafford.mortgage_scenario import (
    FixedArmScenarioInputs,
    analyze_fixed_arm_scenario,
    compare_fixed_arm_purchase,
    format_fixed_arm_purchase_comparison,
    format_fixed_arm_scenario,
)
from homeafford.report import (
    affordability_report_by_year,
    format_affordability_range_report,
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


def _market_query(args: argparse.Namespace, *, loan_term_years: int = 30):
    """Build a market query when the CLI supplies metro context."""
    from homeafford.market.query import MarketQuery

    metro_id = getattr(args, "metro", None)
    reference_year = getattr(args, "reference_year", None)
    if metro_id is None and reference_year is None:
        return None
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
    _add_provider_arg(parser)


def _run_affordability_report_by_year(args: argparse.Namespace):
    provider = get_provider(args.provider)
    return affordability_report_by_year(
        gross_annual_income=args.income,
        monthly_debt_payments=args.debt,
        starting_balance=args.start,
        monthly_contribution=args.monthly,
        annual_return=args.annual_return,
        years=args.years,
        income_growth_rate=args.income_growth,
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
        if args.savings is not None:
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
            print(format_purchase_affordability_plan(purchase_plan))
        else:
            result = model_down_payment_dti(
                scenario,
                down_payment_pcts=down_pcts,
                min_down_payment_pct=args.min_down_pct,
                loan_program=args.program,
                band_label=args.band,
            )
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
        print(format_affordability_report(rows))
    elif args.command == "range-report":
        rows = _run_affordability_report_by_year(args)
        print(format_affordability_range_report(rows))


if __name__ == "__main__":
    main()
