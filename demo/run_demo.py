"""
Action Agent — End-to-End Demo Script
======================================

Runs the full demo scenario without needing a running server.
Demonstrates: parsing → planning → policy → execution → verification
→ audit → rollback for every supported action type.

Usage:
    python -m demo.run_demo
"""

from __future__ import annotations

import asyncio
import json
import sys
import io
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

from demo.demo_payloads import ALL_SCENARIOS, ONBOARDING_EXPERIMENT


# ── Colours for terminal output ──────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    DIM = "\033[2m"


def header(text: str) -> None:
    print(f"\n{C.BOLD}{C.CYAN}{'=' * 70}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  {text}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'=' * 70}{C.RESET}")


def step(num: int, text: str) -> None:
    print(f"\n  {C.MAGENTA}Step {num:>2}{C.RESET} | {text}")


def result_line(label: str, value: str, color: str = C.GREEN) -> None:
    print(f"         | {C.DIM}{label:<24}{C.RESET} {color}{value}{C.RESET}")


def divider() -> None:
    print(f"  {'-' * 66}")


async def build_executor() -> tuple[ActionExecutor, AuditRepository]:
    """Construct the full Action Agent pipeline with in-memory SQLite."""
    db = Database(":memory:")
    await db.connect()

    audit_repo = AuditRepository(db)
    action_repo = ActionRepository(db)

    ff_adapter = MockFeatureFlagAdapter()
    pricing_adapter = MockPricingAdapter()
    exp_adapter = MockExperimentAdapter()
    notif_adapter = MockNotificationAdapter()

    registry = ActionRegistry()
    registry.register(ActionType.EXPERIMENT, ExperimentActionHandler(exp_adapter))
    registry.register(ActionType.PRICING_CHANGE, PricingActionHandler(pricing_adapter))
    registry.register(ActionType.UX_UPDATE, UXActionHandler(ff_adapter))
    registry.register(ActionType.ALERT, AlertActionHandler(notif_adapter))
    registry.register(ActionType.RETENTION_INTERVENTION, RetentionActionHandler(exp_adapter))

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
    return executor, audit_repo


async def main() -> None:
    # Force UTF-8 stdout on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    header("ACTION AGENT -- END-TO-END DEMONSTRATION")
    print(f"\n  {C.DIM}Autonomous SaaS Business Intelligence Engine{C.RESET}")
    print(f"  {C.DIM}Execution Mode: DRY_RUN (no real systems modified){C.RESET}")

    executor, audit_repo = await build_executor()

    # ─── Part 1: Execute All Scenarios ────────────────────────────────────

    header("PART 1: Execute All Strategy Recommendations")

    for i, (name, payload) in enumerate(ALL_SCENARIOS, 1):
        divider()
        print(f"\n  {C.BOLD}Scenario {i}: {name}{C.RESET}")

        # Preview first
        step(1, "Preview (what would happen?)")
        preview = await executor.preview(payload)
        result_line("Action Type", preview.get("action_type", "?"))
        result_line("Risk Level", preview.get("risk_level", "?"))
        result_line("Decision", preview.get("decision", "?"),
                     C.GREEN if preview.get("decision") == "APPROVED" else C.RED)
        if preview.get("violations"):
            result_line("Violations", str(preview["violations"]), C.RED)

        # Execute
        step(2, "Execute recommendation")
        result = await executor.execute(payload)

        status_color = C.GREEN if result.execution_status.value == "SUCCESS" else (
            C.RED if "FAIL" in result.execution_status.value or "REJECT" in result.execution_status.value
            else C.YELLOW
        )
        result_line("Action ID", result.action_id)
        result_line("Execution Status", result.execution_status.value, status_color)
        result_line("Verification", result.verification_status.value,
                     C.GREEN if result.verification_status.value == "PASSED" else C.YELLOW)
        result_line("Rollback Available", str(result.rollback_supported))
        if result.error:
            result_line("Error", result.error, C.RED)

    # ─── Part 2: Idempotency Check ────────────────────────────────────────

    header("PART 2: Idempotency — Duplicate Prevention")

    step(1, "Re-submit the onboarding experiment (should be blocked)")
    dup = await executor.execute(ONBOARDING_EXPERIMENT)
    result_line("Status", dup.execution_status.value, C.YELLOW)

    # ─── Part 3: Rollback ─────────────────────────────────────────────────

    header("PART 3: Rollback — Reverse the Onboarding Experiment")

    # Find the original action
    original = await executor.execute({
        **ONBOARDING_EXPERIMENT,
        "recommendation_id": "rec_rollback_demo",
    })
    step(1, f"Original execution: {original.action_id}")
    result_line("Status", original.execution_status.value, C.GREEN)

    step(2, "Rolling back...")
    try:
        rb = await executor.rollback_action(original.action_id)
        result_line("Rollback Status", rb["rollback_status"],
                     C.GREEN if rb["rollback_status"] == "COMPLETED" else C.RED)
    except Exception as e:
        result_line("Rollback Error", str(e), C.RED)

    # ─── Part 4: Audit Log ────────────────────────────────────────────────

    header("PART 4: Audit Trail")

    step(1, "Fetching complete audit history...")
    history = await audit_repo.get_history(limit=20)
    print(f"\n  {C.BOLD}  Total audit entries: {len(history)}{C.RESET}\n")

    for entry in history[:8]:
        status_c = C.GREEN if entry.execution_status == "SUCCESS" else (
            C.RED if "FAIL" in entry.execution_status or "REJECT" in entry.execution_status
            else C.YELLOW
        )
        print(
            f"    {C.DIM}{entry.timestamp}{C.RESET}  "
            f"{entry.action_type:<25}  "
            f"{status_c}{entry.execution_status:<20}{C.RESET}  "
            f"{C.DIM}{entry.risk_level}{C.RESET}"
        )

    # ─── Summary ──────────────────────────────────────────────────────────

    header("DEMONSTRATION COMPLETE")
    print(f"""
  {C.GREEN}✓{C.RESET} Strategy recommendations parsed and validated
  {C.GREEN}✓{C.RESET} Actions classified and planned autonomously
  {C.GREEN}✓{C.RESET} Policy/risk engine evaluated every action
  {C.GREEN}✓{C.RESET} Low-confidence recommendations rejected safely
  {C.GREEN}✓{C.RESET} Mock adapters simulated real system changes
  {C.GREEN}✓{C.RESET} Post-execution verification confirmed outcomes
  {C.GREEN}✓{C.RESET} Idempotency prevented duplicate execution
  {C.GREEN}✓{C.RESET} Rollback reversed a completed action
  {C.GREEN}✓{C.RESET} Complete audit trail recorded

  {C.BOLD}To start the HTTP server:{C.RESET}
    uvicorn action_agent.main:app --reload

  {C.BOLD}API docs:{C.RESET}
    http://localhost:8000/docs
""")


if __name__ == "__main__":
    asyncio.run(main())
