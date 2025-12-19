"""homeafford — savings, mortgage, and affordability planning."""

from homeafford.affordability import AffordabilityBand, AffordabilityInputs, affordability_bands
from homeafford.mortgage import mortgage_payment, remaining_balance, total_interest
from homeafford.savings import SavingsSnapshot, savings_trajectory

__all__ = [
    "AffordabilityBand",
    "AffordabilityInputs",
    "SavingsSnapshot",
    "affordability_bands",
    "mortgage_payment",
    "remaining_balance",
    "savings_trajectory",
    "total_interest",
]
