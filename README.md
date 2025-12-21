# homeafford

Personal finance simulator for planning a home purchase: model savings growth, estimate mortgage payments, and map income to affordability bands.

## Features

- **Savings trajectory** — project account balances with monthly contributions and annual return assumptions
- **Mortgage math** — amortizing payment, total interest, and remaining balance at any month
- **Affordability bands** — conservative, moderate, and stretch price targets from gross income and debt ratios
- **Purchase checks** — forward DTI and down-payment validation for a specific home, plus savings readiness

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
```

## CLI

```bash
homeafford savings --start 15000 --monthly 800 --years 5 --return 0.04
homeafford mortgage --principal 450000 --rate 0.065 --years 30
homeafford bands --income 120000 --debt 450 --down 60000
homeafford check --price 520000 --down 104000 --income 120000 --debt 450
homeafford check --price 520000 --down 104000 --income 120000 --savings 60000 --monthly-save 1500
```

## Development

```bash
pytest
```

## License

MIT
