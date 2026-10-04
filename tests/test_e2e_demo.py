"""End-to-end demo scenario test.

Reproduces the exact demo scenario from the project spec:
"High-risk customer segment has a churn probability of 0.84.
Causal/feature analysis suggests onboarding friction is a major
retention driver. Start a 20% onboarding experiment for this segment."

This test verifies the complete pipeline from strategy recommendation
through execution, verification, audit, and rollback.
"""

import pytest


DEMO_PAYLOAD = {
    "recommendation_id": "rec_demo_e2e_001",
    "customer_segment": "high_churn_enterprise",
    "priority": "HIGH",
    "confidence": 0.91,
    "reason": (
        "Customers in the high_churn_enterprise segment have a churn probability of 0.84. "
        "Causal analysis via Double/Debiased Machine Learning indicates that onboarding "
        "friction (measured by time-to-first-value > 7 days) is the strongest causal driver "
        "of churn in this segment, with an Average Treatment Effect of -0.12 on 30-day retention."
    ),
    "recommended_action": {
        "type": "ux_experiment",
        "target": "redesigned_onboarding_v2",
        "description": "Enable the redesigned guided onboarding flow for high-churn enterprise users",
        "expected_outcome": "increase_30_day_retention",
        "parameters": {
            "rollout_percentage": 20
        }
    },
    "expected_impact": {
        "metric": "retention_rate",
        "direction": "increase",
        "estimated_change": 0.08
    },
    "constraints": {
        "max_rollout_percentage": 50,
        "requires_approval": False
    }
}


class TestEndToEndDemo:
    """Full demo scenario: recommendation → action → verify → audit → rollback."""

    @pytest.mark.asyncio
    async def test_full_demo_pipeline(self, executor, audit_repo):
        # ── Step 1–6: Execute ──
        result = await executor.execute(DEMO_PAYLOAD)

        assert result.recommendation_id == "rec_demo_e2e_001"
        assert result.action_type.value == "UX_UPDATE"
        assert result.execution_status.value == "SUCCESS"
        assert result.verification_status.value == "PASSED"
        assert result.risk_level == "LOW"
        assert result.policy_decision == "APPROVED"
        assert result.rollback_supported is True
        assert result.execution_mode.value == "DRY_RUN"

        # ── Step 7: Verify audit log was written ──
        audit = await audit_repo.get_by_action_id(result.action_id)
        assert audit is not None
        assert audit.execution_status == "SUCCESS"
        assert audit.verification_status == "PASSED"
        assert audit.confidence == 0.91

        # ── Step 8: Rollback ──
        rb = await executor.rollback_action(result.action_id)
        assert rb["rollback_status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_demo_idempotency(self, executor):
        """Same recommendation should not execute twice."""
        r1 = await executor.execute(DEMO_PAYLOAD)
        assert r1.execution_status.value == "SUCCESS"

        r2 = await executor.execute(DEMO_PAYLOAD)
        assert r2.execution_status.value == "ALREADY_EXECUTED"

    @pytest.mark.asyncio
    async def test_demo_preview(self, executor):
        """Preview shows what would happen without executing."""
        preview = await executor.preview(DEMO_PAYLOAD)

        assert preview["decision"] == "APPROVED"
        assert preview["action_type"] == "UX_UPDATE"
        assert preview["risk_level"] == "LOW"
        assert preview["rollback_supported"] is True
        assert preview["requires_approval"] is False
        assert preview["already_executed"] is False
