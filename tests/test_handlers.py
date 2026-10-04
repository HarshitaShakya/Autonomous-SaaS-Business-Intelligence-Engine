"""Tests for action handlers."""

import pytest

from action_agent.adapters.mock.mock_experiment import MockExperimentAdapter
from action_agent.adapters.mock.mock_feature_flag import MockFeatureFlagAdapter
from action_agent.adapters.mock.mock_notification import MockNotificationAdapter
from action_agent.adapters.mock.mock_pricing import MockPricingAdapter
from action_agent.registry.alert_handler import AlertActionHandler
from action_agent.registry.experiment_handler import ExperimentActionHandler
from action_agent.registry.pricing_handler import PricingActionHandler
from action_agent.registry.retention_handler import RetentionActionHandler
from action_agent.registry.ux_handler import UXActionHandler
from action_agent.schemas.action import ActionPlan, ActionType


class TestExperimentHandler:

    @pytest.mark.asyncio
    async def test_execute(self):
        adapter = MockExperimentAdapter()
        handler = ExperimentActionHandler(adapter)
        plan = ActionPlan(
            action_id="act_h1", recommendation_id="rec_h1",
            action_type=ActionType.EXPERIMENT, target="test_exp",
            target_segment="seg_a", parameters={"rollout_percentage": 15},
        )
        result = await handler.execute(plan)
        assert result.success is True
        assert result.details["active"] is True


class TestPricingHandler:

    @pytest.mark.asyncio
    async def test_execute(self):
        adapter = MockPricingAdapter()
        handler = PricingActionHandler(adapter)
        plan = ActionPlan(
            action_id="act_h2", recommendation_id="rec_h2",
            action_type=ActionType.PRICING_CHANGE, target="pricing_test",
            target_segment="seg_b", parameters={"discount_percentage": 10, "duration_days": 14},
        )
        result = await handler.execute(plan)
        assert result.success is True
        assert result.details["discount_pct"] == 10


class TestUXHandler:

    @pytest.mark.asyncio
    async def test_execute(self):
        adapter = MockFeatureFlagAdapter()
        handler = UXActionHandler(adapter)
        plan = ActionPlan(
            action_id="act_h3", recommendation_id="rec_h3",
            action_type=ActionType.UX_UPDATE, target="flag_onboarding",
            target_segment="seg_c", parameters={"rollout_percentage": 25},
        )
        result = await handler.execute(plan)
        assert result.success is True
        assert result.details["enabled"] is True


class TestAlertHandler:

    @pytest.mark.asyncio
    async def test_execute(self):
        adapter = MockNotificationAdapter()
        handler = AlertActionHandler(adapter)
        plan = ActionPlan(
            action_id="act_h4", recommendation_id="rec_h4",
            action_type=ActionType.ALERT, target="churn_alert",
            parameters={"channel": "ops", "severity": "HIGH", "title": "Test"},
        )
        result = await handler.execute(plan)
        assert result.success is True
        assert len(adapter.sent_notifications) == 1

    @pytest.mark.asyncio
    async def test_rollback_not_supported(self):
        adapter = MockNotificationAdapter()
        handler = AlertActionHandler(adapter)
        assert handler.rollback_supported is False
        result = await handler.rollback({})
        assert result.success is False


class TestRetentionHandler:

    @pytest.mark.asyncio
    async def test_execute(self):
        adapter = MockExperimentAdapter()
        handler = RetentionActionHandler(adapter)
        plan = ActionPlan(
            action_id="act_h5", recommendation_id="rec_h5",
            action_type=ActionType.RETENTION_INTERVENTION, target="outreach",
            target_segment="seg_d", parameters={"rollout_percentage": 10},
        )
        result = await handler.execute(plan)
        assert result.success is True
        assert "retention_outreach" in result.action_performed
