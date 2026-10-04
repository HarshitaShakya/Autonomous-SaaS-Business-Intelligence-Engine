"""FastAPI application entry point.

Wires all components together using dependency injection and
starts the Action Agent as an HTTP service.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from action_agent.adapters.mock.mock_experiment import MockExperimentAdapter
from action_agent.adapters.mock.mock_feature_flag import MockFeatureFlagAdapter
from action_agent.adapters.mock.mock_notification import MockNotificationAdapter
from action_agent.adapters.mock.mock_pricing import MockPricingAdapter
from action_agent.api import routes
from action_agent.config import settings
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
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("action_agent")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    # -- Startup ------------------------------------------------------------
    logger.info("Starting Action Agent (mode=%s)", settings.execution_mode.value)

    # Database
    db = Database(settings.database_path)
    await db.connect()
    logger.info("Database connected: %s", settings.database_path)

    # Repositories
    audit_repo = AuditRepository(db)
    action_repo = ActionRepository(db)

    # Adapters (mock by default — replace with live implementations later)
    feature_flag_adapter = MockFeatureFlagAdapter()
    pricing_adapter = MockPricingAdapter()
    experiment_adapter = MockExperimentAdapter()
    notification_adapter = MockNotificationAdapter()

    # Registry
    registry = ActionRegistry()
    registry.register(ActionType.EXPERIMENT, ExperimentActionHandler(experiment_adapter))
    registry.register(ActionType.PRICING_CHANGE, PricingActionHandler(pricing_adapter))
    registry.register(ActionType.UX_UPDATE, UXActionHandler(feature_flag_adapter))
    registry.register(ActionType.ALERT, AlertActionHandler(notification_adapter))
    registry.register(ActionType.RETENTION_INTERVENTION, RetentionActionHandler(experiment_adapter))

    # Core components
    parser = RecommendationParser()
    planner = ActionPlanner()
    policy_engine = PolicyEngine()
    verification = VerificationEngine()
    idempotency = IdempotencyGuard(action_repo)
    rollback_mgr = RollbackManager(action_repo, audit_repo)

    # Executor
    executor = ActionExecutor(
        parser=parser,
        planner=planner,
        policy_engine=policy_engine,
        registry=registry,
        verification=verification,
        idempotency=idempotency,
        rollback_mgr=rollback_mgr,
        action_repo=action_repo,
        audit_repo=audit_repo,
    )

    # Inject into routes
    routes.configure(executor, audit_repo)

    logger.info(
        "Action Agent ready — %d handler(s) registered: %s",
        len(registry.registered_types),
        [t.value for t in registry.registered_types],
    )

    yield  # ── Application is running ──

    # -- Shutdown -----------------------------------------------------------
    await db.disconnect()
    logger.info("Action Agent shut down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Action Agent — Autonomous SaaS BI Engine",
    description=(
        "The execution layer of the Autonomous SaaS Business Intelligence Engine. "
        "Receives strategy recommendations and converts them into controlled, "
        "verified, and auditable business actions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (permissive for development — tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(routes.router)


@app.get("/health", tags=["system"])
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "action_agent",
        "execution_mode": settings.execution_mode.value,
        "version": "1.0.0",
    }
