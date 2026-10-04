"""Agent-Testing Dashboard — Streamlit UI.

A standalone inspection tool for running and visualising the three ML agents
(User Behavior, Churn Prediction, Feature Analysis) against canonical-schema
data during development.

Run with:
    streamlit run testing_ui/app.py

This file deliberately does NOT touch or reference any other frontend code in
the repo.  It imports the existing agent ``run()`` functions and adapter
registry directly.
"""

from __future__ import annotations

import sys
import time
import random
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Ensure the project root is importable (so ``agents.*``, ``adapters.*``,
# ``schemas.*`` resolve when Streamlit is launched from any directory).
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Agent Testing Dashboard",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Data loading (cached so re-runs don't re-parse the CSV)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading canonical records …")
def load_all_records() -> list:
    """Load every record via the telco_churn adapter."""
    import adapters  # noqa: delayed import
    load_fn = adapters.get_adapter("telco_churn")
    data_path = _PROJECT_ROOT / "data" / "raw" / "telco_churn.csv"
    return load_fn(data_path)


def get_records(
    all_records: list,
    mode: str,
    n_sample: int = 100,
    customer_id: str | None = None,
) -> list:
    """Subset records according to the chosen selection mode."""
    if mode == "Full dataset":
        return all_records
    elif mode == "Random sample":
        n = min(n_sample, len(all_records))
        return random.sample(all_records, n)
    elif mode == "Single customer":
        matches = [r for r in all_records if r.customer_id == customer_id]
        if not matches:
            st.error(f"Customer ID **{customer_id}** not found in the dataset.")
            st.stop()
        return matches
    return all_records


# ---------------------------------------------------------------------------
# Sidebar — data selection
# ---------------------------------------------------------------------------
st.sidebar.title("🧪 Agent Testing")
st.sidebar.markdown("---")

try:
    all_records = load_all_records()
except Exception as exc:
    st.error(f"**Failed to load data:** {exc}")
    st.stop()

all_customer_ids = sorted({r.customer_id for r in all_records})

st.sidebar.metric("Total records", len(all_records))
st.sidebar.markdown("---")

mode = st.sidebar.radio(
    "Data selection",
    options=["Full dataset", "Random sample", "Single customer"],
    index=1,
    help="Choose what slice of data to feed the agent.",
)

n_sample = 100
selected_customer_id: str | None = None

if mode == "Random sample":
    n_sample = st.sidebar.slider(
        "Sample size", min_value=10, max_value=len(all_records), value=200, step=10,
    )
elif mode == "Single customer":
    selected_customer_id = st.sidebar.selectbox(
        "Customer ID",
        options=all_customer_ids,
        index=0,
    )


# ---------------------------------------------------------------------------
# Helper — error wrapper
# ---------------------------------------------------------------------------
def _run_agent(agent_fn, records: list):
    """Run an agent function, timing it and catching errors for the UI."""
    t0 = time.time()
    try:
        result = agent_fn(records)
        elapsed = time.time() - t0
        return result, elapsed, None
    except Exception as exc:
        elapsed = time.time() - t0
        return None, elapsed, exc


def _show_run_metadata(n_records: int, elapsed: float):
    """Display run metadata bar."""
    col1, col2 = st.columns(2)
    col1.metric("Records processed", f"{n_records:,}")
    col2.metric("Wall time", f"{elapsed:.2f} s")


# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════
tab_behavior, tab_churn, tab_features = st.tabs([
    "🧩 User Behavior",
    "📉 Churn Prediction",
    "🔬 Feature Analysis",
])


