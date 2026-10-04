"""Tests for API endpoints.

Uses a conftest-style setup that manually configures the routes
module with a test executor, since ASGITransport doesn't trigger
the FastAPI lifespan events.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from action_agent.main import app
from action_agent.api import routes
from action_agent.adapters.mock.mock_experiment import MockExperimentAdapter
from action_agent.adapters.mock.mock_feature_flag import MockFeatureFlagAdapter
from action_agent.adapters.mock.mock_notification import MockNotificationAdapter
from action_agent.adapters.mock.mock_pricing import MockPricingAdapter
from action_agent.core.executor import ActionExecutor
from action_agent.core.idempotency import IdempotencyGuard
from action_agent.core.parser import RecommendationParser
from action_agent.core.planner import ActionPlanner
from action_agent.core.policy_engine import PolicyEngine
from action_agent.core.rollback_manager import RollbackManager
from action_agent.core.verification import VerificationEngine
from action_agent.persistence.action_repository import ActionRepository
from action_agent.persistence.audit_repository import AuditRepository
from action_agent.persistence.database import Database
from action_agent.registry.alert_handler import AlertActionHandler
from action_agent.registry.experiment_handler import ExperimentActionHandler
from action_agent.registry.pricing_handler import PricingActionHandler
from action_agent.registry.registry import ActionRegistry
from action_agent.registry.retention_handler import RetentionActionHandler
from action_agent.registry.ux_handler import UXActionHandler
from action_agent.schemas.action import ActionType


@pytest_asyncio.fixture(autouse=True)
async def _configure_api():
    """Wire up the Action Agent for API testing (replaces lifespan)."""
    db = Database(":memory:")
    await db.connect()

    audit_repo = AuditRepository(db)
    action_repo = ActionRepository(db)

    registry = ActionRegistry()
    registry.register(ActionType.EXPERIMENT, ExperimentActionHandler(MockExperimentAdapter()))
    registry.register(ActionType.PRICING_CHANGE, PricingActionHandler(MockPricingAdapter()))
    registry.register(ActionType.UX_UPDATE, UXActionHandler(MockFeatureFlagAdapter()))
    registry.register(ActionType.ALERT, AlertActionHandler(MockNotificationAdapter()))
    registry.register(ActionType.RETENTION_INTERVENTION, RetentionActionHandler(MockExperimentAdapter()))

    executor = ActionExecutor(
        parser=RecommendationParser(),
        planner=ActionPlanner(),
        policy_engine=PolicyEngine(),
        registry=registry,
        verification=VerificationEngine(),
        idempotency=IdempotencyGuard(action_repo),
        rollback_mgr=RollbackManager(action_repo, audit_repo),
        action_repo=action_repo,
        audit_repo=audit_repo,
    )
    routes.configure(executor, audit_repo)
    yield
    await db.disconnect()


class TestAPI:

    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["agent"] == "action_agent"

    @pytest.mark.asyncio
    async def test_execute_valid(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "recommendation_id": "rec_api_001",
                "confidence": 0.91,
                "customer_segment": "enterprise",
                "recommended_action": {
                    "type": "ux_experiment",
                    "target": "onboarding_v2",
                    "description": "Test new onboarding",
                    "parameters": {"rollout_percentage": 20}
                }
            }
            resp = await client.post("/actions/execute", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["execution_status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_execute_invalid(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/actions/execute", json={"bad": True})
            assert resp.status_code == 200
            data = resp.json()
            assert data["execution_status"] == "VALIDATION_FAILED"

    @pytest.mark.asyncio
    async def test_preview(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "recommendation_id": "rec_api_preview",
                "confidence": 0.85,
                "recommended_action": {
                    "type": "alert",
                    "target": "churn",
                    "description": "Alert test",
                    "parameters": {"channel": "ops", "severity": "HIGH"}
                }
            }
            resp = await client.post("/actions/preview", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["decision"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/actions/nonexistent_id")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_history(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/actions/")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_rollback_nonexistent(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/actions/fake_id/rollback")
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_and_get(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "recommendation_id": "rec_api_get_test",
                "confidence": 0.9,
                "recommended_action": {
                    "type": "alert",
                    "target": "test_alert",
                    "description": "test",
                    "parameters": {"channel": "test", "severity": "LOW"}
                }
            }
            exec_resp = await client.post("/actions/execute", json=payload)
            action_id = exec_resp.json()["action_id"]

            get_resp = await client.get(f"/actions/{action_id}")
            assert get_resp.status_code == 200
