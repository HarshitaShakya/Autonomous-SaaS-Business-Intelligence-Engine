"""Typed Pydantic output schemas for the three ML agents.

Each agent returns a single top-level model that a future LLM-based Strategy
Agent can parse as structured JSON.  All models are fully serialisable and use
only primitive / standard-library types so they can cross process boundaries
without custom codecs.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent 1 — User Behavior Agent
# ---------------------------------------------------------------------------

class ClusterProfile(BaseModel):
    """Aggregate description of one behavioural cluster."""

    cluster_id: int = Field(..., description="Cluster label (−1 = noise in DBSCAN).")
    size: int = Field(..., ge=0, description="Number of customers in the cluster.")
    centroid_features: dict[str, float] = Field(
        ..., description="Mean value of each engineered feature for this cluster."
    )
    label: str = Field(
        ..., description="Short human-readable description of the cluster."
    )
    is_anomalous: bool = Field(
        default=False,
        description="True if the cluster was flagged by drift / anomaly detection.",
    )


class CustomerCluster(BaseModel):
    """Per-customer cluster assignment and anomaly score."""

    customer_id: str
    cluster_id: int = Field(..., description="Assigned cluster (−1 = noise).")
    anomaly_score: float = Field(
        ...,
        description=(
            "Autoencoder reconstruction error — higher means more anomalous."
        ),
    )


class BehaviorAnalysisResult(BaseModel):
    """Complete output of the User Behavior Agent.

    Designed so an LLM Strategy Agent can iterate ``cluster_profiles`` to
    understand segments, check ``anomalous_clusters`` for alerts, and look up
    any single customer's membership via ``customer_clusters``.
    """

    customer_clusters: list[CustomerCluster] = Field(
        ..., description="Per-customer cluster assignments."
    )
    cluster_profiles: list[ClusterProfile] = Field(
        ..., description="Aggregate profile for every discovered cluster."
    )
    anomalous_clusters: list[int] = Field(
        default_factory=list,
        description="IDs of clusters flagged as anomalous / drifting.",
    )
    method_used: str = Field(
        ..., description="Primary clustering method: 'DBSCAN' or 'autoencoder'."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Hyper-parameters, silhouette score, comparison notes, etc.",
    )


# ---------------------------------------------------------------------------
# Agent 2 — Churn Prediction Agent
# ---------------------------------------------------------------------------

class CustomerChurnRisk(BaseModel):
    """Per-customer churn risk assessment."""

    customer_id: str
    risk_score: float = Field(
        ..., ge=0, le=1,
        description="Predicted churn probability from the binary classifier.",
    )
    survival_probability_6m: float = Field(
        ..., ge=0, le=1,
        description="P(customer survives ≥ 6 more months) from survival model.",
    )
    median_survival_time: Optional[float] = Field(
        default=None,
        description="Estimated months until churn (None if censored / infinite).",
    )
    churn_reason: str = Field(
        ...,
        description=(
            "Dominant churn driver: 'dissatisfaction', 'payment', or 'mixed'."
        ),
    )
    hazard_rate: float = Field(
        ..., ge=0,
        description="Instantaneous hazard rate from the Cox model.",
    )


class ChurnPredictionResult(BaseModel):
    """Complete output of the Churn Prediction Agent.

    Includes per-customer risk assessments, model quality metrics, and feature
    importances that a Strategy Agent can use to prioritise interventions.
    """

    predictions: list[CustomerChurnRisk] = Field(
        ..., description="Per-customer churn risk assessments."
    )
    classifier_metrics: dict[str, float] = Field(
        ...,
        description="Binary classifier metrics: accuracy, auc_roc, f1, precision, recall.",
    )
    survival_model_concordance: float = Field(
        ..., ge=0, le=1,
        description="Harrell's C-index for the survival model.",
    )
    feature_importances: dict[str, float] = Field(
        ..., description="Feature importance scores from the classifier."
    )


# ---------------------------------------------------------------------------
# Agent 3 — Feature Analysis Agent
# ---------------------------------------------------------------------------

class CausalFeatureEffect(BaseModel):
    """Causal effect estimate for one treatment variable."""

    feature_name: str = Field(..., description="Name of the treatment feature.")
    treatment_description: str = Field(
        ...,
        description="Plain-language description of the treatment (e.g. 'Having TechSupport').",
    )
    ate: float = Field(
        ..., description="Average Treatment Effect on retention."
    )
    ci_lower: float = Field(..., description="Lower bound of 95 % confidence interval.")
    ci_upper: float = Field(..., description="Upper bound of 95 % confidence interval.")
    p_value: Optional[float] = Field(
        default=None, description="p-value for the null H₀: ATE = 0."
    )
    is_significant: bool = Field(
        ..., description="True if the 95 % CI excludes zero."
    )


class FeatureAnalysisResult(BaseModel):
    """Complete output of the Feature Analysis Agent.

    Provides a ranked list of product features / attributes with their
    estimated *causal* effect on customer retention, so the Strategy Agent
    can distinguish genuine drivers from confounded correlations.
    """

    effects: list[CausalFeatureEffect] = Field(
        ..., description="Feature effects ranked by |ATE| descending."
    )
    method: str = Field(
        ..., description="Causal method used: 'LinearDML', 'CausalForestDML', etc."
    )
    confounders_used: list[str] = Field(
        ..., description="Names of confounder / control variables."
    )
    outcome_variable: str = Field(
        ..., description="Outcome variable used (e.g. 'retention')."
    )
    n_samples: int = Field(..., ge=0, description="Number of samples analysed.")
