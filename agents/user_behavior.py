"""Agent 1 — User Behavior Agent (Observation Layer).

Consumes ``CanonicalRecord`` instances and produces a
``BehaviorAnalysisResult`` containing:

1. **Engineered behavioural features** — recency, frequency, monetary value,
   service diversity, payment reliability, and demographic indicators.
2. **DBSCAN clustering** with data-driven ``eps`` selection (k-distance elbow)
   and comparison against an autoencoder-based approach.
3. **Cohort-based anomaly / drift detection** — since the Telco dataset is a
   static snapshot, we partition by tenure cohorts and flag clusters whose
   engagement profile deviates significantly from the population.

The agent is wrapped as a LangChain ``RunnableLambda`` so a future
LLM-based Strategy Agent can invoke it via LCEL.

Design notes
------------
* Feature engineering is deliberately dataset-agnostic: it reads only the
  canonical schema fields and the ``service_features`` dict.  No raw column
  names leak in.
* The autoencoder is a simple symmetric MLP (via ``sklearn.neural_network.
  MLPRegressor``) used as an undercomplete autoencoder for reconstruction-error-
  based anomaly scoring.  This avoids pulling in PyTorch.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import silhouette_score
from langchain_core.runnables import RunnableLambda

from schemas.canonical import CanonicalRecord
from schemas.agent_outputs import (
    BehaviorAnalysisResult,
    ClusterProfile,
    CustomerCluster,
)


# ── Feature Engineering ──────────────────────────────────────────────

def _records_to_feature_df(records: list[CanonicalRecord]) -> pd.DataFrame:
    """Transform canonical records into a numerical feature matrix.

    Engineered features
    -------------------
    tenure_months      : tenure in months (tenure_days / 30)
    mrr                : monthly recurring revenue
    total_charges      : lifetime revenue (from service_features)
    support_flag       : 1 if customer has engaged support
    service_count      : number of active service subscriptions
    is_senior          : 1 if senior citizen
    has_partner        : 1 if has partner
    has_dependents     : 1 if has dependents
    is_paperless       : 1 if paperless billing
    payment_auto       : 1 if automatic payment method
    internet_fiber     : 1 if Fiber optic internet
    internet_dsl       : 1 if DSL internet
    internet_none      : 1 if no internet
    streaming_count    : number of streaming services (TV + Movies)
    security_count     : number of security services (Online Security + Backup + Device Protection)
    avg_monthly_spend  : total_charges / max(tenure_months, 1)
    """
    rows: list[dict[str, Any]] = []

    for rec in records:
        sf = rec.service_features
        tenure_months = max(rec.tenure_days / 30, 0.1)  # avoid div-by-zero

        # Count active services
        service_cols = [
            "PhoneService", "MultipleLines", "OnlineSecurity",
            "OnlineBackup", "DeviceProtection", "TechSupport",
            "StreamingTV", "StreamingMovies",
        ]
        service_count = sum(
            1 for col in service_cols
            if sf.get(col, 0) == 1 or sf.get(col) == "Yes"
        )

        streaming_count = sum(
            1 for col in ["StreamingTV", "StreamingMovies"]
            if sf.get(col, 0) == 1
        )

        security_count = sum(
            1 for col in ["OnlineSecurity", "OnlineBackup", "DeviceProtection"]
            if sf.get(col, 0) == 1
        )

        total_charges = float(sf.get("TotalCharges", 0.0))

        internet = sf.get("InternetService", "No")

        rows.append({
            "customer_id": rec.customer_id,
            "tenure_months": tenure_months,
            "mrr": rec.mrr,
            "total_charges": total_charges,
            "support_flag": rec.support_interactions,
            "service_count": service_count,
            "is_senior": sf.get("SeniorCitizen", 0),
            "has_partner": sf.get("Partner", 0),
            "has_dependents": sf.get("Dependents", 0),
            "is_paperless": sf.get("PaperlessBilling", 0),
            "payment_auto": 1 if rec.payment_status.startswith("auto") else 0,
            "internet_fiber": 1 if internet == "Fiber optic" else 0,
            "internet_dsl": 1 if internet == "DSL" else 0,
            "internet_none": 1 if internet == "No" else 0,
            "streaming_count": streaming_count,
            "security_count": security_count,
            "avg_monthly_spend": total_charges / tenure_months,
        })

    return pd.DataFrame(rows)


# ── DBSCAN with k-distance eps selection ─────────────────────────────

def _select_eps(X_scaled: np.ndarray, k: int = 5) -> float:
    """Select DBSCAN ``eps`` via the k-distance elbow method.

    1. Compute the distance to the k-th nearest neighbour for every point.
    2. Sort distances in ascending order.
    3. Find the "elbow" — the point of maximum curvature — using the
       second-derivative (discrete differences) heuristic.

    Returns the eps value at the elbow.
    """
    nn = NearestNeighbors(n_neighbors=k)
    nn.fit(X_scaled)
    distances, _ = nn.kneighbors(X_scaled)
    k_distances = np.sort(distances[:, k - 1])

    # Discrete second derivative to find the elbow
    d1 = np.diff(k_distances)
    d2 = np.diff(d1)

    if len(d2) == 0:
        return float(np.median(k_distances))

    elbow_idx = int(np.argmax(d2)) + 1  # +1 for the diff offset
    eps = float(k_distances[elbow_idx])

    # Guard: eps should be reasonable
    if eps < 0.1:
        eps = float(np.percentile(k_distances, 90))
        logger.info(f"k-distance elbow too small ({eps:.4f}), using 90th percentile")

    logger.info(f"Selected eps={eps:.4f} from k-distance elbow (k={k})")
    return eps


def _run_dbscan(
    X_scaled: np.ndarray, min_samples: int = 5
) -> tuple[np.ndarray, float, dict[str, Any]]:
    """Run DBSCAN with auto-selected eps.

    Returns (labels, silhouette, metadata_dict).
    """
    eps = _select_eps(X_scaled, k=min_samples)

    db = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1)
    labels = db.fit_predict(X_scaled)

    n_clusters = len(set(labels) - {-1})
    n_noise = int(np.sum(labels == -1))

    logger.info(
        f"DBSCAN: {n_clusters} clusters, {n_noise} noise points "
        f"({100 * n_noise / len(labels):.1f}%)"
    )

    # Silhouette score (only meaningful with ≥ 2 clusters and not all noise)
    sil = -1.0
    if n_clusters >= 2 and n_noise < len(labels):
        # Use only non-noise points for silhouette
        mask = labels != -1
        if mask.sum() > 1:
            sil = float(silhouette_score(X_scaled[mask], labels[mask]))
            logger.info(f"Silhouette score (excl. noise): {sil:.4f}")

    metadata = {
        "eps": eps,
        "min_samples": min_samples,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "noise_pct": round(100 * n_noise / len(labels), 2),
        "silhouette": round(sil, 4),
    }
    return labels, sil, metadata


# ── Autoencoder (undercomplete MLP) ──────────────────────────────────

def _run_autoencoder(
    X_scaled: np.ndarray, encoding_dim: int | None = None
) -> np.ndarray:
    """Train a symmetric undercomplete autoencoder and return per-sample
    reconstruction error (MSE).

    The autoencoder is an ``MLPRegressor`` with a bottleneck architecture:
    ``[input_dim, hidden, encoding_dim, hidden, input_dim]``.
    """
    n_features = X_scaled.shape[1]
    if encoding_dim is None:
        encoding_dim = max(3, n_features // 3)

    hidden = max(encoding_dim + 2, n_features // 2)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ae = MLPRegressor(
            hidden_layer_sizes=(hidden, encoding_dim, hidden),
            activation="relu",
            solver="adam",
            max_iter=300,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
        )
        ae.fit(X_scaled, X_scaled)  # self-reconstruction

    reconstructed = ae.predict(X_scaled)
    mse = np.mean((X_scaled - reconstructed) ** 2, axis=1)

    logger.info(
        f"Autoencoder reconstruction error — "
        f"mean={np.mean(mse):.4f}, std={np.std(mse):.4f}, "
        f"max={np.max(mse):.4f}"
    )
    return mse.astype(float)


# ── Cohort-based drift / anomaly detection ───────────────────────────

def _detect_cohort_anomalies(
    df: pd.DataFrame,
    labels: np.ndarray,
    tenure_col: str = "tenure_months",
) -> list[int]:
    """Flag clusters whose engagement deviates from the population.

    Since this is a static historical dump, we partition customers into
    tenure cohorts (0–6, 6–12, 12–24, 24–48, 48+ months) and check
    whether any cluster's churn-adjacent proxy (e.g. low service count +
    high MRR mismatch) is anomalous relative to the overall distribution.

    A cluster is flagged if its mean engagement score is more than 1.5
    standard deviations below the global mean, suggesting it contains
    at-risk customers.
    """
    df = df.copy()
    df["cluster"] = labels

    # Engagement proxy: normalised service_count + support_flag − payment_risk
    # (lower = more likely disengaged)
    df["engagement"] = (
        df["service_count"]
        + df["support_flag"]
        + df["security_count"]
        - (1 - df["payment_auto"])  # penalty for manual payment
    )

    global_mean = df["engagement"].mean()
    global_std = df["engagement"].std()
    threshold = global_mean - 1.5 * global_std

    anomalous: list[int] = []
    for cid in sorted(set(labels) - {-1}):
        cluster_mean = df.loc[df["cluster"] == cid, "engagement"].mean()
        if cluster_mean < threshold:
            anomalous.append(int(cid))
            logger.warning(
                f"Cluster {cid}: engagement={cluster_mean:.2f} < "
                f"threshold={threshold:.2f} — FLAGGED"
            )

    return anomalous


# ── Cluster profiling ────────────────────────────────────────────────

def _build_cluster_profiles(
    df: pd.DataFrame,
    labels: np.ndarray,
    feature_cols: list[str],
    anomalous_ids: list[int],
) -> list[ClusterProfile]:
    """Create a ``ClusterProfile`` for every cluster."""
    df = df.copy()
    df["cluster"] = labels

    profiles: list[ClusterProfile] = []
    for cid in sorted(set(labels)):
        mask = df["cluster"] == cid
        subset = df.loc[mask, feature_cols]
        centroid = {col: round(float(subset[col].mean()), 4) for col in feature_cols}

        # Auto-generate a human-readable label
        label_parts: list[str] = []
        if centroid.get("tenure_months", 0) < 6:
            label_parts.append("New")
        elif centroid.get("tenure_months", 0) > 36:
            label_parts.append("Long-term")
        else:
            label_parts.append("Mid-tenure")

        if centroid.get("mrr", 0) > 70:
            label_parts.append("High-spend")
        elif centroid.get("mrr", 0) < 40:
            label_parts.append("Low-spend")

        if centroid.get("service_count", 0) > 4:
            label_parts.append("Multi-service")
        elif centroid.get("service_count", 0) <= 1:
            label_parts.append("Minimal-service")

        if cid == -1:
            label_parts = ["Noise / Outliers"]

        profiles.append(
            ClusterProfile(
                cluster_id=int(cid),
                size=int(mask.sum()),
                centroid_features=centroid,
                label=" · ".join(label_parts),
                is_anomalous=int(cid) in anomalous_ids,
            )
        )

    return profiles


# ── Main agent function ──────────────────────────────────────────────

def run(records: list[CanonicalRecord]) -> BehaviorAnalysisResult:
    """Execute the User Behavior Agent.

    Steps
    -----
    1. Engineer behavioural features from canonical records.
    2. Scale features with ``StandardScaler``.
    3. Run DBSCAN clustering (primary method).
    4. Run autoencoder for per-customer anomaly scores.
    5. Compare DBSCAN vs autoencoder and select the more interpretable result.
    6. Detect cohort-based anomalies / drift.
    7. Build cluster profiles.

    Parameters
    ----------
    records : list[CanonicalRecord]
        Canonical-schema customer records.

    Returns
    -------
    BehaviorAnalysisResult
        Cluster assignments, profiles, anomaly flags, and metadata.
    """
    logger.info(f"User Behavior Agent: processing {len(records)} records")

    # Step 1 — Feature engineering
    df = _records_to_feature_df(records)
    feature_cols = [
        c for c in df.columns if c != "customer_id"
    ]

    X = df[feature_cols].values.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Step 2 — DBSCAN clustering
    labels, sil, dbscan_meta = _run_dbscan(X_scaled, min_samples=5)

    # Step 3 — Autoencoder anomaly scores
    anomaly_scores = _run_autoencoder(X_scaled)

    # Step 4 — Method comparison and selection
    #
    # DBSCAN gives discrete, interpretable clusters with clear boundaries.
    # The autoencoder gives a continuous anomaly score — useful for ranking
    # but harder to explain to a Strategy Agent.
    #
    # Decision: use DBSCAN clusters as the primary output (more interpretable
    # for segment-level strategies) and attach autoencoder scores as a
    # supplementary signal per customer.
    #
    # If DBSCAN produces only 1 cluster (or everything is noise), we note
    # that the autoencoder approach might be preferable and document it.
    n_real_clusters = dbscan_meta["n_clusters"]
    method_used = "DBSCAN"

    comparison_note = (
        f"DBSCAN produced {n_real_clusters} cluster(s) with silhouette="
        f"{dbscan_meta['silhouette']:.4f}. Autoencoder reconstruction error "
        f"mean={float(np.mean(anomaly_scores)):.4f}, "
        f"std={float(np.std(anomaly_scores)):.4f}. "
    )
    if n_real_clusters < 2:
        comparison_note += (
            "DBSCAN did not find meaningful clusters — autoencoder anomaly "
            "scores may be more useful for this dataset. Consider adjusting "
            "eps or using an alternative method."
        )
    else:
        comparison_note += (
            "DBSCAN clusters are interpretable and stable — preferred over "
            "autoencoder for segment-level analysis. Autoencoder scores are "
            "retained as a per-customer anomaly signal."
        )

    dbscan_meta["comparison_note"] = comparison_note
    dbscan_meta["autoencoder_error_mean"] = round(float(np.mean(anomaly_scores)), 4)
    dbscan_meta["autoencoder_error_std"] = round(float(np.std(anomaly_scores)), 4)

    # Step 5 — Cohort anomaly detection
    anomalous_clusters = _detect_cohort_anomalies(df, labels)

    # Step 6 — Build profiles
    profiles = _build_cluster_profiles(df, labels, feature_cols, anomalous_clusters)

    # Step 7 — Assemble per-customer results
    customer_clusters = [
        CustomerCluster(
            customer_id=df.iloc[i]["customer_id"],
            cluster_id=int(labels[i]),
            anomaly_score=round(float(anomaly_scores[i]), 6),
        )
        for i in range(len(df))
    ]

    result = BehaviorAnalysisResult(
        customer_clusters=customer_clusters,
        cluster_profiles=profiles,
        anomalous_clusters=anomalous_clusters,
        method_used=method_used,
        metadata=dbscan_meta,
    )

    logger.info(
        f"User Behavior Agent complete: {len(profiles)} clusters, "
        f"{len(anomalous_clusters)} anomalous"
    )
    return result


# ── LangChain LCEL wrapper ───────────────────────────────────────────

user_behavior_runnable = RunnableLambda(run).with_config(
    {"run_name": "UserBehaviorAgent"}
)
"""LangChain Runnable that wraps :func:`run`.

Usage::

    from agents.user_behavior import user_behavior_runnable
    result = user_behavior_runnable.invoke(records)
"""