# -----------------------------------------------------------------------
# Tab 1 — User Behavior Agent
# -----------------------------------------------------------------------
with tab_behavior:
    st.header("User Behavior Agent")
    st.caption("DBSCAN clustering + autoencoder anomaly scoring")

    if st.button("▶ Run User Behavior Agent", key="run_behavior"):
        records = get_records(all_records, mode, n_sample, selected_customer_id)
        if len(records) < 10:
            st.warning(
                "The User Behavior agent needs at least ~10 records for "
                "meaningful clustering.  Consider using a larger sample."
            )

        with st.spinner("Running User Behavior Agent …"):
            from agents.user_behavior import run as run_behavior
            result, elapsed, error = _run_agent(run_behavior, records)

        if error is not None:
            st.error(f"**Agent error:** `{type(error).__name__}: {error}`")
            st.exception(error)
        else:
            _show_run_metadata(len(records), elapsed)
            st.markdown("---")

            # ---- Cluster profiles table ----
            st.subheader("Cluster Profiles")
            profiles_data = []
            for cp in result.cluster_profiles:
                profiles_data.append({
                    "Cluster ID": cp.cluster_id,
                    "Label": cp.label,
                    "Size": cp.size,
                    "Anomalous": "⚠️ Yes" if cp.is_anomalous else "No",
                    **{f"μ({k})": round(v, 3) for k, v in cp.centroid_features.items()},
                })
            st.dataframe(
                pd.DataFrame(profiles_data),
                use_container_width=True,
                hide_index=True,
            )

            # ---- Anomalous clusters ----
            if result.anomalous_clusters:
                st.subheader("⚠️ Anomalous Clusters")
                for cid in result.anomalous_clusters:
                    matched = [p for p in result.cluster_profiles if p.cluster_id == cid]
                    if matched:
                        p = matched[0]
                        st.warning(
                            f"**Cluster {cid}** — *{p.label}* ({p.size} customers): "
                            f"flagged as anomalous by cohort drift detection."
                        )
            else:
                st.info("No clusters flagged as anomalous.")

            # ---- 2D scatter (PCA) ----
            st.subheader("Customer Scatter (PCA projection)")

            # Rebuild the feature matrix for PCA
            try:
                from agents.user_behavior import _records_to_feature_df
                from sklearn.decomposition import PCA
                from sklearn.preprocessing import StandardScaler as _Scaler

                df_feat = _records_to_feature_df(records)
                feat_cols = [c for c in df_feat.columns if c != "customer_id"]
                X_pca = _Scaler().fit_transform(df_feat[feat_cols].values)
                coords = PCA(n_components=2, random_state=42).fit_transform(X_pca)

                scatter_df = pd.DataFrame({
                    "PC1": coords[:, 0],
                    "PC2": coords[:, 1],
                    "Cluster": [
                        str(cc.cluster_id) for cc in result.customer_clusters
                    ],
                    "Customer": [cc.customer_id for cc in result.customer_clusters],
                    "Anomaly Score": [
                        round(cc.anomaly_score, 4) for cc in result.customer_clusters
                    ],
                })

                st.scatter_chart(
                    scatter_df,
                    x="PC1",
                    y="PC2",
                    color="Cluster",
                    size=6,
                    use_container_width=True,
                )
            except Exception as exc:
                st.warning(f"Could not render PCA scatter: {exc}")

            # ---- Metadata ----
            st.subheader("Run Metadata")
            st.json(result.metadata)


