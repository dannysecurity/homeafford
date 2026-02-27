# homeafford

Personal finance simulator for planning a home purchase: model savings growth, estimate mortgage payments, and map income to affordability bands.

## Features

- **Savings trajectory** — project account balances with monthly contributions and annual return assumptions
- **Mortgage math** — amortizing payment, total interest, and remaining balance at any month
- **Fixed vs ARM scenarios** — compare hybrid ARM payment shock, intro-period savings, and break-even timing against a fixed-rate loan
- **Fixed vs ARM decision report** — unified purchase comparison with DTI impact, optional rate sweep, and a recommendation
- **Fixed vs ARM scenario catalog** — named loan and purchase presets with side-by-side loan and purchase comparison matrices
- **ARM rate sensitivity** — sweep post-adjustment rates to see when fixed wins and how high rates can rise before DTI caps fail
- **Affordability bands** — conservative, moderate, and stretch price targets from gross income and debt ratios
- **Purchase checks** — forward DTI and down-payment validation for a specific home, plus savings readiness
- **Down payment vs DTI model** — sweep down payment levels for a target home and solve for the minimum down that passes DTI caps
- **DTI binding analysis** — identify which constraint (front-end, back-end, or down payment floor) binds at each down level, with cap headroom
- **Income DTI sensitivity** — sweep income multipliers and solve for minimum gross income to pass DTI at a fixed down payment
- **Affordability diagnostic** — combined down payment sweep, binding analysis, and income sensitivity in one report
- **Loan program comparison** — compare conventional, FHA, and VA minimum down payments and DTI outcomes for the same target home
- **Purchase affordability plan** — combine DTI minimum down with a savings timeline to answer when you can buy
- **Yearly affordability report** — project how conservative, moderate, and stretch price targets change as savings grow
- **Affordable range report** — compact year-by-year view of the conservative-through-stretch price window
- **Target home report** — year-by-year readiness for one fixed home price as savings and income grow

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick start

```python
from homeafford import (
    AffordabilityInputs,
    affordability_bands,
    mortgage_payment,
    savings_trajectory,
)

# Savings: $15k today, $800/mo for 5 years at 4% annual return
trajectory = savings_trajectory(
    starting_balance=15_000,
    monthly_contribution=800,
    annual_return=0.04,
    months=60,
)
print(f"Balance in 5 years: ${trajectory[-1].balance:,.0f}")

# Mortgage: $450k loan, 6.5% APR, 30-year term
payment = mortgage_payment(principal=450_000, annual_rate=0.065, term_years=30)
print(f"Monthly P&I: ${payment:,.2f}")

# Fixed vs 5/1 ARM: payment shock and break-even analysis
from homeafford import FixedArmScenarioInputs, analyze_fixed_arm_scenario, format_fixed_arm_scenario

scenario = analyze_fixed_arm_scenario(
    FixedArmScenarioInputs(
        principal=400_000,
        term_years=30,
        fixed_rate=0.065,
        arm_intro_rate=0.055,
        arm_adjusted_rate=0.075,
        intro_years=5,
    )
)
print(format_fixed_arm_scenario(scenario))

# Sweep ARM post-adjustment rates: when does fixed win? Will DTI still pass?
from homeafford import (
    sweep_arm_adjusted_rates,
    sweep_arm_adjusted_rates_purchase,
    format_arm_rate_sensitivity,
    format_arm_purchase_sensitivity,
)

sensitivity = sweep_arm_adjusted_rates(
    principal=400_000,
    term_years=30,
    fixed_rate=0.065,
    arm_intro_rate=0.055,
    adjusted_rates=(0.06, 0.07, 0.08, 0.09, 0.10),
)
print(format_arm_rate_sensitivity(sensitivity))

# Affordability from $120k gross income
bands = affordability_bands(
    AffordabilityInputs(
        gross_annual_income=120_000,
        monthly_debt_payments=450,
        down_payment=60_000,
        property_tax_rate=0.012,
        insurance_annual=1_800,
        hoa_monthly=0,
    )
)
for band in bands:
    print(f"{band.label:14} max price ${band.max_home_price:,.0f}  (PITI ${band.estimated_piti:,.0f}/mo)")

# Check a specific purchase against DTI and down-payment rules
from homeafford import PurchaseScenario, check_against_band, check_purchase_readiness

scenario = PurchaseScenario(
    home_price=520_000,
    down_payment=104_000,
    gross_annual_income=120_000,
    monthly_debt_payments=450,
)
check = check_against_band(scenario, band_label="conservative")
print(f"Affordable: {check.passes}  back-end DTI {check.back_end_dti:.1%}")

readiness = check_purchase_readiness(
    scenario,
    starting_balance=60_000,
    monthly_contribution=1_500,
    band_label="conservative",
)
print(f"Ready to buy: {readiness.passes}  cash needed ${readiness.cash_required:,.0f}")

# Model down payment levels vs DTI for a target home, then plan savings timeline
from homeafford import (
    model_down_payment_dti,
    plan_purchase_affordability,
    format_purchase_affordability_plan,
    target_home_report_by_year,
    format_target_home_report,
)

target = PurchaseScenario(
    home_price=550_000,
    down_payment=0.0,
    gross_annual_income=130_000,
    monthly_debt_payments=500,
    closing_costs=15_000,
)
plan = plan_purchase_affordability(
    target,
    starting_balance=40_000,
    monthly_contribution=2_000,
    band_label="conservative",
)
print(format_purchase_affordability_plan(plan))

rows = target_home_report_by_year(
    home_price=550_000,
    gross_annual_income=130_000,
    monthly_debt_payments=500,
    starting_balance=40_000,
    monthly_contribution=2_000,
    years=5,
    closing_costs=15_000,
)
print(format_target_home_report(rows, home_price=550_000))

# Compare loan programs for the same target home and DTI band
from homeafford import compare_loan_program_dti, format_loan_program_dti_comparison

comparison = compare_loan_program_dti(target, band_label="conservative")
print(format_loan_program_dti_comparison(comparison))
```

