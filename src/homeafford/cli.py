"""Command-line interface for homeafford."""

from __future__ import annotations

import argparse

from homeafford.affordability import AffordabilityInputs, affordability_bands
from homeafford.check import PurchaseScenario, check_against_band, check_purchase_readiness
from homeafford.mortgage import mortgage_payment, total_interest
from homeafford.report import affordability_report_by_year
from homeafford.savings import savings_trajectory


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

    bands = sub.add_parser("bands", help="Estimate affordability bands")
    bands.add_argument("--income", type=float, required=True)
    bands.add_argument("--debt", type=float, default=0.0)
    bands.add_argument("--down", type=float, default=0.0)
    bands.add_argument("--rate", type=float, default=0.065)

    check = sub.add_parser("check", help="Check DTI and down payment for a purchase")
    check.add_argument("--price", type=float, required=True)
    check.add_argument("--down", type=float, required=True)
    check.add_argument("--income", type=float, required=True)
    check.add_argument("--debt", type=float, default=0.0)
    check.add_argument("--rate", type=float, default=0.065)
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
    elif args.command == "bands":
        for band in affordability_bands(
            AffordabilityInputs(
                gross_annual_income=args.income,
                monthly_debt_payments=args.debt,
                down_payment=args.down,
                mortgage_rate=args.rate,
            )
        ):
            print(
                f"{band.label:12} price ${band.max_home_price:,.0f}  "
                f"PITI ${band.estimated_piti:,.0f}/mo  "
                f"back-end DTI {band.back_end_dti:.1%}"
            )
    elif args.command == "check":
        scenario = PurchaseScenario(
            home_price=args.price,
            down_payment=args.down,
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            mortgage_rate=args.rate,
            closing_costs=args.closing,
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
    elif args.command == "report":
        rows = affordability_report_by_year(
            gross_annual_income=args.income,
            monthly_debt_payments=args.debt,
            starting_balance=args.start,
            monthly_contribution=args.monthly,
            annual_return=args.annual_return,
            years=args.years,
            income_growth_rate=args.income_growth,
            mortgage_rate=args.rate,
        )
        print(
            f"{'Year':>4}  {'Down $':>12}  {'Conservative':>14}  "
            f"{'Moderate':>14}  {'Stretch':>14}"
        )
        for row in rows:
            by_label = {band.label: band for band in row.bands}
            print(
                f"{row.year:4d}  ${row.down_payment:>10,.0f}  "
                f"${by_label['conservative'].max_home_price:>12,.0f}  "
                f"${by_label['moderate'].max_home_price:>12,.0f}  "
                f"${by_label['stretch'].max_home_price:>12,.0f}"
            )


if __name__ == "__main__":
    main()
