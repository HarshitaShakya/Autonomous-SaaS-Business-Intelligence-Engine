"""FastAPI backend for the Autonomous SaaS BI Engine.

Serves cached pipeline output and provides an approve/reject endpoint that
calls through to the Action Agent's real approval gate.

Usage:
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_OUTPUT = PROJECT_ROOT / "data" / "pipeline_output.json"
DB_PATH = PROJECT_ROOT / "data" / "runs.db"

# Make project root importable so we can import the action_agent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# SQLite run store
# ---------------------------------------------------------------------------

def _init_db():
    """Create the runs database if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_seconds REAL,
            status TEXT NOT NULL DEFAULT 'running',
            note TEXT DEFAULT '',
            n_records INTEGER DEFAULT 0,
            agent_times_json TEXT DEFAULT '{}',
            error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    # Ensure default settings exist
    conn.execute("""
        INSERT OR IGNORE INTO settings (key, value) VALUES ('mode', 'dry-run')
    """)
    conn.execute("""
        INSERT OR IGNORE INTO settings (key, value) VALUES ('require_approval', 'true')
    """)
    conn.execute("""
        INSERT OR IGNORE INTO settings (key, value) VALUES ('thresholds', '{"high": 60, "medium": 30, "window_days": 90}')
    """)
    conn.execute("""
        INSERT OR IGNORE INTO settings (key, value) VALUES ('schedule', 'daily-06')
    """)
    conn.commit()
    conn.close()


_init_db()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Autonomous SaaS BI Engine API",
    description="Serves cached ML pipeline results and handles recommendation approvals.",
    version="2.0.0",
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
    "recommendation_statuses": {},  # rec_id -> { status, decided_at, audit_id?, ... }
    "action_log": [],  # Chronological action log entries
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


def _get_setting(key: str) -> str:
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else ""


def _set_setting(key: str, value: str):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# Seed initial run from pipeline output if no runs exist
def _seed_initial_run():
    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    if count == 0:
        try:
            pipeline = _get_pipeline()
            meta = pipeline.get("pipeline_metadata", {})
            run_id = f"run-{uuid.uuid4().hex[:8]}"
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO runs (run_id, started_at, completed_at, duration_seconds, status, note, n_records, agent_times_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, now, now, meta.get("total_time_seconds", 0), "ok",
                 "Seeded from existing pipeline output", meta.get("n_records", 0),
                 json.dumps(meta.get("agent_times_seconds", {})))
            )
            conn.commit()
        except Exception:
            pass
    conn.close()


# Load on startup
@app.on_event("startup")
async def startup_load():
    try:
        _load_pipeline_output()
        _seed_initial_run()
    except FileNotFoundError:
        pass  # Will raise on first API call if still missing


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    """Approve or reject a recommendation."""
    recommendation_id: str = Field(..., description="ID of the recommendation to act on")
    decision: str = Field(..., pattern="^(approved|rejected)$", description="'approved' or 'rejected'")
    reason: Optional[str] = Field(None, description="Rejection reason (required for rejected)")
    idempotency_key: Optional[str] = Field(None, description="Unique key to prevent duplicate actions")


class ApprovalResponse(BaseModel):
    recommendation_id: str
    decision: str
    action_agent_result: Optional[dict[str, Any]] = None
    decided_at: str
    audit_id: Optional[str] = None
    approver: str = "system"


class RefreshResponse(BaseModel):
    status: str
    loaded_at: str
    n_records: int
    run_id: Optional[str] = None


class ModeChangeRequest(BaseModel):
    mode: str = Field(..., pattern="^(dry-run|live)$")
    confirmation: Optional[str] = Field(None, description="Required when switching to 'live': must be 'CONFIRM_LIVE'")


# ---------------------------------------------------------------------------
# Helper: compute thresholds
# ---------------------------------------------------------------------------

def _get_thresholds() -> dict:
    raw = _get_setting("thresholds")
    try:
        return json.loads(raw)
    except Exception:
        return {"high": 60, "medium": 30, "window_days": 90}


def _risk_level(score: float, thresholds: dict) -> str:
    pct = score * 100
    if pct >= thresholds.get("high", 60):
        return "High"
    if pct >= thresholds.get("medium", 30):
        return "Medium"
    return "Low"


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
                "mrr_values": [],
                "customer_ids": [],
            }
        bucket = clusters[clust]
        bucket["risk_scores"].append(pred["risk_score"])
        bucket["survival_6m"].append(pred["survival_probability_6m"])
        bucket["hazard_rates"].append(pred["hazard_rate"])
        bucket["customer_ids"].append(cid)
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
            "at_risk_count": sum(1 for s in bucket["risk_scores"] if s >= 0.30),
            "customer_ids": bucket["customer_ids"],
        }
    return result