## CLI

```bash
homeafford savings --start 15000 --monthly 800 --years 5 --return 0.04
homeafford mortgage --principal 450000 --rate 0.065 --years 30
homeafford compare --principal 400000 --fixed-rate 0.065 --arm-intro 0.055 --arm-adjusted 0.075 --intro-years 5
homeafford compare-purchase --price 500000 --down 100000 --income 150000 --arm-intro 0.055 --arm-adjusted 0.075 --band conservative
homeafford compare-report --price 500000 --down 100000 --income 150000 --arm-intro 0.055 --arm-adjusted 0.075 --adjusted-rates 0.07,0.09,0.11 --band conservative
homeafford compare-report --price 500000 --down 100000 --income 150000 --arm-intro 0.055 --arm-adjusted 0.075 --format json
homeafford compare-sensitivity --principal 400000 --fixed-rate 0.065 --arm-intro 0.055 --adjusted-rates 0.06,0.07,0.08,0.09,0.10
homeafford compare-sensitivity-purchase --price 500000 --down 100000 --income 150000 --arm-intro 0.055 --band conservative
homeafford compare-catalog --list
homeafford compare-catalog --loan ten_one_jumbo
homeafford compare-catalog --purchase low_down_starter
homeafford compare-catalog --loan-matrix
homeafford compare-catalog --purchase-matrix
homeafford bands --income 120000 --debt 450 --down 60000
homeafford check --price 520000 --down 104000 --income 120000 --debt 450
homeafford check --price 520000 --down 104000 --income 120000 --savings 60000 --monthly-save 1500
homeafford model --price 550000 --income 130000 --debt 500 --band conservative --program fha --format json
homeafford analyze-dti --price 550000 --income 130000 --debt 500 --band conservative --down-pcts 3,5,10,15,20
homeafford analyze-dti --price 550000 --income 130000 --debt 500 --band conservative --format json
homeafford programs --price 550000 --income 130000 --debt 500 --band conservative
homeafford plan --price 550000 --income 130000 --debt 500 --savings 40000 --monthly-save 2000 --closing 15000 --program va --format json
homeafford report --income 120000 --debt 450 --start 15000 --monthly 800 --years 5 --return 0.04
homeafford range-report --income 120000 --debt 450 --start 15000 --monthly 800 --years 5 --return 0.04
homeafford range-report --income 120000 --start 15000 --years 5 --base-year 2026
homeafford range-report --income 120000 --start 15000 --years 5 --format json
homeafford range-report --income 100000 --years 0 --provider csv-metro --metro 35620 --reference-year 2023
homeafford target-report --price 550000 --income 130000 --start 40000 --monthly 2000 --years 5 --closing 15000
homeafford metro-trends
homeafford metro-trends --metro 19100
homeafford metro-trends --metro 45300 --project-years 3
homeafford metro-trends --metro 41740 --project-years 3
homeafford metro-trends --rank
```

## Development

```bash
pytest
```

## License

MIT
