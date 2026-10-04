"""Tests for policy / risk engine."""

import pytest

from action_agent.config import Settings
from action_agent.core.parser import RecommendationParser
from action_agent.core.planner import ActionPlanner
from action_agent.core.policy_engine import PolicyEngine
from action_agent.schemas.action import ExecutionMode
from action_agent.schemas.policy import PolicyDecision, RiskLevel


class TestPolicyEngine:
    """Tests for PolicyEngine."""

    def _parse_and_plan(self, payload):
        parser = RecommendationParser()
        planner = ActionPlanner()
        rec = parser.parse(payload)
        plan = planner.create_plan(rec)
        return plan, rec

    def test_approve_low_risk_ux(self, valid_ux_payload):
        plan, rec = self._parse_and_plan(valid_ux_payload)
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        assert result.decision == PolicyDecision.APPROVED
        assert result.risk_level == RiskLevel.LOW
        assert not result.violations

    def test_approve_alert(self, valid_alert_payload):
        plan, rec = self._parse_and_plan(valid_alert_payload)
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        assert result.decision == PolicyDecision.APPROVED
        assert result.risk_level == RiskLevel.LOW

    def test_reject_low_confidence(self, valid_ux_payload):
        valid_ux_payload["confidence"] = 0.3  # below LOW threshold of 0.5
        plan, rec = self._parse_and_plan(valid_ux_payload)
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        assert result.decision == PolicyDecision.REJECTED
        assert any("confidence" in v.lower() for v in result.violations)

    def test_reject_rollout_exceeds_policy(self, valid_ux_payload):
        valid_ux_payload["recommended_action"]["parameters"]["rollout_percentage"] = 60
        plan, rec = self._parse_and_plan(valid_ux_payload)
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        # 60% rollout → MEDIUM risk → max rollout 50% → rejected
        assert result.decision == PolicyDecision.REJECTED

    def test_pricing_is_high_risk(self, valid_pricing_payload):
        plan, rec = self._parse_and_plan(valid_pricing_payload)
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        assert result.risk_level == RiskLevel.HIGH

    def test_high_risk_requires_approval_in_live_mode(self, valid_pricing_payload):
        plan, rec = self._parse_and_plan(valid_pricing_payload)
        plan.execution_mode = ExecutionMode.LIVE
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        assert result.requires_approval is True
        assert result.decision == PolicyDecision.APPROVAL_REQUIRED

    def test_high_risk_auto_approved_in_dry_run(self, valid_pricing_payload):
        plan, rec = self._parse_and_plan(valid_pricing_payload)
        plan.execution_mode = ExecutionMode.DRY_RUN
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        # DRY_RUN auto-approves everything
        assert result.requires_approval is False

    def test_missing_required_params_rejected(self):
        payload = {
            "recommendation_id": "rec_no_params",
            "confidence": 0.9,
            "recommended_action": {
                "type": "experiment",
                "target": "some_test",
                "description": "Missing rollout_percentage param",
                "parameters": {}  # missing rollout_percentage
            }
        }
        plan, rec = self._parse_and_plan(payload)
        engine = PolicyEngine()
        result = engine.evaluate(plan, rec)

        assert result.decision == PolicyDecision.REJECTED
        assert any("param" in v.lower() for v in result.violations)