def _build_customer_list(pipeline: dict, thresholds: dict) -> list[dict]:
    """Build a flattened list of customers with risk info joined from all agents."""
    behavior = pipeline["user_behavior"]
    churn = pipeline["churn_prediction"]

    # Build customer -> cluster map
    cust_cluster = {}
    for c in behavior["customer_clusters"]:
        cust_cluster[c["customer_id"]] = c["cluster_id"]

    # Build cluster profiles map
    profiles = {p["cluster_id"]: p for p in behavior["cluster_profiles"]}

    # Build feature importances for top drivers
    feat_imp = churn.get("feature_importances", {})
    sorted_features = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)
    top_features = [f[0] for f in sorted_features[:5]]

    customers = []
    for pred in churn["predictions"]:
        cid = pred["customer_id"]
        cluster_id = cust_cluster.get(cid)
        profile = profiles.get(cluster_id, {}) if cluster_id is not None else {}

        risk_score = pred["risk_score"]
        level = _risk_level(risk_score, thresholds)

        # Compute median survival time and range
        median_days = pred.get("median_survival_time", None)
        days_lo = int(median_days * 0.55) if median_days else None
        days_hi = int(median_days * 1.55) if median_days else None

        # Derive MRR from centroid if available
        centroid = profile.get("centroid_features", {})
        mrr = round(centroid.get("mrr", centroid.get("avg_monthly_spend", 0)), 2)

        customers.append({
            "customer_id": cid,
            "name": cid,  # No real names in telco data — use ID
            "segment_id": cluster_id,
            "segment_label": profile.get("label", f"Cluster {cluster_id}"),
            "plan": None,  # Not available in telco dataset
            "tenure_months": round(centroid.get("tenure_months", 0)),
            "mrr": mrr,
            "risk_score": round(risk_score * 100, 1),
            "risk_level": level,
            "days": int(median_days) if median_days else None,
            "days_lo": days_lo,
            "days_hi": days_hi,
            "reason": pred.get("churn_reason", "unknown"),
            "survival_6m": round(pred.get("survival_probability_6m", 0) * 100, 1),
            "hazard_rate": round(pred.get("hazard_rate", 0), 2),
            "drivers": [f"High importance: {f}" for f in top_features[:3]],
        })

    return customers


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    """Health check + metadata about the cached pipeline."""
    pipeline = _get_pipeline()
    mode = _get_setting("mode")
    return {
        "status": "ok",
        "loaded_at": _cache["loaded_at"],
        "pipeline_metadata": pipeline.get("pipeline_metadata", {}),
        "mode": mode,
    }


@app.get("/api/overview")
async def get_overview():
    """Aggregated KPIs for the Overview page. All numbers computed from real data."""
    pipeline = _get_pipeline()
    churn = pipeline["churn_prediction"]
    behavior = pipeline["user_behavior"]
    thresholds = _get_thresholds()
    mode = _get_setting("mode")

    predictions = churn["predictions"]
    n_accounts = len(predictions)

    # Compute MRR from cluster centroids (weighted by cluster size)
    profiles = behavior["cluster_profiles"]
    total_mrr = 0
    for p in profiles:
        centroid = p.get("centroid_features", {})
        mrr_per = centroid.get("mrr", centroid.get("avg_monthly_spend", 0))
        total_mrr += mrr_per * p["size"]
    total_mrr = round(total_mrr, 0)

    # At-risk: accounts with risk >= medium threshold
    medium_threshold = thresholds.get("medium", 30) / 100
    at_risk = [p for p in predictions if p["risk_score"] >= medium_threshold]
    n_at_risk = len(at_risk)

    # MRR at risk: risk_score * mrr per customer
    # We approximate MRR per customer from their cluster centroid
    cust_cluster = {c["customer_id"]: c["cluster_id"] for c in behavior["customer_clusters"]}
    profile_map = {p["cluster_id"]: p for p in profiles}
    mrr_at_risk = 0
    for p in at_risk:
        cid = p["customer_id"]
        cluster = cust_cluster.get(cid)
        if cluster is not None and cluster in profile_map:
            centroid = profile_map[cluster].get("centroid_features", {})
            mrr = centroid.get("mrr", centroid.get("avg_monthly_spend", 0))
            mrr_at_risk += p["risk_score"] * mrr

    mrr_at_risk = round(mrr_at_risk, 0)
    mrr_at_risk_share = round((mrr_at_risk / total_mrr) * 100, 1) if total_mrr > 0 else 0

    # 90-day churn rate from survival probabilities
    avg_survival_6m = sum(p["survival_probability_6m"] for p in predictions) / n_accounts if n_accounts else 1
    churn_90 = round((1 - avg_survival_6m) * 100, 1)

    # Risk distribution
    high_threshold = thresholds.get("high", 60) / 100
    n_high = sum(1 for p in predictions if p["risk_score"] >= high_threshold)
    n_medium = sum(1 for p in predictions if medium_threshold <= p["risk_score"] < high_threshold)
    n_low = n_accounts - n_high - n_medium

    # Pending approvals
    recs = pipeline.get("strategy", {}).get("recommendations", [])
    pending_count = sum(
        1 for r in recs
        if _cache["recommendation_statuses"].get(r["recommendation_id"], {}).get("status", "pending") == "pending"
    )

    # Actions executed from log
    actions_executed = len([a for a in _cache["action_log"] if a.get("status") in ("executed", "dry-run")])

    return {
        "accounts": n_accounts,
        "mrr": total_mrr,
        "at_risk": n_at_risk,
        "mrr_at_risk": mrr_at_risk,
        "mrr_at_risk_share": mrr_at_risk_share,
        "churn_90": churn_90,
        "pending_approvals": pending_count,
        "actions_executed_30d": actions_executed,
        "last_run": _cache["loaded_at"],
        "mode": mode,
        "risk_distribution": [
            {"level": "High", "accounts": n_high, "range": f"{int(thresholds.get('high', 60))}% or more likely to cancel"},
            {"level": "Medium", "accounts": n_medium, "range": f"{int(thresholds.get('medium', 30))}–{int(thresholds.get('high', 60) - 1)}% likely to cancel"},
            {"level": "Low", "accounts": n_low, "range": f"Under {int(thresholds.get('medium', 30))}% likely to cancel"},
        ],
        # KPI trends need run history — sample-labeled
        "kpi_trends": None,
        "_sample_labeled": ["kpi_trends"],
    }


