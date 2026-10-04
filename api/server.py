"""FastAPI backend for the Autonomous SaaS BI Engine.

Serves cached pipeline output and provides an approve/reject endpoint that
calls through to the Action Agent's real approval gate.

Usage:
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_OUTPUT = PROJECT_ROOT / "data" / "pipeline_output.json"

# Make project root importable so we can import the action_agent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Autonomous SaaS BI Engine API",
    description="Serves cached ML pipeline results and handles recommendation approvals.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, lock this to the frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory cache for pipeline output + recommendation statuses
# ---------------------------------------------------------------------------
_cache: dict[str, Any] = {
    "pipeline_output": None,
    "loaded_at": None,
    "recommendation_statuses": {},  # rec_id -> { status, decided_at, audit_id? }
}


def _load_pipeline_output() -> dict[str, Any]:
    """Load (or reload) the pipeline output JSON into memory."""
    if not PIPELINE_OUTPUT.exists():
        raise FileNotFoundError(f"Pipeline output not found at {PIPELINE_OUTPUT}")

    with open(PIPELINE_OUTPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    _cache["pipeline_output"] = data
    _cache["loaded_at"] = datetime.now(timezone.utc).isoformat()
    return data


def _get_pipeline() -> dict[str, Any]:
    """Return cached pipeline output, loading if necessary."""
    if _cache["pipeline_output"] is None:
        _load_pipeline_output()
    return _cache["pipeline_output"]


# Load on startup
@app.on_event("startup")
async def startup_load():
    try:
        _load_pipeline_output()
    except FileNotFoundError:
        pass  # Will raise on first API call if still missing


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    """Approve or reject a recommendation."""
    recommendation_id: str = Field(..., description="ID of the recommendation to act on")
    decision: str = Field(..., pattern="^(approved|rejected)$", description="'approved' or 'rejected'")


class ApprovalResponse(BaseModel):
    recommendation_id: str
    decision: str
    action_agent_result: Optional[dict[str, Any]] = None
    decided_at: str
    audit_id: Optional[str] = None


class RefreshResponse(BaseModel):
    status: str
    loaded_at: str
    n_records: int


class SegmentSummary(BaseModel):
    cluster_id: int
    label: str
    size: int
    centroid_features: dict[str, float]
    is_anomalous: bool
    # Joined from churn predictions
    mean_risk_score: float
    mean_survival_6m: float
    mean_hazard_rate: float
    churn_reason_distribution: dict[str, int]


class FeatureImpact(BaseModel):
    feature_name: str
    treatment_description: str
    ate: float
    ci_lower: float
    ci_upper: float
    p_value: Optional[float]
    is_significant: bool


class RecommendationOut(BaseModel):
    recommendation_id: str
    action_type: str
    action_parameters: dict[str, Any]
    segment_label: str
    justification: str
    confidence_score: float
    estimated_impact: float
    urgency: str
    segment_risk: dict[str, Any]
    causal_evidence: dict[str, Any]
    status: str  # "pending" | "approved" | "rejected"
    decided_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: aggregate churn risk per cluster
# ---------------------------------------------------------------------------

def _aggregate_churn_by_cluster(pipeline: dict) -> dict[int, dict]:
    """Join churn predictions to cluster assignments, return per-cluster aggregates."""
    behavior = pipeline["user_behavior"]
    churn = pipeline["churn_prediction"]

    # Build customer -> cluster map
    cust_cluster = {c["customer_id"]: c["cluster_id"] for c in behavior["customer_clusters"]}

    # Accumulate per cluster
    clusters: dict[int, dict] = {}
    for pred in churn["predictions"]:
        cid = pred["customer_id"]
        clust = cust_cluster.get(cid)
        if clust is None:
            continue
        if clust not in clusters:
            clusters[clust] = {
                "risk_scores": [],
                "survival_6m": [],
                "hazard_rates": [],
                "reasons": {},
            }
        bucket = clusters[clust]
        bucket["risk_scores"].append(pred["risk_score"])
        bucket["survival_6m"].append(pred["survival_probability_6m"])
        bucket["hazard_rates"].append(pred["hazard_rate"])
        reason = pred.get("churn_reason", "unknown")
        bucket["reasons"][reason] = bucket["reasons"].get(reason, 0) + 1

    # Compute means
    result = {}
    for cid, bucket in clusters.items():
        n = len(bucket["risk_scores"])
        result[cid] = {
            "mean_risk_score": round(sum(bucket["risk_scores"]) / n, 4) if n else 0,
            "mean_survival_6m": round(sum(bucket["survival_6m"]) / n, 4) if n else 0,
            "mean_hazard_rate": round(sum(bucket["hazard_rates"]) / n, 4) if n else 0,
            "churn_reason_distribution": bucket["reasons"],
        }
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    """Health check + metadata about the cached pipeline."""
    pipeline = _get_pipeline()
    return {
        "status": "ok",
        "loaded_at": _cache["loaded_at"],
        "pipeline_metadata": pipeline.get("pipeline_metadata", {}),
    }


@app.post("/api/refresh", response_model=RefreshResponse)
async def refresh_pipeline():
    """Reload the pipeline output from disk (after a batch run)."""
    try:
        data = _load_pipeline_output()
        return RefreshResponse(
            status="ok",
            loaded_at=_cache["loaded_at"],
            n_records=data.get("pipeline_metadata", {}).get("n_records", 0),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/segments", response_model=list[SegmentSummary])
async def get_segments():
    """Return cluster summaries with aggregate churn risk (User Behavior + Churn joined)."""
    pipeline = _get_pipeline()
    profiles = pipeline["user_behavior"]["cluster_profiles"]
    churn_agg = _aggregate_churn_by_cluster(pipeline)

    result = []
    for p in profiles:
        cid = p["cluster_id"]
        agg = churn_agg.get(cid, {})
        result.append(SegmentSummary(
            cluster_id=cid,
            label=p["label"],
            size=p["size"],
            centroid_features=p["centroid_features"],
            is_anomalous=p["is_anomalous"],
            mean_risk_score=agg.get("mean_risk_score", 0),
            mean_survival_6m=agg.get("mean_survival_6m", 0),
            mean_hazard_rate=agg.get("mean_hazard_rate", 0),
            churn_reason_distribution=agg.get("churn_reason_distribution", {}),
        ))

    # Sort by risk descending
    result.sort(key=lambda s: s.mean_risk_score, reverse=True)
    return result


@app.get("/api/features", response_model=list[FeatureImpact])
async def get_feature_impacts():
    """Return ranked causal feature impacts from Feature Analysis."""
    pipeline = _get_pipeline()
    effects = pipeline["feature_analysis"]["effects"]

    result = []
    for e in effects:
        result.append(FeatureImpact(
            feature_name=e["feature_name"],
            treatment_description=e["treatment_description"],
            ate=e["ate"],
            ci_lower=e["ci_lower"],
            ci_upper=e["ci_upper"],
            p_value=e.get("p_value"),
            is_significant=e["is_significant"],
        ))

    # Ranked by |ATE| descending (already should be, but enforce)
    result.sort(key=lambda f: abs(f.ate), reverse=True)
    return result


@app.get("/api/recommendations", response_model=list[RecommendationOut])
async def get_recommendations():
    """Return current Strategy Agent recommendations with their approval status."""
    pipeline = _get_pipeline()
    recs = pipeline["strategy"]["recommendations"]

    result = []
    for r in recs:
        rec_id = r["recommendation_id"]
        status_info = _cache["recommendation_statuses"].get(rec_id, {})
        result.append(RecommendationOut(
            recommendation_id=rec_id,
            action_type=r["action_type"],
            action_parameters=r.get("action_parameters", {}),
            segment_label=r.get("segment_label", ""),
            justification=r.get("justification", ""),
            confidence_score=r.get("confidence_score", 0),
            estimated_impact=r.get("estimated_impact", 0),
            urgency=r.get("urgency", "medium"),
            segment_risk=r.get("segment_risk", {}),
            causal_evidence=r.get("causal_evidence", {}),
            status=status_info.get("status", "pending"),
            decided_at=status_info.get("decided_at"),
        ))

    return result


@app.post("/api/recommendations/decide", response_model=ApprovalResponse)
async def decide_recommendation(req: ApprovalRequest):
    """Approve or reject a recommendation — calls through to the Action Agent.

    This is the real human-in-the-loop gate. When approved, the Action Agent's
    workflow runs with human_approved=True; when rejected, it runs with
    human_approved=False. The Action Agent's execute_action_node will either
    execute or cancel based on this flag.
    """
    pipeline = _get_pipeline()
    recs = pipeline["strategy"]["recommendations"]

    # Find the recommendation
    rec = None
    for r in recs:
        if r["recommendation_id"] == req.recommendation_id:
            rec = r
            break

    if rec is None:
        raise HTTPException(status_code=404, detail=f"Recommendation '{req.recommendation_id}' not found")

    # Check if already decided
    existing = _cache["recommendation_statuses"].get(req.recommendation_id, {})
    if existing.get("status") in ("approved", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"Recommendation '{req.recommendation_id}' already {existing['status']}",
        )

    decided_at = datetime.now(timezone.utc).isoformat()
    is_approved = req.decision == "approved"
    action_result = None
    audit_id = None

    # Call through to the Action Agent with the real approval state
    try:
        # Build the input payload matching what action_agent expects
        action_input = {
            "recommendation_id": rec["recommendation_id"],
            "action_type": rec["action_type"],
            "target_entity": rec.get("segment_label", ""),
            "description": rec.get("justification", ""),
            "parameters": rec.get("action_parameters", {}),
            "confidence_score": rec.get("confidence_score", 0),
            "justification": rec.get("justification", ""),
        }

        # Import and run the action agent with the pre-set approval
        # We use auto_approve_test to bypass interactive prompt
        sys.path.insert(0, str(PROJECT_ROOT / "action_agent"))
        from action_agent.agent import run_action_agent

        result_state = run_action_agent(
            action_input,
            human_approved=is_approved,
            auto_approve_test=is_approved,
        )

        action_result = result_state.get("execution_result")
        audit_id = result_state.get("audit_id")

    except Exception as exc:
        # If Action Agent fails, still record the decision but note the error
        action_result = {
            "status": "error",
            "error": str(exc),
            "timestamp": decided_at,
        }

    # Record the status
    _cache["recommendation_statuses"][req.recommendation_id] = {
        "status": req.decision,
        "decided_at": decided_at,
        "audit_id": audit_id,
        "action_result": action_result,
    }

    return ApprovalResponse(
        recommendation_id=req.recommendation_id,
        decision=req.decision,
        action_agent_result=action_result,
        decided_at=decided_at,
        audit_id=audit_id,
    )


@app.get("/api/pipeline-metadata")
async def get_pipeline_metadata():
    """Return pipeline run metadata including timing and model info."""
    pipeline = _get_pipeline()
    return {
        "pipeline_metadata": pipeline.get("pipeline_metadata", {}),
        "strategy_metadata": pipeline.get("strategy", {}).get("pipeline_metadata", {}),
        "loaded_at": _cache["loaded_at"],
        "feature_analysis_method": pipeline.get("feature_analysis", {}).get("method", ""),
        "behavior_method": pipeline.get("user_behavior", {}).get("method_used", ""),
        "classifier_metrics": pipeline.get("churn_prediction", {}).get("classifier_metrics", {}),
        "survival_concordance": pipeline.get("churn_prediction", {}).get("survival_model_concordance", 0),
    }
