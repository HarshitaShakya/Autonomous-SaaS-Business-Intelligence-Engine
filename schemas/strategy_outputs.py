"""Pydantic output schemas for the Strategy Agent (Agent 4).

These schemas are the *contract* between the Strategy Agent and the downstream
Action Agent.  Every field was derived from the Action Agent's
``StrategyRecommendation`` input model and its ``ActionType`` enum
(``action_agent/schemas.py``), so the two sides stay in sync by construction.

Design decisions
----------------
* ``ActionTypeEnum`` mirrors ``action_agent.schemas.ActionType`` values exactly.
  If the Action Agent gains a new tool, add it here too.
* ``confidence_score`` is *not* simply the LLM's self-assessed confidence;
  it is computed deterministically from the upstream Feature Analysis
  confidence interval width, so it cannot be hallucinated upward.
* ``justification`` is a human-readable narrative intended for a manager to
  read before clicking Approve in the Action Agent — it must name the segment,
  the risk evidence, and the causal evidence in plain English.
* ``causal_evidence`` preserves the full CI from Feature Analysis so a reviewer
  can verify the LLM didn't overstate certainty.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Action types — pinned to what the Action Agent actually implements
# ---------------------------------------------------------------------------

class ActionTypeEnum(str, Enum):
    """Supported action types, mirroring ``action_agent.schemas.ActionType``.

    The Strategy Agent MUST only emit values from this enum.  If the Action
    Agent adds a new tool, add the corresponding member here.
    """

    A_B_TEST = "trigger_a_b_test"
    STRIPE_DISCOUNT = "apply_stripe_discount"
    CS_ALERT = "send_cs_alert"


# ---------------------------------------------------------------------------
# Evidence sub-models — carry upstream numbers through unchanged
# ---------------------------------------------------------------------------

class SegmentRiskEvidence(BaseModel):
    """Aggregated churn risk statistics for a single cluster/segment.

    All numbers come directly from the Churn Prediction Agent's output,
    aggregated at the segment level by the Strategy Agent's pre-processing
    (not by the LLM).
    """

    segment_id: int = Field(
        ..., description="Cluster ID from the User Behavior Agent."
    )
    segment_label: str = Field(
        ..., description="Human-readable cluster label from the User Behavior Agent."
    )
    segment_size: int = Field(
        ..., ge=0, description="Number of customers in this cluster."
    )
    mean_risk_score: float = Field(
        ..., ge=0, le=1,
        description="Mean churn probability across cluster members.",
    )
    mean_hazard_rate: float = Field(
        ..., ge=0,
        description="Mean Cox PH hazard rate across cluster members.",
    )
    mean_survival_probability_6m: float = Field(
        ..., ge=0, le=1,
        description="Mean P(survive ≥ 6 months) across cluster members.",
    )
    dominant_churn_reason: str = Field(
        ...,
        description="Most frequent churn reason category in this cluster.",
    )
    churn_reason_distribution: dict[str, int] = Field(
        ...,
        description="Count of each churn reason in the cluster.",
    )
    customer_ids: list[str] = Field(
        ...,
        description="All customer IDs in this cluster (for the Action Agent).",
    )
    is_anomalous: bool = Field(
        default=False,
        description="True if the User Behavior Agent flagged this cluster.",
    )


class CausalEvidence(BaseModel):
    """Feature-level causal evidence carried through from Feature Analysis.

    The Strategy Agent MUST NOT modify these numbers.  The LLM uses them to
    reason about which intervention to recommend, but the output preserves
    the original estimates and CI so a human reviewer can verify claims.
    """

    feature_name: str = Field(
        ..., description="Name of the treatment feature."
    )
    treatment_description: str = Field(
        ..., description="Plain-language description of the treatment."
    )
    ate: float = Field(
        ..., description="Average Treatment Effect on retention."
    )
    ci_lower: float = Field(
        ..., description="Lower bound of 95% confidence interval."
    )
    ci_upper: float = Field(
        ..., description="Upper bound of 95% confidence interval."
    )
    is_significant: bool = Field(
        ..., description="True if the 95% CI excludes zero."
    )
    ci_width: float = Field(
        ..., ge=0,
        description="Width of the CI (ci_upper − ci_lower); wider = less certain.",
    )


# ---------------------------------------------------------------------------
# Per-segment recommendation — the primary output unit
# ---------------------------------------------------------------------------

class SegmentRecommendation(BaseModel):
    """One actionable recommendation for a flagged customer segment.

    This model is designed so that its fields can be trivially mapped to the
    Action Agent's ``StrategyRecommendation`` input schema:

    ==================== ============================
    SegmentRecommendation  → StrategyRecommendation
    ==================== ============================
    recommendation_id      recommendation_id
    action_type            action_type
    segment_label          target_entity
    justification          description  *and*  justification
    action_parameters      parameters
    confidence_score       confidence_score
    ==================== ============================
    """

    recommendation_id: str = Field(
        ..., description="Unique ID for this recommendation (e.g. 'rec_001')."
    )

    # ── Action ───────────────────────────────────────────────────────
    action_type: ActionTypeEnum = Field(
        ...,
        description=(
            "The action the Action Agent should execute.  Must be one of: "
            "trigger_a_b_test, apply_stripe_discount, send_cs_alert."
        ),
    )
    action_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Key-value parameters for the chosen action tool.  "
            "For trigger_a_b_test: {segment_id, experiment_name}.  "
            "For apply_stripe_discount: {customer_id, coupon_code}.  "
            "For send_cs_alert: {channel, message}."
        ),
    )

    # ── Evidence ─────────────────────────────────────────────────────
    segment_risk: SegmentRiskEvidence = Field(
        ..., description="Aggregated risk evidence for the target segment."
    )
    causal_evidence: CausalEvidence = Field(
        ...,
        description="Upstream causal effect driving this recommendation.",
    )

    # ── Narrative ────────────────────────────────────────────────────
    justification: str = Field(
        ...,
        description=(
            "Human-readable narrative justification.  Must name the segment, "
            "the churn risk evidence, and the causal evidence in plain English.  "
            "This is what a manager reads before clicking Approve."
        ),
    )

    # ── Confidence & ranking ─────────────────────────────────────────
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0,
        description=(
            "Confidence in this recommendation, derived from the Feature "
            "Analysis CI width.  Narrow CI → high confidence; wide CI → low.  "
            "NOT the LLM's self-assessed confidence."
        ),
    )
    estimated_impact: float = Field(
        ...,
        description=(
            "Estimated retention impact = ATE × segment_size.  "
            "Used to rank recommendations by expected customer-level lift."
        ),
    )
    urgency: str = Field(
        ...,
        description=(
            "One of 'critical', 'high', 'medium', 'low' — derived from "
            "mean_risk_score and is_anomalous."
        ),
    )
    segment_label: str = Field(
        ..., description="Short segment descriptor for the Action Agent's target_entity."
    )


# ---------------------------------------------------------------------------
# Top-level Strategy Agent output
# ---------------------------------------------------------------------------

class StrategyAgentResult(BaseModel):
    """Complete output of the Strategy Agent (Agent 4).

    Contains a ranked list of recommendations (one per flagged segment),
    ordered by estimated impact descending, plus pipeline-level metadata.

    The Action Agent consumes ``recommendations`` — each can be mapped 1:1
    to a ``StrategyRecommendation`` for the Action Agent workflow.
    """

    recommendations: list[SegmentRecommendation] = Field(
        ...,
        description=(
            "Ranked recommendations, one per flagged segment.  "
            "Ordered by estimated_impact descending."
        ),
    )
    segments_analysed: int = Field(
        ..., ge=0,
        description="Total number of clusters from the User Behavior Agent.",
    )
    segments_flagged: int = Field(
        ..., ge=0,
        description="Number of segments that received a recommendation.",
    )
    significant_features_available: int = Field(
        ..., ge=0,
        description="Number of causally significant features from Feature Analysis.",
    )
    pipeline_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="LLM provider, model, token usage, and timing information.",
    )


# ---------------------------------------------------------------------------
# Strategy Agent input — aggregation of all three upstream agents
# ---------------------------------------------------------------------------

class StrategyAgentInput(BaseModel):
    """Typed input to the Strategy Agent, bundling all three upstream outputs.

    This is the Pydantic counterpart of the dict that ``pipeline.py``
    assembles after the three ML agents run.
    """

    behavior: Any = Field(
        ..., description="Output of the User Behavior Agent (BehaviorAnalysisResult)."
    )
    churn: Any = Field(
        ..., description="Output of the Churn Prediction Agent (ChurnPredictionResult)."
    )
    features: Any = Field(
        ..., description="Output of the Feature Analysis Agent (FeatureAnalysisResult)."
    )