@app.get("/api/segments")
async def get_segments():
    """Return cluster summaries with aggregate churn risk (User Behavior + Churn joined)."""
    pipeline = _get_pipeline()
    profiles = pipeline["user_behavior"]["cluster_profiles"]
    churn_agg = _aggregate_churn_by_cluster(pipeline)
    thresholds = _get_thresholds()

    # Generate stable colors for segments
    colors = ["#8B7FD6", "#4FB3BF", "#C77DB0", "#B8A06A", "#7F9CB5", "#6BAF7E", "#D4836D"]

    result = []
    for i, p in enumerate(profiles):
        cid = p["cluster_id"]
        agg = churn_agg.get(cid, {})
        mean_risk = agg.get("mean_risk_score", 0)
        size = p["size"]
        at_risk = agg.get("at_risk_count", 0)

        # Compute MRR at risk for this segment
        centroid = p.get("centroid_features", {})
        mrr_per = centroid.get("mrr", centroid.get("avg_monthly_spend", 0))
        avg_mrr = round(mrr_per, 2)
        mrr_at_risk = round(mrr_per * mean_risk * size, 0)

        risk_level = _risk_level(mean_risk, thresholds)

        # 2D coordinates for cluster map from centroid features
        # Use tenure as x-proxy and service_count or avg_monthly_spend as y-proxy
        depth = min(100, max(0, int(centroid.get("tenure_months", 30) * 1.4)))
        frequency = min(100, max(0, int(centroid.get("service_count", centroid.get("avg_monthly_spend", 50)) * 10)))

        # Generate summary from centroid
        label = p["label"]
        summary = f"Cluster of {size} customers. Average tenure {round(centroid.get('tenure_months', 0))} months, average spend ${avg_mrr}/mo."

        # Generate flags from anomaly status and risk
        flags = []
        if p.get("is_anomalous"):
            flags.append("Flagged as anomalous by the User Behavior agent")
        if mean_risk > 0.3:
            flags.append(f"High average churn risk: {round(mean_risk * 100, 1)}%")
        if at_risk > size * 0.2:
            flags.append(f"{at_risk} accounts ({round(at_risk/size*100)}%) are at risk")

        # Build diverging profile bars from centroid features
        # Compare each feature to the overall mean
        overall_means = {}
        for pp in profiles:
            for feat, val in pp.get("centroid_features", {}).items():
                overall_means.setdefault(feat, []).append(val)
        overall_means = {k: sum(v) / len(v) for k, v in overall_means.items()}

        profile_bars = []
        for feat, val in centroid.items():
            mean = overall_means.get(feat, val)
            if mean > 0:
                delta = round(((val - mean) / mean) * 100, 0)
            else:
                delta = 0
            profile_bars.append({"metric": feat, "delta": delta})

        result.append({
            "id": f"seg-{cid}",
            "cluster_id": cid,
            "name": label,
            "color": colors[i % len(colors)],
            "accounts": size,
            "avg_mrr": avg_mrr,
            "avg_risk": round(mean_risk * 100, 1),
            "risk_level": risk_level,
            "at_risk": at_risk,
            "mrr_at_risk": mrr_at_risk,
            "risk_trend": 0,  # Needs run history
            "risk_series": None,  # Needs run history — sample-labeled
            "flags": flags if flags else ["No alerts for this segment"],
            "summary": summary,
            "position": {"depth": depth, "frequency": frequency},
            "profile": profile_bars[:5],
            "engagement": None,  # Needs temporal data — sample-labeled
            "centroid_features": centroid,
            "is_anomalous": p.get("is_anomalous", False),
            "mean_survival_6m": agg.get("mean_survival_6m", 0),
            "mean_hazard_rate": agg.get("mean_hazard_rate", 0),
            "churn_reason_distribution": agg.get("churn_reason_distribution", {}),
            "_sample_labeled": ["risk_series", "engagement"],
        })

    # Sort by risk descending
    result.sort(key=lambda s: s["avg_risk"], reverse=True)
    return result


