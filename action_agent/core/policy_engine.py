"""Policy / risk engine.

Evaluates an ActionPlan against configurable business rules to
decide whether execution should proceed, require approval, or
be rejected.  All thresholds come from ``config.settings``.
"""

from __future__ import annotations

from action_agent.config import Settings, settings
from action_agent.schemas.action import ActionPlan, ActionType, ExecutionMode
from action_agent.schemas.policy import PolicyDecision, PolicyEvaluation, RiskLevel
from action_agent.schemas.recommendation import StrategyRecommendation


# ---------------------------------------------------------------------------
# Risk classification heuristics
# ---------------------------------------------------------------------------

# Actions that are inherently low-risk
_LOW_RISK_TYPES = {ActionType.ALERT}

# Actions that are inherently high-risk
_HIGH_RISK_TYPES = {ActionType.PRICING_CHANGE}


class PolicyEngine:
    """Deterministic policy evaluation — no LLM, pure rules."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self._cfg = cfg or settings

    def evaluate(
        self,
        plan: ActionPlan,
        rec: StrategyRecommendation,
    ) -> PolicyEvaluation:
        """Run all policy checks and return a combined evaluation."""
        checks: dict[str, bool] = {}
        violations: list[str] = []
        reasons: list[str] = []

        # 1. Determine risk level
        risk = self._assess_risk(plan, rec)
        reasons.append(f"Risk assessed as {risk.value}")

        # 2. Confidence check
        min_conf = self._min_confidence_for(risk)
        conf_ok = rec.confidence >= min_conf
        checks["confidence_threshold"] = conf_ok
        if not conf_ok:
            violations.append(
                f"Confidence {rec.confidence:.2f} is below {risk.value} threshold {min_conf:.2f}"
            )

        # 3. Rollout check
        rollout = plan.parameters.get("rollout_percentage", 0.0)
        max_rollout = self._max_rollout_for(risk)
        rollout_ok = rollout <= max_rollout
        checks["rollout_within_limit"] = rollout_ok
        if not rollout_ok:
            violations.append(
                f"Rollout {rollout}% exceeds {risk.value} limit of {max_rollout}%"
            )

        # 4. Strategy-level constraint: rollout cap
        strat_cap = rec.constraints.max_rollout_percentage
        strat_ok = rollout <= strat_cap
        checks["strategy_rollout_cap"] = strat_ok
        if not strat_ok:
            violations.append(
                f"Rollout {rollout}% exceeds Strategy Agent cap of {strat_cap}%"
            )

        # 5. Required parameters present
        params_ok = self._check_required_params(plan)
        checks["required_params_present"] = params_ok
        if not params_ok:
            violations.append("Missing required parameters for this action type")

        # 6. Determine approval requirement
        requires_approval = rec.constraints.requires_approval or self._requires_approval(
            risk, plan.execution_mode
        )
        checks["approval_not_required"] = not requires_approval

        # 7. Decision
        if violations:
            decision = PolicyDecision.REJECTED
            reasons.append(f"{len(violations)} policy violation(s) detected")
        elif requires_approval:
            decision = PolicyDecision.APPROVAL_REQUIRED
            reasons.append(f"{risk.value} risk action requires human approval")
        else:
            decision = PolicyDecision.APPROVED
            reasons.append(
                f"Confidence {rec.confidence:.2f} and rollout {rollout}% within {risk.value} policy"
            )

        return PolicyEvaluation(
            decision=decision,
            risk_level=risk,
            requires_approval=requires_approval,
            reasons=reasons,
            violations=violations,
            checks_passed=checks,
            metadata={
                "confidence": rec.confidence,
                "min_confidence": min_conf,
                "rollout_pct": rollout,
                "max_rollout": max_rollout,
                "execution_mode": plan.execution_mode.value,
            },
        )

    # -- Risk classification -------------------------------------------------

    def _assess_risk(self, plan: ActionPlan, rec: StrategyRecommendation) -> RiskLevel:
        """Classify an action's risk level based on type and parameters."""
        # Alerts are always low risk
        if plan.action_type in _LOW_RISK_TYPES:
            return RiskLevel.LOW

        # Pricing changes are inherently high risk
        if plan.action_type in _HIGH_RISK_TYPES:
            return RiskLevel.HIGH

        # Heuristic: rollout percentage
        rollout = plan.parameters.get("rollout_percentage", 0.0)
        if rollout > 50:
            return RiskLevel.HIGH
        if rollout > 20:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # -- Threshold lookups ---------------------------------------------------

    def _min_confidence_for(self, risk: RiskLevel) -> float:
        return {
            RiskLevel.LOW: self._cfg.min_confidence_low_risk,
            RiskLevel.MEDIUM: self._cfg.min_confidence_medium_risk,
            RiskLevel.HIGH: self._cfg.min_confidence_high_risk,
        }[risk]

    def _max_rollout_for(self, risk: RiskLevel) -> float:
        return {
            RiskLevel.LOW: self._cfg.max_rollout_low_risk,
            RiskLevel.MEDIUM: self._cfg.max_rollout_medium_risk,
            RiskLevel.HIGH: self._cfg.max_rollout_high_risk,
        }[risk]

    def _requires_approval(self, risk: RiskLevel, mode: ExecutionMode) -> bool:
        """In DRY_RUN mode, auto-approve everything; in LIVE, respect config."""
        if mode == ExecutionMode.DRY_RUN:
            return False
        return {
            RiskLevel.LOW: not self._cfg.auto_approve_low_risk,
            RiskLevel.MEDIUM: not self._cfg.auto_approve_medium_risk,
            RiskLevel.HIGH: not self._cfg.auto_approve_high_risk,
        }[risk]

    # -- Parameter validation ------------------------------------------------

    @staticmethod
    def _check_required_params(plan: ActionPlan) -> bool:
        """Verify action-type-specific required parameters."""
        required_map: dict[ActionType, set[str]] = {
            ActionType.EXPERIMENT: {"rollout_percentage"},
            ActionType.UX_UPDATE: {"rollout_percentage"},
            ActionType.PRICING_CHANGE: {"discount_percentage"},
            ActionType.RETENTION_INTERVENTION: {"rollout_percentage"},
        }
        required = required_map.get(plan.action_type, set())
        return required.issubset(plan.parameters.keys())
