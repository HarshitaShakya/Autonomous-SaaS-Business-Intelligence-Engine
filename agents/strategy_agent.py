"""Agent 4 — Strategy Agent (Reasoning Layer).

Consumes the typed Pydantic outputs of the three upstream ML agents
(User Behavior, Churn Prediction, Feature Analysis) and produces a
ranked list of business recommendations that the Action Agent can execute.

Pipeline position
-----------------
::

    [User Behavior, Churn Prediction, Feature Analysis]
        → **Strategy Agent**
            → Action Agent (human-approved execution)

This is the only agent in the pipeline that calls an LLM.  The three upstream
agents are classical ML / statistical models; this agent takes their structured
output and reasons over it to produce actionable recommendations.

Grounding strategy
------------------
The internal prompt to the LLM passes *real* numbers (hazard scores, cluster
sizes, causal ATE estimates and CIs) and explicitly instructs the model:

1. **Do not invent numbers** — only reference values present in the prompt.
2. **Respect the CI** — if the confidence interval is wide, say so; reflect
   uncertainty in a ``confidence_score`` field rather than presenting every
   recommendation as equally certain.
3. **Reason at the segment level** — aggregate churn risk across each cluster,
   then ask which causally-validated features would move the needle.

The output is parsed via LangChain ``with_structured_output`` into Pydantic
models, so we get typed objects — not free text that needs regex.

Design notes
------------
* Uses LangChain's LLM abstraction (``init_chat_model``) — not hardcoded to
  one provider.  Set ``STRATEGY_LLM_MODEL`` env var to switch.
* Falls back to a deterministic heuristic engine when no LLM is configured,
  so the pipeline can run end-to-end without an API key.
* Exposed as a ``RunnableLambda`` with the same calling convention as the
  other three agents, composing into the LangGraph pipeline.
* Carries ``customer_ids`` through to each recommendation so the Action Agent
  knows who to act on.
"""

from __future__ import annotations

import os
import time
import uuid
from collections import Counter
from typing import Any

from loguru import logger
from langchain_core.runnables import RunnableLambda

from schemas.agent_outputs import (
    BehaviorAnalysisResult,
    ChurnPredictionResult,
    FeatureAnalysisResult,
    CausalFeatureEffect,
)
from schemas.strategy_outputs import (
    ActionTypeEnum,
    CausalEvidence,
    SegmentRecommendation,
    SegmentRiskEvidence,
    StrategyAgentInput,
    StrategyAgentResult,
)


# ── Configuration ────────────────────────────────────────────────────

# LLM model identifier — provider-agnostic via langchain's init_chat_model.
# Examples: "openai:gpt-4o", "anthropic:claude-3-5-sonnet-20241022",
#           "google-genai:gemini-1.5-pro"
_DEFAULT_MODEL = "openai:gpt-4o"
STRATEGY_LLM_MODEL: str = os.getenv("STRATEGY_LLM_MODEL", _DEFAULT_MODEL)
STRATEGY_LLM_TEMPERATURE: float = float(
    os.getenv("STRATEGY_LLM_TEMPERATURE", "0.0")
)


# ── Segment-level aggregation (deterministic — runs BEFORE the LLM) ──

def _aggregate_segments(
    behavior: BehaviorAnalysisResult,
    churn: ChurnPredictionResult,
) -> list[SegmentRiskEvidence]:
    """Aggregate churn risk from per-customer predictions into per-cluster
    summaries.

    This is *not* done by the LLM — it's a deterministic pre-processing
    step that produces the exact numbers the LLM will see.
    """
    # Build lookup: customer_id → churn prediction
    churn_lookup = {p.customer_id: p for p in churn.predictions}

    # Group customer IDs by cluster
    cluster_customers: dict[int, list[str]] = {}
    for cc in behavior.customer_clusters:
        cluster_customers.setdefault(cc.cluster_id, []).append(cc.customer_id)

    # Profile lookup
    profile_lookup = {p.cluster_id: p for p in behavior.cluster_profiles}

    segments: list[SegmentRiskEvidence] = []
    for cid, cust_ids in sorted(cluster_customers.items()):
        if cid == -1:
            # Skip noise cluster for strategy — too heterogeneous
            continue

        profile = profile_lookup.get(cid)
        if profile is None:
            continue

        # Aggregate churn metrics
        risk_scores: list[float] = []
        hazard_rates: list[float] = []
        survival_probs: list[float] = []
        reasons: list[str] = []

        for cust_id in cust_ids:
            pred = churn_lookup.get(cust_id)
            if pred is None:
                continue
            risk_scores.append(pred.risk_score)
            hazard_rates.append(pred.hazard_rate)
            survival_probs.append(pred.survival_probability_6m)
            reasons.append(pred.churn_reason)

        if not risk_scores:
            continue

        reason_counts = dict(Counter(reasons))
        dominant_reason = max(reason_counts, key=reason_counts.get)  # type: ignore[arg-type]

        segments.append(
            SegmentRiskEvidence(
                segment_id=cid,
                segment_label=profile.label,
                segment_size=profile.size,
                mean_risk_score=round(sum(risk_scores) / len(risk_scores), 4),
                mean_hazard_rate=round(
                    sum(hazard_rates) / len(hazard_rates), 4
                ),
                mean_survival_probability_6m=round(
                    sum(survival_probs) / len(survival_probs), 4
                ),
                dominant_churn_reason=dominant_reason,
                churn_reason_distribution=reason_counts,
                customer_ids=cust_ids,
                is_anomalous=profile.is_anomalous,
            )
        )

    return segments