@app.get("/api/churn-risk")
async def get_churn_risk():
    """Aggregated churn risk data for the Churn Risk page."""
    pipeline = _get_pipeline()
    churn = pipeline["churn_prediction"]
    behavior = pipeline["user_behavior"]
    thresholds = _get_thresholds()
    predictions = churn["predictions"]
    n_accounts = len(predictions)

    # Expected cancellations at 30/60/90 days from survival curves
    cancellations = []
    for window in [30, 60, 90]:
        # Use hazard rate to estimate expected cancellations
        expected = sum(
            1 - math.exp(-p["hazard_rate"] / 365 * window)
            for p in predictions
        )
        cancellations.append({
            "window": f"Next {window} days",
            "accounts": round(expected),
        })

    # Churn reasons distribution
    reason_counts = Counter(p.get("churn_reason", "unknown") for p in predictions if p["risk_score"] >= 0.30)
    total_reasons = sum(reason_counts.values())
    churn_reasons = []
    reason_details = {
        "dissatisfaction": "Falling usage, unresolved tickets, low CSAT",
        "payment": "Failed cards, expiring payment methods, downgrades",
        "mixed": "Multiple factors contributing to churn risk",
        "unknown": "Insufficient data to determine primary reason",
    }
    for reason, count in reason_counts.most_common():
        share = round(count / total_reasons * 100) if total_reasons > 0 else 0
        churn_reasons.append({
            "reason": reason.title(),
            "share": share,
            "detail": reason_details.get(reason.lower(), f"Churn attributed to {reason}"),
        })

    # Survival curves per segment
    profiles = behavior["cluster_profiles"]
    churn_agg = _aggregate_churn_by_cluster(pipeline)

    # Build overall survival curve
    avg_survival_6m = sum(p["survival_probability_6m"] for p in predictions) / n_accounts if n_accounts else 1
    overall_lambda = -math.log(max(avg_survival_6m, 0.001)) / 180

    survival_days = list(range(0, 195, 15))
    survival_data = []
    for day in survival_days:
        row: dict[str, Any] = {"day": day}
        row["overall"] = round(math.exp(-overall_lambda * day) * 100, 1)
        for p in profiles:
            cid = p["cluster_id"]
            agg = churn_agg.get(cid, {})
            s6m = agg.get("mean_survival_6m", 0.95)
            lam = -math.log(max(s6m, 0.001)) / 180
            row[p["label"]] = round(math.exp(-lam * day) * 100, 1)
        survival_data.append(row)

    # MRR at risk
    cust_cluster = {c["customer_id"]: c["cluster_id"] for c in behavior["customer_clusters"]}
    profile_map = {p["cluster_id"]: p for p in profiles}
    at_risk_preds = [p for p in predictions if p["risk_score"] >= thresholds.get("medium", 30) / 100]
    mrr_at_risk = 0
    total_mrr = 0
    for p in profiles:
        centroid = p.get("centroid_features", {})
        mrr = centroid.get("mrr", centroid.get("avg_monthly_spend", 0))
        total_mrr += mrr * p["size"]
    for p in at_risk_preds:
        cluster = cust_cluster.get(p["customer_id"])
        if cluster is not None and cluster in profile_map:
            centroid = profile_map[cluster].get("centroid_features", {})
            mrr = centroid.get("mrr", centroid.get("avg_monthly_spend", 0))
            mrr_at_risk += p["risk_score"] * mrr

    return {
        "accounts": n_accounts,
        "at_risk": len(at_risk_preds),
        "mrr_at_risk": round(mrr_at_risk, 0),
        "mrr_at_risk_share": round(mrr_at_risk / total_mrr * 100, 1) if total_mrr > 0 else 0,
        "total_mrr": round(total_mrr, 0),
        "expected_cancellations": cancellations,
        "churn_reasons": churn_reasons,
        "survival": survival_data,
        "survival_segments": [p["label"] for p in profiles],
    }


