"""Tests for the verification engine."""

import pytest

from action_agent.adapters.base import AdapterResult
from action_agent.core.verification import VerificationEngine
from action_agent.schemas.action import ActionPlan, ActionType, VerificationStatus


class TestVerificationEngine:

    def test_verify_ux_success(self):
        engine = VerificationEngine()
        plan = ActionPlan(
            action_id="act_v1", recommendation_id="rec_v1",
            action_type=ActionType.UX_UPDATE, target="flag_x",
            target_segment="seg_a", parameters={"rollout_percentage": 20},
        )
        adapter_result = AdapterResult(
            success=True, adapter_name="MockFF",
            details={"enabled": True, "rollout_pct": 20, "segment": "seg_a"},
        )
        vr = engine.verify(plan, adapter_result)
        assert vr.status == VerificationStatus.PASSED
        assert vr.checks.get("flag_enabled") is True

    def test_verify_ux_wrong_rollout(self):
        engine = VerificationEngine()
        plan = ActionPlan(
            action_id="act_v2", recommendation_id="rec_v2",
            action_type=ActionType.UX_UPDATE, target="flag_y",
            target_segment="seg_b", parameters={"rollout_percentage": 20},
        )
        adapter_result = AdapterResult(
            success=True, adapter_name="MockFF",
            details={"enabled": True, "rollout_pct": 50, "segment": "seg_b"},
        )
        vr = engine.verify(plan, adapter_result)
        assert vr.status == VerificationStatus.FAILED

    def test_verify_adapter_failure(self):
        engine = VerificationEngine()
        plan = ActionPlan(
            action_id="act_v3", recommendation_id="rec_v3",
            action_type=ActionType.ALERT, target="x",
        )
        adapter_result = AdapterResult(success=False, error="Connection timeout")
        vr = engine.verify(plan, adapter_result)
        assert vr.status == VerificationStatus.FAILED

    def test_verify_alert_success(self):
        engine = VerificationEngine()
        plan = ActionPlan(
            action_id="act_v4", recommendation_id="rec_v4",
            action_type=ActionType.ALERT, target="alert_x",
        )
        adapter_result = AdapterResult(success=True, adapter_name="MockNotif", details={})
        vr = engine.verify(plan, adapter_result)
        assert vr.status == VerificationStatus.PASSED
