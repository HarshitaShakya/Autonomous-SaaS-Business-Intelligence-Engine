"""Canonical schema — the single contract between adapters and agents.

Every adapter transforms its raw source into a list of ``CanonicalRecord``
instances.  The three ML agents are written *once*, against this schema, and
never reference a source-specific column name directly.

Design decisions
----------------
* ``signup_date`` and ``last_activity_date`` are kept as ``datetime.date``
  rather than full timestamps — most SaaS / telco sources only have day-level
  granularity.
* ``satisfaction_score`` is ``Optional`` because not every source has a CSAT or
  NPS signal.  Agents must handle ``None`` gracefully (e.g. impute or skip).
* ``service_features`` is a flexible ``dict[str, Any]`` bag for source-specific
  columns that don't map onto the fixed fields but are still useful for the ML
  agents (service flags, demographic indicators, etc.).  Each adapter documents
  what it puts here.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CanonicalRecord(BaseModel):
    """One customer row in the source-agnostic internal schema.

    Attributes
    ----------
    customer_id : str
        Unique customer identifier from the source system.
    signup_date : date
        Date the customer first signed up / was onboarded.
        May be synthetic if the source only provides tenure.
    plan_tier : str
        Contract or subscription tier (e.g. "Month-to-month", "One year").
    mrr : float
        Monthly Recurring Revenue (or monthly charge equivalent).
    billing_cycle : str
        One of "monthly", "annual", "biennial", or similar.
    payment_status : str
        Describes payment reliability.  Examples: "auto_bank", "auto_card",
        "manual_mail", "manual_electronic".
    tenure_days : int
        Days since signup (converted from whatever unit the source uses).
    last_activity_date : date
        Most recent activity or observation date.
    support_interactions : int
        Count (or binary proxy) of support engagements.
    satisfaction_score : float | None
        CSAT, NPS, or review-based score.  ``None`` when the source doesn't
        provide one.
    churn_flag : bool
        ``True`` if the customer has churned.
    churn_date : date | None
        Date of churn event.  ``None`` for active customers.
    service_features : dict[str, Any]
        Bag of additional source-specific features that don't fit the fixed
        fields above.  Each adapter documents the keys it populates.
    """

    customer_id: str = Field(
        ..., description="Unique customer identifier from the source system."
    )
    signup_date: datetime.date = Field(
        ..., description="Date the customer first signed up."
    )
    plan_tier: str = Field(
        ..., description="Contract or subscription tier."
    )
    mrr: float = Field(
        ..., ge=0, description="Monthly Recurring Revenue."
    )
    billing_cycle: str = Field(
        ..., description="Billing cadence: monthly, annual, biennial, etc."
    )
    payment_status: str = Field(
        ..., description="Payment method reliability category."
    )
    tenure_days: int = Field(
        ..., ge=0, description="Days since customer signup."
    )
    last_activity_date: datetime.date = Field(
        ..., description="Most recent activity or observation date."
    )
    support_interactions: int = Field(
        ..., ge=0, description="Count or binary proxy of support engagements."
    )
    satisfaction_score: Optional[float] = Field(
        default=None,
        description="CSAT / NPS score.  None when unavailable.",
    )
    churn_flag: bool = Field(
        ..., description="True if the customer has churned."
    )
    churn_date: Optional[datetime.date] = Field(
        default=None,
        description="Date of churn event; None for active customers.",
    )
    service_features: dict[str, Any] = Field(
        default_factory=dict,
        description="Bag of additional source-specific features.",
    )