def _rank_features(
    features: FeatureAnalysisResult,
) -> list[CausalEvidence]:
    """Convert Feature Analysis effects to CausalEvidence, sorted by |ATE|."""
    evidence: list[CausalEvidence] = []
    for eff in features.effects:
        if not eff.is_significant:
            continue
        evidence.append(
            CausalEvidence(
                feature_name=eff.feature_name,
                treatment_description=eff.treatment_description,
                ate=eff.ate,
                ci_lower=eff.ci_lower,
                ci_upper=eff.ci_upper,
                is_significant=eff.is_significant,
                ci_width=round(eff.ci_upper - eff.ci_lower, 6),
            )
        )
    evidence.sort(key=lambda e: abs(e.ate), reverse=True)
    return evidence


def _compute_confidence(ci_width: float) -> float:
    """Map CI width to a 0-1 confidence score.

    Narrower intervals → higher confidence.  The mapping is:
        confidence = max(0.1, 1.0 − ci_width)
    clamped to [0.1, 1.0].
    """
    return round(max(0.1, min(1.0, 1.0 - ci_width)), 4)


def _determine_urgency(
    mean_risk: float, is_anomalous: bool
) -> str:
    """Classify urgency from risk score and anomaly flag."""
    if is_anomalous and mean_risk >= 0.6:
        return "critical"
    elif mean_risk >= 0.6 or is_anomalous:
        return "high"
    elif mean_risk >= 0.4:
        return "medium"
    else:
        return "low"


def _select_action_type(
    urgency: str, dominant_reason: str, causal: CausalEvidence
) -> ActionTypeEnum:
    """Heuristic action-type selection for fallback mode.

    Policy
    ------
    - **critical / high + payment reason** → ``apply_stripe_discount``
      (financial intervention, high-risk, will require HITL approval)
    - **any urgency + dissatisfaction** → ``trigger_a_b_test``
      (product experiment for the feature the causal model identified)
    - **fallback** → ``send_cs_alert``
      (operational notification to the customer success team)
    """
    if urgency in ("critical", "high") and dominant_reason == "payment":
        return ActionTypeEnum.STRIPE_DISCOUNT
    elif dominant_reason == "dissatisfaction":
        return ActionTypeEnum.A_B_TEST
    elif urgency in ("critical", "high"):
        return ActionTypeEnum.A_B_TEST
    else:
        return ActionTypeEnum.CS_ALERT


def _build_action_parameters(
    action_type: ActionTypeEnum,
    segment: SegmentRiskEvidence,
    causal: CausalEvidence,
) -> dict[str, Any]:
    """Build tool-specific parameters matching Action Agent schemas."""
    segment_tag = f"cluster_{segment.segment_id}"

    if action_type == ActionTypeEnum.A_B_TEST:
        experiment = (
            f"{causal.feature_name.lower().replace(' ', '_')}_"
            f"intervention_{segment_tag}"
        )
        return {
            "segment_id": segment_tag,
            "experiment_name": experiment,
        }
    elif action_type == ActionTypeEnum.STRIPE_DISCOUNT:
        # For bulk segment actions, target the highest-risk customer
        return {
            "customer_id": segment.customer_ids[0] if segment.customer_ids else "unknown",
            "coupon_code": "RETENTION_25",
        }
    else:  # CS_ALERT
        msg = (
            f"[AUTO] Segment '{segment.segment_label}' "
            f"(cluster {segment.segment_id}, {segment.segment_size} customers) "
            f"has mean churn risk {segment.mean_risk_score:.0%}.  "
            f"Primary driver: {causal.treatment_description} "
            f"(ATE={causal.ate:+.4f}).  "
            f"Recommended outreach for {len(segment.customer_ids)} customers."
        )
        return {
            "channel": "#churn-alerts",
            "message": msg,
        }


