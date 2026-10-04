"""Tests for mock adapters."""

import pytest

from action_agent.adapters.mock.mock_experiment import MockExperimentAdapter
from action_agent.adapters.mock.mock_feature_flag import MockFeatureFlagAdapter
from action_agent.adapters.mock.mock_notification import MockNotificationAdapter
from action_agent.adapters.mock.mock_pricing import MockPricingAdapter


class TestMockFeatureFlagAdapter:

    @pytest.mark.asyncio
    async def test_enable_and_get(self):
        adapter = MockFeatureFlagAdapter()
        result = await adapter.enable_flag("flag_a", "seg_x", 30.0)
        assert result.success
        state = await adapter.get_flag_state("flag_a")
        assert state["enabled"] is True
        assert state["rollout_pct"] == 30.0

    @pytest.mark.asyncio
    async def test_disable(self):
        adapter = MockFeatureFlagAdapter()
        await adapter.enable_flag("flag_b", "seg_y", 50.0)
        result = await adapter.disable_flag("flag_b", "seg_y")
        assert result.success
        state = await adapter.get_flag_state("flag_b")
        assert state["enabled"] is False

    @pytest.mark.asyncio
    async def test_previous_state_captured(self):
        adapter = MockFeatureFlagAdapter()
        await adapter.enable_flag("flag_c", "seg_z", 20.0)
        result = await adapter.enable_flag("flag_c", "seg_z", 40.0)
        assert result.previous_state["rollout_pct"] == 20.0


class TestMockPricingAdapter:

    @pytest.mark.asyncio
    async def test_apply_and_revert(self):
        adapter = MockPricingAdapter()
        r1 = await adapter.apply_discount("seg_a", 15.0, 30)
        assert r1.success
        assert r1.details["discount_pct"] == 15.0

        r2 = await adapter.revert_discount("seg_a")
        assert r2.success
        state = await adapter.get_pricing_state("seg_a")
        assert state["active"] is False


class TestMockNotificationAdapter:

    @pytest.mark.asyncio
    async def test_send(self):
        adapter = MockNotificationAdapter()
        result = await adapter.send_notification("slack", "Test", "Hello", "INFO")
        assert result.success
        assert len(adapter.sent_notifications) == 1
        assert adapter.sent_notifications[0]["title"] == "Test"
