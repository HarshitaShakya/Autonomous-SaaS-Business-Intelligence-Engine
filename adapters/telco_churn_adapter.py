"""Telco Customer Churn adapter.

Maps the IBM / Kaggle *WA_Fn-UseC_-Telco-Customer-Churn* dataset onto the
canonical ``CanonicalRecord`` schema.

Source columns → canonical mapping
-----------------------------------
customerID        → customer_id          (direct)
tenure            → tenure_days          (× 30 — months to days)
                  → signup_date          (synthetic: ref_date − tenure_days)
Contract          → plan_tier            (direct)
                  → billing_cycle        ("monthly" / "annual" / "biennial")
MonthlyCharges    → mrr                  (direct)
TotalCharges      → service_features     (cleaned; 11 blanks → 0.0)
PaymentMethod     → payment_status       (see _PAYMENT_MAP)
TechSupport       → support_interactions (1 if "Yes", else 0)
Churn             → churn_flag           ("Yes" → True)
                  → churn_date           (signup_date + tenure_days if churned)
(no CSAT column)  → satisfaction_score   (None)

All remaining service / demographic columns are placed in
``service_features`` as binary or categorical values.

Data quality notes
------------------
* 11 rows have blank ``TotalCharges`` (all ``tenure == 0``).  We impute 0.0.
* Dates are synthetic — the dataset provides only tenure in months.
  We use **2023-12-31** as the reference observation date.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Any

from schemas.canonical import CanonicalRecord
from adapters import register

# Reference date — all synthetic dates are relative to this.
_REF_DATE = datetime.date(2023, 12, 31)

# PaymentMethod → canonical payment_status
_PAYMENT_MAP: dict[str, str] = {
    "Electronic check": "manual_electronic",
    "Mailed check": "manual_mail",
    "Bank transfer (automatic)": "auto_bank",
    "Credit card (automatic)": "auto_card",
}

# Contract → billing_cycle
_BILLING_CYCLE_MAP: dict[str, str] = {
    "Month-to-month": "monthly",
    "One year": "annual",
    "Two year": "biennial",
}

# Binary Yes/No columns that go into service_features
_BINARY_COLUMNS = [
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "PaperlessBilling",
]


def _parse_binary(value: str) -> int:
    """Convert Yes/No/0/1 to int, treating 'No …' variants as 0."""
    if value in ("Yes", "1"):
        return 1
    return 0


def _parse_total_charges(value: str) -> float:
    """Parse TotalCharges, handling blanks (11 rows where tenure == 0)."""
    stripped = value.strip()
    if stripped == "":
        return 0.0
    return float(stripped)


def _build_service_features(row: dict[str, str]) -> dict[str, Any]:
    """Extract all service / demographic columns into a flat dict.

    Values are kept as integers (0/1) for binary flags and strings for
    multi-valued categoricals so downstream feature engineering can handle
    them uniformly.
    """
    features: dict[str, Any] = {}

    for col in _BINARY_COLUMNS:
        raw = row[col]
        # Multi-valued columns like MultipleLines, OnlineSecurity, etc.
        if raw in ("No internet service", "No phone service"):
            features[col] = 0
        elif col == "InternetService":
            # Keep as categorical — it has 3 levels
            features[col] = raw  # "DSL", "Fiber optic", "No"
        elif col == "gender":
            features[col] = raw  # "Male", "Female"
        elif col == "SeniorCitizen":
            features[col] = int(raw)
        else:
            features[col] = _parse_binary(raw)

    # Continuous features
    features["TotalCharges"] = _parse_total_charges(row["TotalCharges"])
    features["PaymentMethod"] = row["PaymentMethod"]

    return features


def _row_to_record(row: dict[str, str]) -> CanonicalRecord:
    """Convert one CSV row into a ``CanonicalRecord``."""
    tenure_months = int(row["tenure"])
    tenure_days = tenure_months * 30

    signup_date = _REF_DATE - datetime.timedelta(days=tenure_days)

    churn_flag = row["Churn"].strip() == "Yes"
    churn_date = (
        _REF_DATE if churn_flag else None
    )

    # last_activity_date: for churned customers, this is the churn/reference
    # date; for active customers, also the reference date (last observation).
    last_activity_date = _REF_DATE

    return CanonicalRecord(
        customer_id=row["customerID"],
        signup_date=signup_date,
        plan_tier=row["Contract"],
        mrr=float(row["MonthlyCharges"]),
        billing_cycle=_BILLING_CYCLE_MAP.get(row["Contract"], "monthly"),
        payment_status=_PAYMENT_MAP.get(row["PaymentMethod"], "unknown"),
        tenure_days=tenure_days,
        last_activity_date=last_activity_date,
        support_interactions=_parse_binary(row["TechSupport"]),
        satisfaction_score=None,  # not available in this source
        churn_flag=churn_flag,
        churn_date=churn_date,
        service_features=_build_service_features(row),
    )


@register("telco_churn")
def load(path: str | Path) -> list[CanonicalRecord]:
    """Load the Telco Customer Churn CSV and return canonical records.

    Parameters
    ----------
    path : str or Path
        Path to ``WA_Fn-UseC_-Telco-Customer-Churn.csv`` (or the copy at
        ``data/raw/telco_churn.csv``).

    Returns
    -------
    list[CanonicalRecord]
        One record per customer (7 043 expected).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at {path}")

    records: list[CanonicalRecord] = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            records.append(_row_to_record(row))

    return records
