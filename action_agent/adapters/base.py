"""Abstract adapter interfaces for external systems.

Every external integration (feature flags, pricing, experiments,
notifications) is accessed through an adapter so the core logic
never couples to a specific vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AdapterResult(BaseModel):
    """Standardised result from any adapter call."""

    success: bool
    adapter_name: str = ""
    action_performed: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    previous_state: dict[str, Any] = Field(
        default_factory=dict,
        description="State before the action — used for rollback.",
    )
    error: str | None = None


# ---------------------------------------------------------------------------
# Feature Flag Adapter
# ---------------------------------------------------------------------------

class FeatureFlagAdapter(ABC):
    """Interface for feature-flag services (LaunchDarkly, Flagsmith, etc.)."""

    @abstractmethod
    async def enable_flag(
        self, flag_key: str, segment: str, rollout_pct: float
    ) -> AdapterResult: ...

    @abstractmethod
    async def disable_flag(self, flag_key: str, segment: str) -> AdapterResult: ...

    @abstractmethod
    async def get_flag_state(self, flag_key: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Pricing Adapter
# ---------------------------------------------------------------------------

class PricingAdapter(ABC):
    """Interface for pricing / billing services (Stripe, Chargebee, etc.)."""

    @abstractmethod
    async def apply_discount(
        self, segment: str, discount_pct: float, duration_days: int
    ) -> AdapterResult: ...

    @abstractmethod
    async def revert_discount(self, segment: str) -> AdapterResult: ...

    @abstractmethod
    async def get_pricing_state(self, segment: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Experiment Adapter
# ---------------------------------------------------------------------------

class ExperimentAdapter(ABC):
    """Interface for A/B testing platforms (Optimizely, GrowthBook, etc.)."""

    @abstractmethod
    async def create_experiment(
        self,
        experiment_key: str,
        segment: str,
        rollout_pct: float,
        parameters: dict[str, Any],
    ) -> AdapterResult: ...

    @abstractmethod
    async def stop_experiment(self, experiment_key: str) -> AdapterResult: ...

    @abstractmethod
    async def get_experiment_state(self, experiment_key: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Notification Adapter
# ---------------------------------------------------------------------------

class NotificationAdapter(ABC):
    """Interface for alerting services (Slack, PagerDuty, email, etc.)."""

    @abstractmethod
    async def send_notification(
        self,
        channel: str,
        title: str,
        message: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> AdapterResult: ...
