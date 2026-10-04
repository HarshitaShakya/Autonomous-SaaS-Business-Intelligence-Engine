"""Action executor — central pipeline orchestrator.

This is the main entry point for the Action Agent's logic.
It coordinates: parse → plan → idempotency → policy → execute →
verify → audit → rollback-data.

Each stage is a separate, testable component; the executor just
wires them together in order.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from action_agent.adapters.base import AdapterResult
from action_agent.core.idempotency import IdempotencyGuard
from action_agent.core.parser import ParseError, RecommendationParser
from action_agent.core.planner import ActionPlanner, ClassificationError
from action_agent.core.policy_engine import PolicyEngine
from action_agent.core.rollback_manager import RollbackError, RollbackManager
from action_agent.core.verification import VerificationEngine
from action_agent.persistence.action_repository import ActionRepository
from action_agent.persistence.audit_repository import AuditRepository
from action_agent.registry.registry import ActionRegistry
from action_agent.schemas.action import (
    ActionPlan,
    ExecutionResult,
    ExecutionStatus,
    VerificationStatus,
)
from action_agent.schemas.audit import AuditEntry
from action_agent.schemas.policy import PolicyDecision, PolicyEvaluation
from action_agent.schemas.recommendation import StrategyRecommendation

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Orchestrates the full action execution pipeline."""

    def __init__(
        self,
        parser: RecommendationParser,
        planner: ActionPlanner,
        policy_engine: PolicyEngine,
        registry: ActionRegistry,
        verification: VerificationEngine,
        idempotency: IdempotencyGuard,
        rollback_mgr: RollbackManager,
        action_repo: ActionRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._parser = parser
        self._planner = planner
        self._policy = policy_engine
        self._registry = registry
        self._verification = verification
        self._idempotency = idempotency
        self._rollback = rollback_mgr
        self._action_repo = action_repo
        self._audit_repo = audit_repo

    # -----------------------------------------------------------------------
    # Main pipeline
    # -----------------------------------------------------------------------

    async def execute(self, raw_payload: dict[str, Any]) -> ExecutionResult:
        """Full pipeline: parse → plan → idempotency → policy → execute → verify → audit."""
        plan: ActionPlan | None = None
        rec: StrategyRecommendation | None = None
        policy_eval: PolicyEvaluation | None = None

        try:
            # 1. Parse & validate
            rec = self._parser.parse(raw_payload)
            logger.info("Parsed recommendation %s", rec.recommendation_id)

            # 2. Plan
            plan = self._planner.create_plan(rec)
            logger.info(
                "Action planned: %s (type=%s, target=%s)",
                plan.action_id, plan.action_type.value, plan.target,
            )

            # 3. Idempotency check
            cached = await self._idempotency.check(plan.idempotency_key)
            if cached is not None:
                logger.info("Idempotency hit for %s — returning cached result", plan.idempotency_key)
                cached.execution_status = ExecutionStatus.ALREADY_EXECUTED
                return cached

            # 4. Persist plan (state = PENDING)
            await self._action_repo.save_plan(plan)

            # 5. Policy evaluation
            policy_eval = self._policy.evaluate(plan, rec)
            logger.info(
                "Policy: decision=%s risk=%s",
                policy_eval.decision.value, policy_eval.risk_level.value,
            )

            if policy_eval.decision == PolicyDecision.REJECTED:
                return await self._finalise(
                    plan, rec, policy_eval,
                    status=ExecutionStatus.POLICY_REJECTED,
                    verification=VerificationStatus.SKIPPED,
                    details={"violations": policy_eval.violations},
                )

            if policy_eval.decision == PolicyDecision.APPROVAL_REQUIRED:
                return await self._finalise(
                    plan, rec, policy_eval,
                    status=ExecutionStatus.APPROVAL_REQUIRED,
                    verification=VerificationStatus.SKIPPED,
                    details={"reason": "Human approval required before execution"},
                )

            # 6. Execute via registry handler
            handler = self._registry.get_handler(plan.action_type)
            await self._action_repo.update_status(plan.action_id, ExecutionStatus.EXECUTING.value)

            adapter_result: AdapterResult = await handler.execute(plan)
            logger.info("Adapter result: success=%s", adapter_result.success)

            if not adapter_result.success:
                return await self._finalise(
                    plan, rec, policy_eval,
                    status=ExecutionStatus.FAILED,
                    verification=VerificationStatus.FAILED,
                    error=adapter_result.error or "Adapter execution failed",
                    details=adapter_result.details,
                )

            # 7. Store rollback data
            if adapter_result.previous_state and self._rollback.is_reversible(plan.action_type):
                await self._action_repo.save_rollback_data(
                    plan.action_id,
                    {
                        "previous_state": adapter_result.previous_state,
                        "adapter_name": adapter_result.adapter_name,
                        "action_performed": adapter_result.action_performed,
                    },
                )

            # 8. Verify
            vr = self._verification.verify(plan, adapter_result)
            logger.info("Verification: %s", vr.status.value)

            return await self._finalise(
                plan, rec, policy_eval,
                status=ExecutionStatus.SUCCESS if vr.passed else ExecutionStatus.FAILED,
                verification=vr.status,
                details={
                    "adapter": adapter_result.details,
                    "verification_checks": vr.checks,
                    **vr.details,
                },
                rollback_supported=self._rollback.is_reversible(plan.action_type),
            )

        except ParseError as exc:
            logger.warning("Parse error: %s", exc)
            return self._error_result(
                plan, rec, ExecutionStatus.VALIDATION_FAILED, str(exc),
                details={"validation_errors": exc.details},
            )
        except ClassificationError as exc:
            logger.warning("Classification error: %s", exc)
            return self._error_result(
                plan, rec, ExecutionStatus.VALIDATION_FAILED, str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected error in execution pipeline")
            return self._error_result(
                plan, rec, ExecutionStatus.FAILED, f"Internal error: {exc}",
            )

    # -----------------------------------------------------------------------
    # Preview (dry analysis without execution)
    # -----------------------------------------------------------------------

    async def preview(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Preview what would happen if this recommendation were executed."""
        try:
            rec = self._parser.parse(raw_payload)
            plan = self._planner.create_plan(rec)
            policy_eval = self._policy.evaluate(plan, rec)

            # Idempotency check
            cached = await self._idempotency.check(plan.idempotency_key)
            already_executed = cached is not None

            return {
                "recommendation_id": rec.recommendation_id,
                "action_type": plan.action_type.value,
                "target": plan.target,
                "target_segment": plan.target_segment,
                "parameters": plan.parameters,
                "execution_mode": plan.execution_mode.value,
                "decision": policy_eval.decision.value,
                "risk_level": policy_eval.risk_level.value,
                "requires_approval": policy_eval.requires_approval,
                "reasons": policy_eval.reasons,
                "violations": policy_eval.violations,
                "checks": policy_eval.checks_passed,
                "rollback_supported": self._rollback.is_reversible(plan.action_type),
                "already_executed": already_executed,
                "expected_impact": rec.expected_impact.model_dump() if rec.expected_impact else None,
            }

        except (ParseError, ClassificationError) as exc:
            return {"error": str(exc), "decision": "REJECTED"}

    # -----------------------------------------------------------------------
    # Rollback
    # -----------------------------------------------------------------------

    async def rollback_action(self, action_id: str) -> dict[str, Any]:
        """Attempt to roll back a previously executed action."""
        record = await self._action_repo.get_by_action_id(action_id)
        if record is None:
            raise RollbackError(f"Action '{action_id}' not found")

        handler = self._registry.get_handler(record["action_type"])

        async def _do_rollback(rollback_data: dict[str, Any]) -> AdapterResult:
            return await handler.rollback(rollback_data)

        result = await self._rollback.rollback(action_id, _do_rollback)
        return {
            "action_id": action_id,
            "rollback_status": "COMPLETED" if result.success else "FAILED",
            "details": result.details,
            "error": result.error,
        }

    # -----------------------------------------------------------------------
    # Approve pending action
    # -----------------------------------------------------------------------

    async def approve(self, action_id: str) -> ExecutionResult:
        """Approve and execute a pending HIGH-risk action."""
        record = await self._action_repo.get_by_action_id(action_id)
        if record is None:
            raise RollbackError(f"Action '{action_id}' not found")
        if record["status"] != ExecutionStatus.APPROVAL_REQUIRED.value:
            raise RollbackError(
                f"Action '{action_id}' is in state '{record['status']}', not APPROVAL_REQUIRED"
            )

        # Re-parse the stored plan and re-execute through the handler
        plan = ActionPlan.model_validate_json(record["plan_json"])
        handler = self._registry.get_handler(plan.action_type)

        await self._action_repo.update_status(action_id, ExecutionStatus.EXECUTING.value)
        adapter_result = await handler.execute(plan)

        if not adapter_result.success:
            await self._action_repo.update_status(action_id, ExecutionStatus.FAILED.value)
            return ExecutionResult(
                action_id=action_id,
                recommendation_id=plan.recommendation_id,
                action_type=plan.action_type,
                execution_status=ExecutionStatus.FAILED,
                execution_mode=plan.execution_mode,
                error=adapter_result.error,
            )

        # Store rollback data
        if adapter_result.previous_state and self._rollback.is_reversible(plan.action_type):
            await self._action_repo.save_rollback_data(
                action_id,
                {
                    "previous_state": adapter_result.previous_state,
                    "adapter_name": adapter_result.adapter_name,
                },
            )

        vr = self._verification.verify(plan, adapter_result)
        status = ExecutionStatus.SUCCESS if vr.passed else ExecutionStatus.FAILED

        result = ExecutionResult(
            action_id=action_id,
            recommendation_id=plan.recommendation_id,
            action_type=plan.action_type,
            execution_status=status,
            verification_status=vr.status,
            execution_mode=plan.execution_mode,
            rollback_supported=self._rollback.is_reversible(plan.action_type),
            details={"adapter": adapter_result.details, "verification_checks": vr.checks},
        )
        await self._action_repo.save_result(action_id, result)
        return result

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _finalise(
        self,
        plan: ActionPlan,
        rec: StrategyRecommendation,
        policy_eval: PolicyEvaluation,
        *,
        status: ExecutionStatus,
        verification: VerificationStatus,
        details: dict[str, Any] | None = None,
        error: str | None = None,
        rollback_supported: bool = False,
    ) -> ExecutionResult:
        """Build the result, persist state, and write the audit log."""
        result = ExecutionResult(
            action_id=plan.action_id,
            recommendation_id=plan.recommendation_id,
            action_type=plan.action_type,
            execution_status=status,
            verification_status=verification,
            execution_mode=plan.execution_mode,
            risk_level=policy_eval.risk_level.value,
            policy_decision=policy_eval.decision.value,
            requires_approval=policy_eval.requires_approval,
            rollback_supported=rollback_supported,
            rollback_id=plan.action_id if rollback_supported else None,
            target=plan.target,
            target_segment=plan.target_segment,
            parameters=plan.parameters,
            details=details or {},
            error=error,
        )

        # Persist
        await self._action_repo.save_result(plan.action_id, result)

        # Audit
        await self._audit_repo.save(
            AuditEntry(
                action_id=plan.action_id,
                recommendation_id=plan.recommendation_id,
                timestamp=datetime.now(timezone.utc),
                action_type=plan.action_type.value,
                target=plan.target,
                target_segment=plan.target_segment,
                parameters=plan.parameters,
                risk_level=policy_eval.risk_level.value,
                confidence=rec.confidence,
                policy_decision=policy_eval.decision.value,
                approval_status="APPROVED" if status not in (
                    ExecutionStatus.APPROVAL_REQUIRED,
                    ExecutionStatus.POLICY_REJECTED,
                ) else policy_eval.decision.value,
                execution_mode=plan.execution_mode.value,
                execution_status=status.value,
                verification_status=verification.value,
                rollback_status="AVAILABLE" if rollback_supported else "NOT_APPLICABLE",
                error_info=error,
                result_details=details or {},
            )
        )

        return result

    @staticmethod
    def _error_result(
        plan: ActionPlan | None,
        rec: StrategyRecommendation | None,
        status: ExecutionStatus,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Build an error ExecutionResult when the pipeline fails early."""
        return ExecutionResult(
            action_id=plan.action_id if plan else "unknown",
            recommendation_id=(
                rec.recommendation_id if rec else
                (plan.recommendation_id if plan else "unknown")
            ),
            action_type=plan.action_type if plan else "UNKNOWN",
            execution_status=status,
            verification_status=VerificationStatus.SKIPPED,
            execution_mode=plan.execution_mode if plan else "DRY_RUN",
            error=error,
            details=details or {},
        )