# ── LLM-powered reasoning ───────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Strategy Agent in an Autonomous SaaS Business Intelligence Engine.

Your job is to take the structured output of three upstream ML agents and
produce actionable business recommendations for each flagged customer segment.

## GROUNDING RULES — MANDATORY
1. **Do NOT invent numbers.** Every number you cite (risk score, ATE, CI bounds,
   cluster size, hazard rate) MUST come from the data provided below.  If you
   cannot find a number in the data, do not state it.
2. **Respect confidence intervals.** If the CI is wide (ci_width > 0.3), say
   "there is suggestive but imprecise evidence" — do NOT assert a strong causal
   claim.  Reflect uncertainty in the confidence_score field.
3. **Reason at the segment level.** Each recommendation targets a cluster, not
   an individual.

## AVAILABLE ACTIONS (Action Agent tools)
You may ONLY recommend one of these three action_type values:
- "trigger_a_b_test" — launch a GrowthBook feature experiment.
  Parameters: { "segment_id": str, "experiment_name": str }
- "apply_stripe_discount" — apply a Stripe retention coupon.
  Parameters: { "customer_id": str, "coupon_code": str }
  ⚠️ This is HIGH RISK — only recommend for payment-driven churn with strong evidence.
- "send_cs_alert" — dispatch a Slack / CRM alert.
  Parameters: { "channel": str, "message": str }

## JUSTIFICATION FORMAT
Each justification MUST:
- Name the segment (cluster label and ID).
- State the churn risk evidence (mean risk score, 6-month survival probability).
- State the causal evidence (feature name, ATE, CI) and acknowledge uncertainty
  if the CI is wide.
- Explain WHY this action type was chosen for this segment.

