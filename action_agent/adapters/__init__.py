"""Adapter package — abstract interfaces and mock implementations."""

from action_agent.adapters.base import (
    AdapterResult,
    ExperimentAdapter,
    FeatureFlagAdapter,
    NotificationAdapter,
    PricingAdapter,
)

__all__ = [
    "AdapterResult",
    "ExperimentAdapter",
    "FeatureFlagAdapter",
    "NotificationAdapter",
    "PricingAdapter",
]
