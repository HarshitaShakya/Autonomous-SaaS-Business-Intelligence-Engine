"""Post-execution verification engine.

After an action is executed, verification checks whether the
adapter's state matches expectations (e.g. was the feature flag
actually enabled? Is the rollout percentage correct?).
"""

from __future__ import annotations

from typing import Any

from action_agent.adapters.base import AdapterResult
from action_agent.schemas.action import ActionPlan, ActionType, VerificationStatus


class VerificationResult:
    """Outcome of verification checks."""

    def __init__(self) -> None:
        self.status: VerificationStatus = VerificationStatus.PENDING
        self.checks: dict[str, bool] = {}
        self.details: dict[str, Any] = {}

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED


class VerificationEngine:
    """Runs post-execution verification checks."""

    def verify(
        self,
        plan: ActionPlan,
        adapter_result: AdapterResult,
    ) -> VerificationResult:
        """Verify that execution achieved the intended state."""
        vr = VerificationResult()

        # Basic checks applicable to all action types
        vr.checks["adapter_success"] = adapter_result.success
        if not adapter_result.success:
            vr.status = VerificationStatus.FAILED
            vr.details["error"] = adapter_result.error or "Adapter reported failure"
            return vr

        # Type-specific checks
        checker = _VERIFIERS.get(plan.action_type, _verify_generic)
        checker(plan, adapter_result, vr)

        # Final verdict
        if all(vr.checks.values()):
            vr.status = VerificationStatus.PASSED
        else:
            vr.status = VerificationStatus.FAILED
            vr.details["failed_checks"] = [k for k, v in vr.checks.items() if not v]

        return vr


# ---------------------------------------------------------------------------
# Type-specific verifiers
# ---------------------------------------------------------------------------

def _verify_experiment(plan: ActionPlan, result: AdapterResult, vr: VerificationResult) -> None:
    details = result.details
    expected_rollout = plan.parameters.get("rollout_percentage")
    if expected_rollout is not None:
        actual = details.get("rollout_pct")
        vr.checks["rollout_percentage_matches"] = actual == expected_rollout

    vr.checks["experiment_active"] = details.get("active", False)

    expected_segment = plan.target_segment
    if expected_segment:
        vr.checks["segment_matches"] = details.get("segment") == expected_segment


def _verify_ux(plan: ActionPlan, result: AdapterResult, vr: VerificationResult) -> None:
    details = result.details
    vr.checks["flag_enabled"] = details.get("enabled", False)

    expected_rollout = plan.parameters.get("rollout_percentage")
    if expected_rollout is not None:
        vr.checks["rollout_percentage_matches"] = details.get("rollout_pct") == expected_rollout

    expected_segment = plan.target_segment
    if expected_segment:
        vr.checks["segment_matches"] = details.get("segment") == expected_segment


def _verify_pricing(plan: ActionPlan, result: AdapterResult, vr: VerificationResult) -> None:
    details = result.details
    vr.checks["discount_active"] = details.get("active", False)

    expected_disc = plan.parameters.get("discount_percentage")
    if expected_disc is not None:
        vr.checks["discount_matches"] = details.get("discount_pct") == expected_disc


def _verify_alert(plan: ActionPlan, result: AdapterResult, vr: VerificationResult) -> None:
    # For notifications, adapter success is sufficient
    vr.checks["notification_sent"] = result.success


def _verify_generic(plan: ActionPlan, result: AdapterResult, vr: VerificationResult) -> None:
    vr.checks["action_acknowledged"] = result.success


_VERIFIERS = {
    ActionType.EXPERIMENT: _verify_experiment,
    ActionType.UX_UPDATE: _verify_ux,
    ActionType.PRICING_CHANGE: _verify_pricing,
    ActionType.ALERT: _verify_alert,
    ActionType.RETENTION_INTERVENTION: _verify_experiment,  # same verification as experiments
}