# -----------------------------------------------------------------------
# Tab 2 — Churn Prediction Agent
# -----------------------------------------------------------------------
with tab_churn:
    st.header("Churn Prediction Agent")
    st.caption("Cox Proportional Hazards + Gradient Boosting classifier")

    if st.button("▶ Run Churn Prediction Agent", key="run_churn"):
        records = get_records(all_records, mode, n_sample, selected_customer_id)

        with st.spinner("Running Churn Prediction Agent …"):
            from agents.churn_prediction import run as run_churn
            result, elapsed, error = _run_agent(run_churn, records)

        if error is not None:
            st.error(f"**Agent error:** `{type(error).__name__}: {error}`")
            st.exception(error)
        else:
            _show_run_metadata(len(records), elapsed)
            st.markdown("---")

            # ---- Model metrics ----
            st.subheader("Model Performance")
            met_cols = st.columns(3)
            met_cols[0].metric(
                "Cox C-index",
                f"{result.survival_model_concordance:.4f}",
            )
            met_cols[1].metric(
                "Classifier AUC-ROC",
                f"{result.classifier_metrics.get('auc_roc', 'N/A')}",
            )
            met_cols[2].metric(
                "Classifier F1",
                f"{result.classifier_metrics.get('f1', 'N/A')}",
            )

            # ---- Per-customer risk table ----
            st.subheader("Per-Customer Risk Scores")
            pred_rows = []
            for p in result.predictions:
                pred_rows.append({
                    "Customer ID": p.customer_id,
                    "Risk Score": round(p.risk_score, 4),
                    "Survival P(6m)": round(p.survival_probability_6m, 4),
                    "Median Survival (mo)": (
                        round(p.median_survival_time, 1)
                        if p.median_survival_time is not None else "∞"
                    ),
                    "Churn Reason": p.churn_reason,
                    "Hazard Rate": round(p.hazard_rate, 4),
                })

            pred_df = pd.DataFrame(pred_rows)
            st.dataframe(
                pred_df.sort_values("Risk Score", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

            # ---- Survival curve for selected customer ----
            st.subheader("Survival Curve")
            cust_ids_in_result = [p.customer_id for p in result.predictions]
            sel_cust = st.selectbox(
                "Select customer for survival curve",
                options=cust_ids_in_result,
                key="surv_customer",
            )

            if sel_cust:
                try:
                    from agents.churn_prediction import (
                        _records_to_survival_df,
                        _fit_cox_model,
                    )
                    from lifelines import CoxPHFitter

                    surv_df = _records_to_survival_df(records)
                    feat_cols = [
                        c for c in surv_df.columns
                        if c not in ("customer_id", "duration", "event")
                    ]

                    # Re-fit Cox (fast — already cached data)
                    with st.spinner("Fitting Cox model for survival curve …"):
                        cph, _ = _fit_cox_model(surv_df, feat_cols)

                    # Get survival function for the selected customer
                    idx = surv_df.index[surv_df["customer_id"] == sel_cust][0]
                    cust_row = surv_df.iloc[[idx]]

                    sf = cph.predict_survival_function(
                        cust_row[["duration", "event"] + feat_cols]
                    )

                    chart_df = pd.DataFrame({
                        "Months": sf.index.values,
                        "Survival Probability": sf.iloc[:, 0].values,
                    })

                    st.line_chart(
                        chart_df.set_index("Months"),
                        use_container_width=True,
                    )

                    # Show the customer's prediction summary
                    cust_pred = [
                        p for p in result.predictions if p.customer_id == sel_cust
                    ][0]
                    info_cols = st.columns(4)
                    info_cols[0].metric("Risk Score", f"{cust_pred.risk_score:.4f}")
                    info_cols[1].metric(
                        "P(survive 6m)", f"{cust_pred.survival_probability_6m:.4f}",
                    )
                    info_cols[2].metric("Churn Reason", cust_pred.churn_reason)
                    info_cols[3].metric(
                        "Median Survival",
                        f"{cust_pred.median_survival_time:.1f} mo"
                        if cust_pred.median_survival_time is not None
                        else "∞",
                    )

                except Exception as exc:
                    st.warning(f"Could not render survival curve: {exc}")

            # ---- Feature importances ----
            st.subheader("Feature Importances (Classifier)")
            imp_df = pd.DataFrame(
                [
                    {"Feature": k, "Importance": v}
                    for k, v in sorted(
                        result.feature_importances.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                ]
            )
            st.bar_chart(imp_df.set_index("Feature"), use_container_width=True)


# -----------------------------------------------------------------------
# Tab 3 — Feature Analysis Agent
# -----------------------------------------------------------------------
with tab_features:
    st.header("Feature Analysis Agent")
    st.caption("Double Machine Learning — causal effect estimation (LinearDML)")

    st.info(
        "⏱ **This agent is slow** (~30-60 s on the full dataset) because it fits "
        "a separate DML model for each treatment feature.  Use a random sample "
        "of 200-500 records for faster iteration."
    )

    if st.button("▶ Run Feature Analysis Agent", key="run_features"):
        records = get_records(all_records, mode, n_sample, selected_customer_id)

        if len(records) < 50:
            st.warning(
                "DML needs a reasonable sample size for reliable estimates.  "
                "Consider using ≥ 50 records."
            )

        with st.spinner("Running Feature Analysis Agent (this may take a while) …"):
            from agents.feature_analysis import run as run_features
            result, elapsed, error = _run_agent(run_features, records)

        if error is not None:
            st.error(f"**Agent error:** `{type(error).__name__}: {error}`")
            st.exception(error)
        else:
            _show_run_metadata(len(records), elapsed)
            st.markdown("---")

            # ---- Summary metrics ----
            st.subheader("Summary")
            sum_cols = st.columns(4)
            sum_cols[0].metric("Method", result.method)
            sum_cols[1].metric("Outcome", result.outcome_variable)
            sum_cols[2].metric("Features analysed", len(result.effects))
            sum_cols[3].metric(
                "Significant",
                sum(1 for e in result.effects if e.is_significant),
            )

            # ---- Causal effects table ----
            st.subheader("Causal Feature Effects (ranked by |ATE|)")
            effects_rows = []
            for e in result.effects:
                effects_rows.append({
                    "Feature": e.feature_name,
                    "Description": e.treatment_description,
                    "ATE": round(e.ate, 5),
                    "CI Lower": round(e.ci_lower, 5),
                    "CI Upper": round(e.ci_upper, 5),
                    "p-value": (
                        f"{e.p_value:.4f}" if e.p_value is not None else "—"
                    ),
                    "Significant": "✅" if e.is_significant else "❌",
                })
            st.dataframe(
                pd.DataFrame(effects_rows),
                use_container_width=True,
                hide_index=True,
            )

            # ---- Bar chart with error bars ----
            st.subheader("ATE with 95% Confidence Intervals")

            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, max(4, len(result.effects) * 0.5)))
            names = [e.feature_name for e in result.effects]
            ates = [e.ate for e in result.effects]
            ci_low = [e.ci_lower for e in result.effects]
            ci_high = [e.ci_upper for e in result.effects]
            errors_low = [a - cl for a, cl in zip(ates, ci_low)]
            errors_high = [ch - a for a, ch in zip(ates, ci_high)]
            colors = [
                "#2ecc71" if e.is_significant and e.ate > 0
                else "#e74c3c" if e.is_significant and e.ate < 0
                else "#95a5a6"
                for e in result.effects
            ]

            y_pos = range(len(names))
            ax.barh(
                y_pos, ates,
                xerr=[errors_low, errors_high],
                color=colors,
                edgecolor="white",
                capsize=4,
                height=0.6,
            )
            ax.set_yticks(y_pos)
            ax.set_yticklabels(names)
            ax.axvline(x=0, color="black", linewidth=0.8, linestyle="--")
            ax.set_xlabel("Average Treatment Effect on Retention")
            ax.set_title("Causal Effects — Green = positive, Red = negative, Grey = not significant")
            fig.tight_layout()

            st.pyplot(fig)

            # ---- Confounders ----
            st.subheader("Confounders Used")
            st.write(", ".join(result.confounders_used))
