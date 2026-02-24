"""JSON serialization helpers for DTI affordability results."""

from __future__ import annotations

import json

from homeafford.check import AffordabilityCheckResult


def affordability_check_to_dict(check: AffordabilityCheckResult) -> dict[str, object]:
    return {
        "passes": check.passes,
        "passes_front_end": check.passes_front_end,
        "passes_back_end": check.passes_back_end,
        "passes_down_payment": check.passes_down_payment,
        "front_end_dti": check.front_end_dti,
        "back_end_dti": check.back_end_dti,
        "ltv": check.ltv,
        "down_payment_pct": check.down_payment_pct,
        "loan_amount": check.loan_amount,
        "estimated_piti": check.estimated_piti,
        "estimated_pmi_monthly": check.estimated_pmi_monthly,
        "pmi_required": check.pmi_required,
        "reasons": list(check.reasons),
        "band_label": check.band_label,
    }


def dumps_dti_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2)
