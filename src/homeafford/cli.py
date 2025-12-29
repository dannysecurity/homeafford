"""Command-line interface for homeafford."""

from __future__ import annotations

import argparse

from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.check import PurchaseScenario, check_against_band, check_purchase_readiness
from homeafford.model import model_down_payment_dti
from homeafford.market.registry import available_providers, get_provider
from homeafford.market.resolve import apply_market_to_affordability_inputs, apply_market_to_purchase_scenario
from homeafford.mortgage import mortgage_payment, total_interest
from homeafford.mortgage_scenario import FixedArmScenarioInputs, analyze_fixed_arm_scenario, format_fixed_arm_scenario
from homeafford.report import affordability_report_by_year, format_affordability_report
from homeafford.savings import savings_trajectory


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
        help="Market data provider for rate and cost assumptions",
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
    check.add_argument("--savings", type=float, default=None, help="Current savings balance")
    check.add_argument("--monthly-save", type=float, default=0.0)
    check.add_argument("--closing", type=float, default=0.0)

    report = sub.add_parser(
        "report",
        help="Show affordability bands by year as savings grow",
    )
    report.add_argument("--income", type=float, required=True)
    report.add_argument("--debt", type=float, default=0.0)
    report.add_argument("--start", type=float, default=0.0, help="Starting savings balance")
    report.add_argument("--monthly", type=float, default=0.0, help="Monthly savings contribution")
    report.add_argument("--years", type=int, default=5)
    report.add_argument("--return", dest="annual_return", type=float, default=0.04)
    report.add_argument("--income-growth", type=float, default=0.0, help="Annual income growth rate")
    report.add_argument("--rate", type=float, default=0.065)
    _add_provider_arg(report)

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
        "--down-pcts",
        type=str,
        default="3,5,10,15,20",
        help="Comma-separated down payment percentages to evaluate",
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
            overrides=_market_overrides(args),
        )
        if args.savings is not None:
            readiness = check_purchase_readiness(
                scenario,
                starting_balance=args.savings,
                monthly_contribution=args.monthly_save,
                min_down_payment_pct=args.min_down_pct,
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
            print(f"Result: {'PASS' if result.passes else 'FAIL'} ({args.band} band)")
        print(f"  PITI: ${result.estimated_piti:,.0f}/mo")
        print(f"  Front-end DTI: {result.front_end_dti:.1%}")
        print(f"  Back-end DTI: {result.back_end_dti:.1%}")
        print(f"  Down payment: {result.down_payment_pct:.1%}  LTV: {result.ltv:.1%}")
        if result.pmi_required:
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
        )
        scenario = apply_market_to_purchase_scenario(
            base_scenario,
            provider,
            overrides=_market_overrides(args),
        )
        down_pcts = tuple(float(x.strip()) / 100 for x in args.down_pcts.split(","))
        result = model_down_payment_dti(
            scenario,
            down_payment_pcts=down_pcts,
            min_down_payment_pct=args.min_down_pct,
            band_label=args.band,
        )
        print(f"Down payment vs DTI model (${result.home_price:,.0f} home, {args.band} band)")
        if result.min_down_payment is not None:
            print(
                f"Minimum down for DTI pass: ${result.min_down_payment:,.0f} "
                f"({result.min_down_payment_pct:.1%})"
            )
        else:
            print("Minimum down for DTI pass: not reachable (debt exceeds back-end cap)")
        print(f"{'Down %':>7}  {'Down $':>12}  {'PITI':>10}  {'Front':>7}  {'Back':>7}  Pass")
        for row in result.rows:
            status = "yes" if row.check.passes else "no"
            print(
                f"{row.down_payment_pct:>6.1%}  "
                f"${row.down_payment:>11,.0f}  "
                f"${row.check.estimated_piti:>9,.0f}  "
                f"{row.check.front_end_dti:>6.1%}  "
                f"{row.check.back_end_dti:>6.1%}  "
                f"{status}"
            )
    elif args.command == "report":
        provider = get_provider(args.provider)
        rows = affordability_report_by_year(
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            starting_balance=args.start,
            monthly_contribution=args.monthly,
            annual_return=args.annual_return,
            years=args.years,
            income_growth_rate=args.income_growth,
            mortgage_rate=args.rate,
            provider=provider,
            market_overrides=_market_overrides(args),
        )
        print(format_affordability_report(rows))


if __name__ == "__main__":
    main()