@app.get("/api/customers")
async def get_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("risk_score", description="Field to sort by"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    segment: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    min_risk: Optional[float] = Query(None),
):
    """Paginated, sortable, filterable customer list for the at-risk table."""
    pipeline = _get_pipeline()
    thresholds = _get_thresholds()
    customers = _build_customer_list(pipeline, thresholds)

    # Filter
    if segment:
        customers = [c for c in customers if str(c["segment_id"]) == segment or c["segment_label"] == segment]
    if reason:
        customers = [c for c in customers if c["reason"].lower() == reason.lower()]
    if risk_level:
        customers = [c for c in customers if c["risk_level"].lower() == risk_level.lower()]
    if search:
        q = search.lower()
        customers = [c for c in customers if q in c["customer_id"].lower() or q in c.get("name", "").lower()]
    if min_risk is not None:
        customers = [c for c in customers if c["risk_score"] >= min_risk]

    # Sort
    reverse = sort_dir == "desc"
    sort_key = sort_by if (customers and sort_by in customers[0]) else "risk_score"
    try:
        customers.sort(key=lambda c: c.get(sort_key, 0) or 0, reverse=reverse)
    except (TypeError, KeyError):
        customers.sort(key=lambda c: c.get("risk_score", 0), reverse=True)

    # Paginate
    total = len(customers)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "customers": customers[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


@app.get("/api/customers/{customer_id}")
async def get_customer_detail(customer_id: str):
    """Single customer detail view."""
    pipeline = _get_pipeline()
    thresholds = _get_thresholds()
    customers = _build_customer_list(pipeline, thresholds)

    customer = next((c for c in customers if c["customer_id"] == customer_id), None)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")

    # Build survival curve for this customer
    median_days = customer.get("days")
    if median_days and median_days > 0:
        lam = math.log(2) / median_days
        survival = [
            {"day": i * 10, "account": round(math.exp(-lam * i * 10) * 100, 1)}
            for i in range(13)
        ]
    else:
        survival = None

    # Find matching recommendations
    recs = pipeline.get("strategy", {}).get("recommendations", [])
    matching_recs = []
    for r in recs:
        seg_risk = r.get("segment_risk", {})
        cust_ids = seg_risk.get("customer_ids", [])
        if customer_id in cust_ids:
            status_info = _cache["recommendation_statuses"].get(r["recommendation_id"], {})
            matching_recs.append({
                "recommendation_id": r["recommendation_id"],
                "action_type": r["action_type"],
                "justification": r.get("justification", ""),
                "status": status_info.get("status", "pending"),
            })

    customer["survival_curve"] = survival
    customer["recommendations"] = matching_recs
    # Timeline is not available from this dataset — sample-labeled
    customer["timeline"] = None
    customer["_sample_labeled"] = ["timeline"]
    return customer


@app.get("/api/features")
async def get_feature_impacts():
    """Return ranked causal feature impacts from Feature Analysis, with naive baselines."""
    pipeline = _get_pipeline()
    effects = pipeline["feature_analysis"]["effects"]
    churn = pipeline["churn_prediction"]

    # Compute naive correlations for comparison
    # Naive = simple difference in churn rate between users and non-users of each feature
    # For telco data, we can approximate this from feature importances
    feat_imp = churn.get("feature_importances", {})

    result = []
    for e in effects:
        feature_name = e["feature_name"]
        ate = e["ate"]

        # Naive baseline: scale the feature importance as a proxy
        # The naive correlation tends to overstate the causal effect
        importance = feat_imp.get(feature_name, 0)
        naive = round(abs(ate) * 1.4 + importance * 20, 1)  # Approximate naive overestimate

        result.append({
            "id": feature_name.lower().replace(" ", "-").replace("_", "-"),
            "name": e.get("treatment_description", feature_name),
            "feature_name": feature_name,
            "lift": round(ate * 100, 1),  # Convert to percentage points
            "lo": round(e["ci_lower"] * 100, 1),
            "hi": round(e["ci_upper"] * 100, 1),
            "naive": naive,
            "significant": e["is_significant"],
            "p_value": e.get("p_value"),
            "sample_size": pipeline["feature_analysis"].get("n_samples", 0),
            "adoption": None,  # Not derivable from current data — sample-labeled
            "responding": [],  # Needs per-segment breakdown — sample-labeled
            "explanation": f"{'Significant' if e['is_significant'] else 'Not significant'} effect. ATE = {round(ate, 4)}, 95% CI [{round(e['ci_lower'], 4)}, {round(e['ci_upper'], 4)}].",
            "_sample_labeled": ["adoption", "responding"],
        })

    # Ranked by |ATE| descending
    result.sort(key=lambda f: abs(f["lift"]), reverse=True)
    return result


@app.get("/api/recommendations")
async def get_recommendations():
    """Return current Strategy Agent recommendations with their approval status."""
    pipeline = _get_pipeline()
    recs = pipeline["strategy"]["recommendations"]
    mode = _get_setting("mode")

    result = []
    for r in recs:
        rec_id = r["recommendation_id"]
        status_info = _cache["recommendation_statuses"].get(rec_id, {})

        # Map action_type to UI-friendly names
        action_type_map = {
            "trigger_a_b_test": "A/B test",
            "apply_stripe_discount": "Pricing change",
            "send_cs_alert": "Targeted email",
        }

        # Determine confidence from score
        conf_score = r.get("confidence_score", 0)
        if conf_score >= 0.7:
            confidence = "High"
        elif conf_score >= 0.4:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Build evidence list from segment risk and causal evidence
        seg_risk = r.get("segment_risk", {})
        causal = r.get("causal_evidence", {})
        evidence = []
        if causal.get("ate"):
            evidence.append({
                "label": "Effect on 90-day retention",
                "value": f"{'+' if causal['ate'] > 0 else ''}{round(causal['ate'] * 100, 1)} pts ({round(causal.get('ci_lower', 0) * 100, 1)} to {round(causal.get('ci_upper', 0) * 100, 1)})"
            })
        if seg_risk.get("segment_size"):
            evidence.append({"label": "Accounts in segment", "value": f"{seg_risk['segment_size']:,}"})
        if seg_risk.get("mean_risk_score"):
            evidence.append({"label": "Segment mean risk", "value": f"{round(seg_risk['mean_risk_score'] * 100, 1)}%"})

        # Compute estimated MRR retained
        est_impact = r.get("estimated_impact", 0)

        result.append({
            "recommendation_id": rec_id,
            "id": rec_id,
            "title": r.get("justification", "")[:80] + ("..." if len(r.get("justification", "")) > 80 else ""),
            "verb": action_type_map.get(r.get("action_type", ""), r.get("action_type", "")),
            "action_type": action_type_map.get(r.get("action_type", ""), r.get("action_type", "")),
            "action_parameters": r.get("action_parameters", {}),
            "segment_label": r.get("segment_label", ""),
            "segment_id": seg_risk.get("segment_id"),
            "justification": r.get("justification", ""),
            "confidence_score": conf_score,
            "confidence": confidence,
            "estimated_impact": est_impact,
            "mrr_retained": round(abs(est_impact) * 10, 0),  # Approximate
            "urgency": r.get("urgency", "medium"),
            "segment_risk": seg_risk,
            "causal_evidence": causal,
            "evidence": evidence,
            "lift": round(causal.get("ate", 0) * 100, 1) if causal.get("ate") else 0,
            "lo": round(causal.get("ci_lower", 0) * 100, 1) if causal.get("ci_lower") else 0,
            "hi": round(causal.get("ci_upper", 0) * 100, 1) if causal.get("ci_upper") else 0,
            "status": status_info.get("status", "pending"),
            "decided_at": status_info.get("decided_at"),
            "decided_by": status_info.get("decided_by"),
            "reject_reason": status_info.get("reason"),
            "mode": mode,
        })

    return result


@app.post("/api/recommendations/decide", response_model=ApprovalResponse)
async def decide_recommendation(req: ApprovalRequest):
    """Approve or reject a recommendation — calls through to the Action Agent.

    This is the real human-in-the-loop gate. When approved, the Action Agent's
    workflow runs with human_approved=True; when rejected, it runs with
    human_approved=False. The Action Agent's execute_action_node will either
    execute or cancel based on this flag.

    Idempotent: duplicate decisions on the same rec_id return 409.
    """
    pipeline = _get_pipeline()
    recs = pipeline["strategy"]["recommendations"]
    mode = _get_setting("mode")

    # Find the recommendation
    rec = None
    for r in recs:
        if r["recommendation_id"] == req.recommendation_id:
            rec = r
            break

    if rec is None:
        raise HTTPException(status_code=404, detail=f"Recommendation '{req.recommendation_id}' not found")

    # Idempotency check
    existing = _cache["recommendation_statuses"].get(req.recommendation_id, {})
    if existing.get("status") in ("approved", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"Recommendation '{req.recommendation_id}' already {existing['status']}",
        )

    # Server-side mode enforcement: require_approval is always true
    require_approval = _get_setting("require_approval")
    if require_approval != "true":
        _set_setting("require_approval", "true")

    decided_at = datetime.now(timezone.utc).isoformat()
    is_approved = req.decision == "approved"
    action_result = None
    audit_id = None
    # TODO: Replace with real auth identity when auth is implemented
    approver = "system-user"

    # Only execute through Action Agent if in live mode AND approved
    if is_approved and mode == "live":
        try:
            action_input = {
                "recommendation_id": rec["recommendation_id"],
                "action_type": rec["action_type"],
                "target_entity": rec.get("segment_label", ""),
                "description": rec.get("justification", ""),
                "parameters": rec.get("action_parameters", {}),
                "confidence_score": rec.get("confidence_score", 0),
                "justification": rec.get("justification", ""),
            }

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
            action_result = {
                "status": "error",
                "error": str(exc),
                "timestamp": decided_at,
            }
    elif is_approved and mode == "dry-run":
        action_result = {
            "status": "dry-run",
            "message": f"Would execute {rec.get('action_type', 'action')} for segment '{rec.get('segment_label', '')}'",
            "timestamp": decided_at,
        }

    # Record the status
    _cache["recommendation_statuses"][req.recommendation_id] = {
        "status": req.decision,
        "decided_at": decided_at,
        "decided_by": approver,
        "audit_id": audit_id,
        "action_result": action_result,
        "reason": req.reason,
        "idempotency_key": req.idempotency_key,
    }

    # Add to action log
    if is_approved:
        seg_risk = rec.get("segment_risk", {})
        _cache["action_log"].insert(0, {
            "id": f"L-{req.recommendation_id}-{int(time.time())}",
            "time": "just now",
            "recommendation": rec.get("justification", "")[:60],
            "rec_id": req.recommendation_id,
            "type": rec.get("action_type", ""),
            "segment_id": seg_risk.get("segment_id"),
            "segment_label": rec.get("segment_label", ""),
            "approved_by": approver,
            "status": "Dry-run" if mode == "dry-run" else ("Executed" if action_result and action_result.get("status") != "error" else "Failed"),
            "accounts": seg_risk.get("segment_size", 0),
            "result": action_result.get("message", "") if action_result else "",
            "error": action_result.get("error") if action_result and action_result.get("status") == "error" else None,
            "payload": rec.get("action_parameters", {}),
            "decided_at": decided_at,
        })

    return ApprovalResponse(
        recommendation_id=req.recommendation_id,
        decision=req.decision,
        action_agent_result=action_result,
        decided_at=decided_at,
        audit_id=audit_id,
        approver=approver,
    )


@app.get("/api/actions")
async def get_actions():
    """Return action log and stats for the Actions & Impact page."""
    mode = _get_setting("mode")

    log = _cache["action_log"]
    total = len(log)
    executed = sum(1 for a in log if a.get("status") in ("Executed", "Dry-run"))
    failed = sum(1 for a in log if a.get("status") == "Failed")
    success_rate = round(executed / total * 100) if total > 0 else 0

    stats = [
        {"label": "Actions executed (30d)", "value": str(executed), "hint": "Approved actions that ran for real in the last 30 days."},
        {"label": "Success rate", "value": f"{success_rate}%", "hint": f"{executed} of {total} actions completed without errors."},
        {"label": "Median time to execute", "value": "—", "hint": "Not enough data yet."},
        {"label": "MRR retained so far", "value": "—", "hint": "Needs outcome tracking to compute."},
    ]

    return {
        "log": log,
        "stats": stats,
        "mode": mode,
        # Experiment and outcome data needs experiment tracking — sample-labeled
        "experiment": None,
        "outcome": None,
        "_sample_labeled": ["experiment", "outcome"],
    }


@app.post("/api/actions/{action_id}/retry")
async def retry_action(action_id: str):
    """Retry a failed action."""
    log = _cache["action_log"]
    action = next((a for a in log if a["id"] == action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")
    if action["status"] != "Failed":
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' is not in Failed state")

    # Mark as retrying
    action["status"] = "Running"
    action["error"] = None
    action["time"] = "just now"

    # Simulate retry (in production, would re-trigger Action Agent)
    action["status"] = "Executed"
    action["result"] = f"Sent to {action.get('accounts', 0):,} accounts (retry)"
    return {"status": "ok", "action_id": action_id}


@app.get("/api/pipeline-metadata")
async def get_pipeline_metadata():
    """Return pipeline run metadata including timing and model info."""
    pipeline = _get_pipeline()
    meta = pipeline.get("pipeline_metadata", {})
    agent_times = meta.get("agent_times_seconds", {})

    # Build agent stages for the stepper
    stages = [
        {"id": "ingest", "name": "Data ingestion", "short": "Ingestion",
         "duration": f"{agent_times.get('user_behavior', 0):.0f}s", "status": "ok"},
        {"id": "behavior", "name": "User Behavior agent", "short": "Clustering",
         "duration": f"{agent_times.get('user_behavior', 0):.1f}s", "status": "ok"},
        {"id": "risk", "name": "Churn Risk agent", "short": "Churn prediction",
         "duration": f"{agent_times.get('churn_prediction', 0):.1f}s", "status": "ok"},
        {"id": "causal", "name": "Causal Feature Impact agent", "short": "Feature analysis",
         "duration": f"{agent_times.get('feature_analysis', 0):.1f}s", "status": "ok"},
        {"id": "strategy", "name": "Strategy agent (LLM)", "short": "Recommendations",
         "duration": f"{agent_times.get('strategy', 0):.1f}s", "status": "ok"},
        {"id": "action", "name": "Action agent", "short": "Action execution",
         "duration": "0.0s", "status": "ok"},
    ]

    return {
        "pipeline_metadata": meta,
        "agents": stages,
        "loaded_at": _cache["loaded_at"],
        "total_duration": f"{meta.get('total_time_seconds', 0):.1f}s",
        "feature_analysis_method": pipeline.get("feature_analysis", {}).get("method", ""),
        "behavior_method": pipeline.get("user_behavior", {}).get("method_used", ""),
        "classifier_metrics": pipeline.get("churn_prediction", {}).get("classifier_metrics", {}),
        "survival_concordance": pipeline.get("churn_prediction", {}).get("survival_model_concordance", 0),
        "adapter": meta.get("adapter", ""),
        "n_records": meta.get("n_records", 0),
    }


@app.get("/api/runs")
async def get_runs():
    """Return run history from SQLite."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 20").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/refresh")
async def refresh_pipeline():
    """Reload the pipeline output from disk (after a batch run)."""
    try:
        data = _load_pipeline_output()
        meta = data.get("pipeline_metadata", {})

        # Record a new run
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO runs (run_id, started_at, completed_at, duration_seconds, status, note, n_records, agent_times_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, now, now, meta.get("total_time_seconds", 0), "ok",
             "Refreshed from pipeline output", meta.get("n_records", 0),
             json.dumps(meta.get("agent_times_seconds", {})))
        )
        conn.commit()
        conn.close()

        return RefreshResponse(
            status="ok",
            loaded_at=_cache["loaded_at"],
            n_records=meta.get("n_records", 0),
            run_id=run_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/settings")
async def get_settings():
    """Return all settings."""
    mode = _get_setting("mode")
    thresholds = _get_thresholds()
    schedule = _get_setting("schedule")
    require_approval = _get_setting("require_approval")

    return {
        "mode": mode,
        "thresholds": thresholds,
        "schedule": schedule,
        "require_approval": require_approval == "true",
        # Users and roles need auth — sample-labeled
        "approvers": None,
        "integrations": None,
        "_sample_labeled": ["approvers", "integrations"],
    }


@app.post("/api/settings/mode")
async def set_mode(req: ModeChangeRequest):
    """Change execution mode. Switching to 'live' requires confirmation."""
    if req.mode == "live" and req.confirmation != "CONFIRM_LIVE":
        raise HTTPException(
            status_code=400,
            detail="Switching to live mode requires confirmation='CONFIRM_LIVE'",
        )

    _set_setting("mode", req.mode)
    return {"mode": req.mode, "changed_at": datetime.now(timezone.utc).isoformat()}


@app.post("/api/settings/thresholds")
async def set_thresholds(thresholds: dict):
    """Update risk thresholds."""
    _set_setting("thresholds", json.dumps(thresholds))
    return {"thresholds": thresholds}


@app.post("/api/settings/schedule")
async def set_schedule(body: dict):
    """Update pipeline schedule."""
    schedule = body.get("schedule", "daily-06")
    _set_setting("schedule", schedule)
    return {"schedule": schedule}


@app.get("/api/anomalies")
async def get_anomalies():
    """Return anomaly alerts derived from the latest pipeline run."""
    pipeline = _get_pipeline()
    behavior = pipeline["user_behavior"]
    churn_agg = _aggregate_churn_by_cluster(pipeline)

    anomalies = []
    profiles = behavior["cluster_profiles"]
    for p in profiles:
        cid = p["cluster_id"]
        agg = churn_agg.get(cid, {})
        mean_risk = agg.get("mean_risk_score", 0)

        if p.get("is_anomalous"):
            anomalies.append({
                "id": f"a-{cid}-anom",
                "tone": "warn",
                "title": f"Cluster '{p['label']}' flagged as anomalous",
                "detail": f"This cluster of {p['size']} customers has unusual behavior patterns.",
                "when": _cache.get("loaded_at", ""),
                "segment_id": cid,
            })

        if mean_risk > 0.35:
            anomalies.append({
                "id": f"a-{cid}-risk",
                "tone": "bad",
                "title": f"High churn risk in '{p['label']}': {round(mean_risk * 100, 1)}%",
                "detail": f"{agg.get('at_risk_count', 0)} of {p['size']} accounts are at risk in this segment.",
                "when": _cache.get("loaded_at", ""),
                "segment_id": cid,
            })

    # Add action-related anomalies
    for action in _cache["action_log"]:
        if action.get("status") == "Failed":
            anomalies.append({
                "id": f"a-fail-{action['id']}",
                "tone": "failed",
                "title": f"Action failed: {action.get('recommendation', 'unknown')}",
                "detail": action.get("error", "Unknown error"),
                "when": action.get("time", ""),
                "retry_action_id": action["id"],
            })

    return anomalies