## OUTPUT
Produce one recommendation per flagged segment, ranked by estimated_impact
(= ATE × segment_size) descending.
"""


def _build_user_prompt(
    segments: list[SegmentRiskEvidence],
    causal_evidence: list[CausalEvidence],
    features_meta: dict[str, Any],
) -> str:
    """Build the data-grounded user prompt for the LLM."""
    lines: list[str] = []

    lines.append("## FLAGGED SEGMENTS\n")
    for seg in segments:
        lines.append(
            f"### Cluster {seg.segment_id}: {seg.segment_label}\n"
            f"- Size: {seg.segment_size} customers\n"
            f"- Mean churn risk score: {seg.mean_risk_score:.4f}\n"
            f"- Mean 6-month survival probability: {seg.mean_survival_probability_6m:.4f}\n"
            f"- Mean hazard rate: {seg.mean_hazard_rate:.4f}\n"
            f"- Dominant churn reason: {seg.dominant_churn_reason}\n"
            f"- Churn reason distribution: {seg.churn_reason_distribution}\n"
            f"- Anomalous: {seg.is_anomalous}\n"
            f"- Number of affected customers: {len(seg.customer_ids)}\n"
        )

    lines.append("\n## CAUSALLY SIGNIFICANT FEATURES (ranked by |ATE|)\n")
    for ev in causal_evidence:
        lines.append(
            f"- **{ev.feature_name}**: {ev.treatment_description}\n"
            f"  ATE = {ev.ate:+.4f}, 95% CI = [{ev.ci_lower:.4f}, {ev.ci_upper:.4f}], "
            f"CI width = {ev.ci_width:.4f}\n"
        )

    if not causal_evidence:
        lines.append(
            "- No features reached statistical significance.  "
            "Recommend CS alerts for manual review.\n"
        )

    lines.append(
        f"\n## FEATURE ANALYSIS METADATA\n"
        f"- Causal method: {features_meta.get('method', 'unknown')}\n"
        f"- Outcome variable: {features_meta.get('outcome', 'retention')}\n"
        f"- Sample size: {features_meta.get('n_samples', 'unknown')}\n"
    )

    return "\n".join(lines)


def _try_llm_reasoning(
    segments: list[SegmentRiskEvidence],
    causal_evidence: list[CausalEvidence],
    features_meta: dict[str, Any],
) -> tuple[list[SegmentRecommendation] | None, dict[str, Any]]:
    """Attempt LLM-based reasoning.  Returns (recommendations, metadata).

    Returns (None, metadata) if the LLM is unavailable or fails.
    """
    metadata: dict[str, Any] = {"llm_used": False}

    # Check if any LLM is configured
    model_str = STRATEGY_LLM_MODEL
    if not model_str:
        logger.info("No STRATEGY_LLM_MODEL configured — skipping LLM reasoning.")
        return None, metadata

    # Attempt import of langchain model init
    try:
        from langchain.chat_models import init_chat_model
    except ImportError:
        try:
            # Fallback for older langchain versions
            from langchain_community.chat_models import init_chat_model
        except ImportError:
            logger.info(
                "langchain init_chat_model not available — "
                "falling back to provider-specific import."
            )
            # Try direct OpenAI import as common fallback
            try:
                from langchain_openai import ChatOpenAI

                api_key = os.getenv("OPENAI_API_KEY", "")
                if not api_key or api_key == "your-openai-api-key-here":
                    logger.info("No valid OPENAI_API_KEY — skipping LLM reasoning.")
                    return None, metadata

                llm = ChatOpenAI(
                    model=model_str.replace("openai:", ""),
                    temperature=STRATEGY_LLM_TEMPERATURE,
                    api_key=api_key,
                )
                return _invoke_llm(llm, segments, causal_evidence, features_meta, metadata)
            except ImportError:
                logger.info("No LLM provider package installed — using heuristic fallback.")
                return None, metadata

    # Use init_chat_model for provider-agnostic instantiation
    try:
        api_key = os.getenv("OPENAI_API_KEY", "")
        # Check if we have any valid API key for the specified provider
        provider = model_str.split(":")[0] if ":" in model_str else "openai"
        key_env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google-genai": "GOOGLE_API_KEY",
        }
        key_var = key_env_vars.get(provider, "OPENAI_API_KEY")
        key_val = os.getenv(key_var, "")

        if not key_val or key_val.startswith("your-"):
            logger.info(
                f"No valid API key for provider '{provider}' "
                f"(checked ${key_var}) — skipping LLM."
            )
            return None, metadata

        llm = init_chat_model(
            model_str,
            temperature=STRATEGY_LLM_TEMPERATURE,
        )
        return _invoke_llm(llm, segments, causal_evidence, features_meta, metadata)

    except Exception as exc:
        logger.warning(f"Failed to initialise LLM ({model_str}): {exc}")
        return None, metadata


def _invoke_llm(
    llm: Any,
    segments: list[SegmentRiskEvidence],
    causal_evidence: list[CausalEvidence],
    features_meta: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[list[SegmentRecommendation] | None, dict[str, Any]]:
    """Invoke the LLM with structured output parsing."""
    from langchain_core.messages import SystemMessage, HumanMessage

    # We use a wrapper model for structured output parsing
    from pydantic import BaseModel as _PydanticBase, Field as _Field

    class _LLMRecommendation(_PydanticBase):
        """Single recommendation from the LLM."""
        segment_id: int = _Field(..., description="Cluster ID")
        action_type: str = _Field(..., description="One of: trigger_a_b_test, apply_stripe_discount, send_cs_alert")
        feature_name: str = _Field(..., description="The causal feature driving this recommendation")
        justification: str = _Field(..., description="Human-readable narrative")
        urgency: str = _Field(..., description="One of: critical, high, medium, low")

    class _LLMOutput(_PydanticBase):
        """Structured LLM output."""
        recommendations: list[_LLMRecommendation]

    user_prompt = _build_user_prompt(segments, causal_evidence, features_meta)

    try:
        structured_llm = llm.with_structured_output(_LLMOutput)

        t0 = time.time()
        result: _LLMOutput = structured_llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        elapsed = time.time() - t0

        metadata["llm_used"] = True
        metadata["model"] = str(STRATEGY_LLM_MODEL)
        metadata["latency_seconds"] = round(elapsed, 2)

        logger.info(
            f"LLM returned {len(result.recommendations)} recommendations "
            f"in {elapsed:.1f}s"
        )

        # Map LLM output to full SegmentRecommendation models
        seg_lookup = {s.segment_id: s for s in segments}
        causal_lookup = {e.feature_name: e for e in causal_evidence}
        recs: list[SegmentRecommendation] = []

        for i, llm_rec in enumerate(result.recommendations):
            seg = seg_lookup.get(llm_rec.segment_id)
            if seg is None:
                logger.warning(f"LLM referenced unknown segment {llm_rec.segment_id} — skipping.")
                continue

            causal = causal_lookup.get(llm_rec.feature_name)
            if causal is None:
                # Use the top causal feature as fallback
                causal = causal_evidence[0] if causal_evidence else None
                if causal is None:
                    logger.warning(f"No causal evidence available — skipping segment {llm_rec.segment_id}.")
                    continue

            # Validate action type
            try:
                action_type = ActionTypeEnum(llm_rec.action_type)
            except ValueError:
                logger.warning(
                    f"LLM returned invalid action_type '{llm_rec.action_type}' — "
                    f"falling back to heuristic."
                )
                action_type = _select_action_type(
                    llm_rec.urgency, seg.dominant_churn_reason, causal
                )

            confidence = _compute_confidence(causal.ci_width)
            impact = round(causal.ate * seg.segment_size, 2)
            params = _build_action_parameters(action_type, seg, causal)

            recs.append(
                SegmentRecommendation(
                    recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                    action_type=action_type,
                    action_parameters=params,
                    segment_risk=seg,
                    causal_evidence=causal,
                    justification=llm_rec.justification,
                    confidence_score=confidence,
                    estimated_impact=impact,
                    urgency=llm_rec.urgency,
                    segment_label=seg.segment_label,
                )
            )

        # Sort by impact
        recs.sort(key=lambda r: abs(r.estimated_impact), reverse=True)
        return recs, metadata

    except Exception as exc:
        logger.warning(f"LLM invocation failed: {exc} — falling back to heuristic.")
        metadata["llm_error"] = str(exc)
        return None, metadata


# ── Deterministic fallback engine ────────────────────────────────────

def _heuristic_reasoning(
    segments: list[SegmentRiskEvidence],
    causal_evidence: list[CausalEvidence],
) -> list[SegmentRecommendation]:
    """Pure-deterministic recommendation engine — no LLM needed.

    This is the fallback when no LLM API key is configured.  It applies
    simple policy rules but still produces the same Pydantic output schema,
    ensuring the Action Agent can consume the result identically.
    """
    recs: list[SegmentRecommendation] = []

    # If no significant features, use a generic placeholder
    if not causal_evidence:
        for seg in segments:
            urgency = _determine_urgency(seg.mean_risk_score, seg.is_anomalous)
            generic_causal = CausalEvidence(
                feature_name="(no significant feature)",
                treatment_description="No causally significant feature identified",
                ate=0.0,
                ci_lower=0.0,
                ci_upper=0.0,
                is_significant=False,
                ci_width=0.0,
            )
            justification = (
                f"Segment '{seg.segment_label}' (cluster {seg.segment_id}, "
                f"{seg.segment_size} customers) has a mean churn risk of "
                f"{seg.mean_risk_score:.0%} and a 6-month survival probability "
                f"of {seg.mean_survival_probability_6m:.0%}.  "
                f"The dominant churn driver is '{seg.dominant_churn_reason}'.  "
                f"No causally significant feature was identified by the Feature "
                f"Analysis Agent, so this recommendation is exploratory.  "
                f"A customer success alert is recommended for manual review "
                f"and outreach to {len(seg.customer_ids)} affected customers."
            )
            recs.append(
                SegmentRecommendation(
                    recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                    action_type=ActionTypeEnum.CS_ALERT,
                    action_parameters=_build_action_parameters(
                        ActionTypeEnum.CS_ALERT, seg, generic_causal
                    ),
                    segment_risk=seg,
                    causal_evidence=generic_causal,
                    justification=justification,
                    confidence_score=0.1,
                    estimated_impact=0.0,
                    urgency=urgency,
                    segment_label=seg.segment_label,
                )
            )
        return recs

    # Match each segment with the most impactful causal feature
    for seg in segments:
        best_causal = causal_evidence[0]  # already sorted by |ATE|
        urgency = _determine_urgency(seg.mean_risk_score, seg.is_anomalous)
        action_type = _select_action_type(
            urgency, seg.dominant_churn_reason, best_causal
        )
        confidence = _compute_confidence(best_causal.ci_width)
        impact = round(best_causal.ate * seg.segment_size, 2)
        params = _build_action_parameters(action_type, seg, best_causal)

        # Build a grounded justification
        ci_qualifier = (
            "with strong statistical confidence"
            if best_causal.ci_width < 0.15
            else (
                "with moderate confidence"
                if best_causal.ci_width < 0.3
                else "with suggestive but imprecise evidence (wide confidence interval)"
            )
        )

        action_rationale = {
            ActionTypeEnum.A_B_TEST: (
                f"An A/B test is recommended to validate whether deploying "
                f"'{best_causal.treatment_description}' reduces churn in this segment."
            ),
            ActionTypeEnum.STRIPE_DISCOUNT: (
                f"A retention discount is recommended because this segment's churn "
                f"is primarily payment-driven, and the financial intervention has "
                f"the highest expected impact."
            ),
            ActionTypeEnum.CS_ALERT: (
                f"A customer success alert is recommended to initiate manual "
                f"outreach and investigation for this segment."
            ),
        }

        justification = (
            f"Segment '{seg.segment_label}' (cluster {seg.segment_id}, "
            f"{seg.segment_size} customers) has a mean churn risk of "
            f"{seg.mean_risk_score:.0%} with a 6-month survival probability "
            f"of {seg.mean_survival_probability_6m:.0%} (mean hazard rate: "
            f"{seg.mean_hazard_rate:.4f}).  "
            f"The dominant churn driver is '{seg.dominant_churn_reason}' "
            f"({seg.churn_reason_distribution}).  "
            f"{'This cluster was flagged as anomalous by drift detection.  ' if seg.is_anomalous else ''}"
            f"Feature Analysis identifies '{best_causal.treatment_description}' as "
            f"the strongest causal lever for retention, {ci_qualifier} "
            f"(ATE = {best_causal.ate:+.4f}, 95% CI = "
            f"[{best_causal.ci_lower:.4f}, {best_causal.ci_upper:.4f}]).  "
            f"{action_rationale[action_type]}  "
            f"Estimated impact: {abs(impact):.1f} additional retained customers.  "
            f"Action targets {len(seg.customer_ids)} customers in this segment."
        )

        recs.append(
            SegmentRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:8]}",
                action_type=action_type,
                action_parameters=params,
                segment_risk=seg,
                causal_evidence=best_causal,
                justification=justification,
                confidence_score=confidence,
                estimated_impact=impact,
                urgency=urgency,
                segment_label=seg.segment_label,
            )
        )

    # Sort by estimated impact descending
    recs.sort(key=lambda r: abs(r.estimated_impact), reverse=True)
    return recs


# ── Main agent entry point ───────────────────────────────────────────

def run(
    behavior: BehaviorAnalysisResult,
    churn: ChurnPredictionResult,
    features: FeatureAnalysisResult,
) -> StrategyAgentResult:
    """Execute the Strategy Agent.

    Steps
    -----
    1. Aggregate churn risk at the segment level (deterministic).
    2. Rank causally significant features (deterministic).
    3. Filter to segments worth acting on (anomalous OR high-risk).
    4. Attempt LLM-based reasoning; fall back to heuristic if unavailable.
    5. Assemble ``StrategyAgentResult`` with ranked recommendations.

    Parameters
    ----------
    behavior : BehaviorAnalysisResult
        Output of the User Behavior Agent (Agent 1).
    churn : ChurnPredictionResult
        Output of the Churn Prediction Agent (Agent 2).
    features : FeatureAnalysisResult
        Output of the Feature Analysis Agent (Agent 3).

    Returns
    -------
    StrategyAgentResult
        Ranked list of recommendations, one per flagged segment.
    """
    t0 = time.time()
    logger.info("Strategy Agent: starting reasoning pipeline")

    # Step 1 — Aggregate segments
    all_segments = _aggregate_segments(behavior, churn)
    logger.info(f"  Aggregated {len(all_segments)} segments (excl. noise cluster)")

    # Step 2 — Rank causal features
    causal_evidence = _rank_features(features)
    logger.info(
        f"  {len(causal_evidence)} significant causal features "
        f"(from {len(features.effects)} total)"
    )

    # Step 3 — Filter to actionable segments
    # Include segments that are anomalous OR have mean risk ≥ 0.35
    RISK_THRESHOLD = 0.35
    flagged_segments = [
        seg for seg in all_segments
        if seg.is_anomalous or seg.mean_risk_score >= RISK_THRESHOLD
    ]

    # If nothing is flagged, lower threshold to include at least top-risk segments
    if not flagged_segments and all_segments:
        all_segments.sort(key=lambda s: s.mean_risk_score, reverse=True)
        flagged_segments = all_segments[:max(1, len(all_segments) // 3)]
        logger.info(
            f"  No segments above threshold — using top {len(flagged_segments)} "
            f"by risk score"
        )

    logger.info(f"  {len(flagged_segments)} segments flagged for recommendation")

    # Step 4 — Reasoning
    recommendations, metadata = _try_llm_reasoning(
        flagged_segments, causal_evidence,
        {
            "method": features.method,
            "outcome": features.outcome_variable,
            "n_samples": features.n_samples,
        },
    )

    if recommendations is None:
        logger.info("  Using deterministic heuristic reasoning engine")
        recommendations = _heuristic_reasoning(flagged_segments, causal_evidence)
        metadata["reasoning_engine"] = "heuristic"
    else:
        metadata["reasoning_engine"] = "llm"

    elapsed = time.time() - t0
    metadata["total_time_seconds"] = round(elapsed, 2)

    result = StrategyAgentResult(
        recommendations=recommendations,
        segments_analysed=len(all_segments),
        segments_flagged=len(flagged_segments),
        significant_features_available=len(causal_evidence),
        pipeline_metadata=metadata,
    )

    logger.info(
        f"Strategy Agent complete in {elapsed:.1f}s: "
        f"{len(recommendations)} recommendation(s), "
        f"engine={metadata.get('reasoning_engine', 'unknown')}"
    )
    return result


# ── Wrapper for dict-based invocation (pipeline compatibility) ───────

def run_from_dict(inputs: dict[str, Any]) -> StrategyAgentResult:
    """Invoke the Strategy Agent from a dict of serialised upstream outputs.

    This is the entry point used by the LangChain ``RunnableLambda`` and
    ``pipeline.py``.  It accepts a dict with keys ``behavior``, ``churn``,
    ``features`` — each either a Pydantic model or a dict that can be
    parsed into one.
    """
    behavior_raw = inputs.get("behavior")
    churn_raw = inputs.get("churn")
    features_raw = inputs.get("features")

    if behavior_raw is None or churn_raw is None or features_raw is None:
        raise ValueError(
            "Strategy Agent requires 'behavior', 'churn', and 'features' keys."
        )

    # Parse if raw dicts
    if isinstance(behavior_raw, dict):
        behavior_raw = BehaviorAnalysisResult(**behavior_raw)
    if isinstance(churn_raw, dict):
        churn_raw = ChurnPredictionResult(**churn_raw)
    if isinstance(features_raw, dict):
        features_raw = FeatureAnalysisResult(**features_raw)

    return run(behavior_raw, churn_raw, features_raw)


# ── Utility: convert to Action Agent input format ────────────────────

def to_action_agent_inputs(
    result: StrategyAgentResult,
) -> list[dict[str, Any]]:
    """Convert Strategy Agent output to Action Agent ``StrategyRecommendation``
    dicts.

    Each recommendation is mapped to the fields expected by
    ``action_agent.schemas.StrategyRecommendation``:

    - recommendation_id → recommendation_id
    - action_type       → action_type (enum value string)
    - target_entity     → segment_label
    - description       → justification (narrative)
    - parameters        → action_parameters
    - confidence_score  → confidence_score
    - justification     → justification (same narrative, for the audit log)
    """
    action_inputs: list[dict[str, Any]] = []
    for rec in result.recommendations:
        action_inputs.append({
            "recommendation_id": rec.recommendation_id,
            "action_type": rec.action_type.value,
            "target_entity": rec.segment_label,
            "description": rec.justification,
            "parameters": rec.action_parameters,
            "confidence_score": rec.confidence_score,
            "justification": rec.justification,
        })
    return action_inputs


# ── LangChain LCEL wrapper ───────────────────────────────────────────

strategy_agent_runnable = RunnableLambda(run_from_dict).with_config(
    {"run_name": "StrategyAgent"}
)
"""LangChain Runnable that wraps :func:`run_from_dict`.

Usage::

    from agents.strategy_agent import strategy_agent_runnable

    result = strategy_agent_runnable.invoke({
        "behavior": behavior_result,  # or .model_dump()
        "churn": churn_result,
        "features": feature_result,
    })
"""
