"""Shared test fixtures.

Provides pre-built components (database, repos, adapters, executor)
that every test module can use without repetitive setup.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

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


# ---------------------------------------------------------------------------
# Database (in-memory SQLite for speed)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.disconnect()


@pytest_asyncio.fixture
async def audit_repo(db):
    return AuditRepository(db)


@pytest_asyncio.fixture
async def action_repo(db):
    return ActionRepository(db)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

@pytest.fixture
def feature_flag_adapter():
    return MockFeatureFlagAdapter()


@pytest.fixture
def pricing_adapter():
    return MockPricingAdapter()


@pytest.fixture
def experiment_adapter():
    return MockExperimentAdapter()


@pytest.fixture
def notification_adapter():
    return MockNotificationAdapter()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@pytest.fixture
def registry(experiment_adapter, pricing_adapter, feature_flag_adapter, notification_adapter):
    reg = ActionRegistry()
    reg.register(ActionType.EXPERIMENT, ExperimentActionHandler(experiment_adapter))
    reg.register(ActionType.PRICING_CHANGE, PricingActionHandler(pricing_adapter))
    reg.register(ActionType.UX_UPDATE, UXActionHandler(feature_flag_adapter))
    reg.register(ActionType.ALERT, AlertActionHandler(notification_adapter))
    reg.register(ActionType.RETENTION_INTERVENTION, RetentionActionHandler(experiment_adapter))
    return reg


# ---------------------------------------------------------------------------
# Core components
# ---------------------------------------------------------------------------

@pytest.fixture
def parser():
    return RecommendationParser()


@pytest.fixture
def planner():
    return ActionPlanner()


@pytest.fixture
def policy_engine():
    return PolicyEngine()


@pytest.fixture
def verification_engine():
    return VerificationEngine()


@pytest_asyncio.fixture
async def idempotency_guard(action_repo):
    return IdempotencyGuard(action_repo)


@pytest_asyncio.fixture
async def rollback_manager(action_repo, audit_repo):
    return RollbackManager(action_repo, audit_repo)


# ---------------------------------------------------------------------------
# Full executor
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def executor(parser, planner, policy_engine, registry, verification_engine,
                   idempotency_guard, rollback_manager, action_repo, audit_repo):
    return ActionExecutor(
        parser=parser,
        planner=planner,
        policy_engine=policy_engine,
        registry=registry,
        verification=verification_engine,
        idempotency=idempotency_guard,
        rollback_mgr=rollback_manager,
        action_repo=action_repo,
        audit_repo=audit_repo,
    )


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_ux_payload():
    return {
        "recommendation_id": "rec_test_001",
        "customer_segment": "high_churn_enterprise",
        "priority": "HIGH",
        "confidence": 0.91,
        "reason": "Onboarding friction is the primary retention driver for this segment",
        "recommended_action": {
            "type": "ux_experiment",
            "target": "new_onboarding_flow",
            "description": "Enable redesigned onboarding for high-risk users",
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


@pytest.fixture
def valid_alert_payload():
    return {
        "recommendation_id": "rec_test_alert_001",
        "confidence": 0.85,
        "recommended_action": {
            "type": "alert",
            "target": "churn_spike",
            "description": "High churn detected in enterprise segment",
            "parameters": {
                "channel": "product_team",
                "severity": "HIGH",
                "title": "Churn Spike Alert",
                "message": "Enterprise segment churn increased 15% week-over-week"
            }
        }
    }


@pytest.fixture
def valid_pricing_payload():
    return {
        "recommendation_id": "rec_test_pricing_001",
        "customer_segment": "at_risk_smb",
        "confidence": 0.88,
        "recommended_action": {
            "type": "pricing_change",
            "target": "smb_discount",
            "description": "Offer 15% discount to at-risk SMB segment",
            "parameters": {
                "discount_percentage": 15.0,
                "duration_days": 30
            }
        },
        "expected_impact": {
            "metric": "retention_rate",
            "direction": "increase",
            "estimated_change": 0.05
        }
    }


@pytest.fixture
def valid_experiment_payload():
    return {
        "recommendation_id": "rec_test_exp_001",
        "customer_segment": "trial_users",
        "confidence": 0.78,
        "recommended_action": {
            "type": "experiment",
            "target": "email_cadence_test",
            "description": "Test reduced email cadence for trial users",
            "parameters": {
                "rollout_percentage": 15
            }
        },
        "expected_impact": {
            "metric": "trial_conversion",
            "direction": "increase",
            "estimated_change": 0.03
        }
    }


@pytest.fixture
def valid_retention_payload():
    return {
        "recommendation_id": "rec_test_ret_001",
        "customer_segment": "churning_mid_market",
        "confidence": 0.82,
        "recommended_action": {
            "type": "retention_intervention",
            "target": "personal_outreach",
            "description": "Trigger personalised outreach for churning mid-market accounts",
            "parameters": {
                "rollout_percentage": 10
            }
        },
        "expected_impact": {
            "metric": "retention_rate",
            "direction": "increase",
            "estimated_change": 0.06
        }
    }
