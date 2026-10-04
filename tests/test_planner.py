"""Tests for action planner."""

import pytest

from action_agent.core.planner import ActionPlanner, ClassificationError
from action_agent.schemas.action import ActionType
from action_agent.core.parser import RecommendationParser


class TestActionPlanner:
    """Tests for ActionPlanner."""

    def test_classify_known_types(self):
        planner = ActionPlanner()
        assert planner.classify("ux_experiment") == ActionType.UX_UPDATE
        assert planner.classify("experiment") == ActionType.EXPERIMENT
        assert planner.classify("pricing_change") == ActionType.PRICING_CHANGE
        assert planner.classify("alert") == ActionType.ALERT
        assert planner.classify("retention_intervention") == ActionType.RETENTION_INTERVENTION

    def test_classify_case_insensitive(self):
        planner = ActionPlanner()
        assert planner.classify("UX_EXPERIMENT") == ActionType.UX_UPDATE
        assert planner.classify("Alert") == ActionType.ALERT

    def test_classify_unsupported_type(self):
        planner = ActionPlanner()
        with pytest.raises(ClassificationError, match="Unsupported"):
            planner.classify("telepathy")

    def test_create_plan(self, valid_ux_payload):
        parser = RecommendationParser()
        planner = ActionPlanner()
        rec = parser.parse(valid_ux_payload)
        plan = planner.create_plan(rec)

        assert plan.action_id.startswith("act_")
        assert plan.recommendation_id == "rec_test_001"
        assert plan.action_type == ActionType.UX_UPDATE
        assert plan.target == "new_onboarding_flow"
        assert plan.idempotency_key  # non-empty

    def test_idempotency_key_deterministic(self, valid_ux_payload):
        parser = RecommendationParser()
        planner = ActionPlanner()
        rec = parser.parse(valid_ux_payload)

        plan1 = planner.create_plan(rec)
        plan2 = planner.create_plan(rec)
        assert plan1.idempotency_key == plan2.idempotency_key
        assert plan1.action_id != plan2.action_id  # IDs are unique
