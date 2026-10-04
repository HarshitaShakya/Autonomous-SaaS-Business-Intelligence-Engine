"""Agent 2 — Churn Prediction Agent (Forecasting Layer).

Consumes ``CanonicalRecord`` instances (optionally enriched with Agent 1's
cluster assignment) and produces a ``ChurnPredictionResult`` containing:

1. **Survival analysis** via Cox Proportional Hazards (``lifelines``) —
   estimates a hazard function and expected time-to-churn per customer.
2. **Binary classifier** (Gradient Boosting) as a simpler risk-flag baseline,
   with comparison metrics.
3. **Churn reason categorisation** — dissatisfaction-driven vs payment-driven
   vs mixed, operationalised from canonical schema fields.

Mathematical background
-----------------------
**Cox Proportional Hazards** models the hazard function as:

    h(t | X) = h₀(t) · exp(β₁X₁ + β₂X₂ + … + βₚXₚ)

where h₀(t) is the baseline hazard (non-parametric) and βⱼ are log-hazard
ratios.  A positive βⱼ means feature Xⱼ *increases* the instantaneous risk
of churn.  The model's quality is measured by **Harrell's C-index** (concordance),
analogous to AUC for time-to-event data.

The survival function S(t | X) = exp(−H₀(t) · exp(Xβ)) gives the probability
that a customer survives past time t.

Design notes
------------
* ``tenure_days`` is used as the time-to-event variable.  For churned customers
  the event is observed; for active customers the observation is *right-
  censored* at their current tenure.
* The churn-reason heuristic uses ``payment_status`` and ``support_interactions``
  from the canonical schema — it's deliberately simple so it generalises across
  sources.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from lifelines import CoxPHFitter
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from langchain_core.runnables import RunnableLambda

from schemas.canonical import CanonicalRecord
from schemas.agent_outputs import ChurnPredictionResult, CustomerChurnRisk


# ── Feature engineering ──────────────────────────────────────────────

def _records_to_survival_df(records: list[CanonicalRecord]) -> pd.DataFrame:
    """Build a DataFrame suitable for both Cox PH and the binary classifier.

    Columns
    -------
    customer_id, duration (months), event (1=churned), plus all numeric
    features derived from the canonical schema.
    """
    rows: list[dict[str, Any]] = []

    for rec in records:
        sf = rec.service_features
        tenure_months = max(rec.tenure_days / 30, 0.5)

        # Service counts
        service_cols = [
            "PhoneService", "MultipleLines", "OnlineSecurity",
            "OnlineBackup", "DeviceProtection", "TechSupport",
            "StreamingTV", "StreamingMovies",
        ]
        service_count = sum(
            1 for col in service_cols
            if sf.get(col, 0) == 1
        )

        internet = sf.get("InternetService", "No")

        rows.append({
            "customer_id": rec.customer_id,
            "duration": tenure_months,
            "event": int(rec.churn_flag),
            "mrr": rec.mrr,
            "total_charges": float(sf.get("TotalCharges", 0.0)),
            "support_flag": rec.support_interactions,
            "service_count": service_count,
            "is_senior": int(sf.get("SeniorCitizen", 0)),
            "has_partner": int(sf.get("Partner", 0)),
            "has_dependents": int(sf.get("Dependents", 0)),
            "is_paperless": int(sf.get("PaperlessBilling", 0)),
            "payment_auto": 1 if rec.payment_status.startswith("auto") else 0,
            "payment_electronic": 1 if rec.payment_status == "manual_electronic" else 0,
            "internet_fiber": 1 if internet == "Fiber optic" else 0,
            "internet_dsl": 1 if internet == "DSL" else 0,
            "contract_monthly": 1 if rec.plan_tier == "Month-to-month" else 0,
            "contract_yearly": 1 if rec.plan_tier == "One year" else 0,
            "contract_biennial": 1 if rec.plan_tier == "Two year" else 0,
        })

    return pd.DataFrame(rows)


# ── Churn reason categorisation ──────────────────────────────────────

def _classify_churn_reason(row: pd.Series) -> str:
    """Heuristic churn-reason classification.

    Categories
    ----------
    * **dissatisfaction**: Customer shows low engagement — no tech support,
      few services, month-to-month contract.  These are customers who aren't
      getting value and leave by choice.
    * **payment**: Customer uses a manual/electronic payment method and has
      paperless billing.  This pattern correlates with involuntary churn
      (failed payments) or friction-driven churn.
    * **mixed**: Both signals present, or neither clearly dominates.
    """
    dissatisfaction_signals = (
        (row.get("support_flag", 0) == 0)
        + (row.get("service_count", 0) <= 2)
        + (row.get("contract_monthly", 0) == 1)
    )

    payment_signals = (
        (row.get("payment_electronic", 0) == 1)
        + (row.get("is_paperless", 0) == 1)
        + (row.get("payment_auto", 0) == 0)
    )

    if dissatisfaction_signals >= 2 and payment_signals < 2:
        return "dissatisfaction"
    elif payment_signals >= 2 and dissatisfaction_signals < 2:
        return "payment"
    else:
        return "mixed"


# ── Cox Proportional Hazards ─────────────────────────────────────────

def _fit_cox_model(
    df: pd.DataFrame, feature_cols: list[str]
) -> tuple[CoxPHFitter, float]:
    """Fit a Cox PH model and return the fitter + concordance index.

    The Cox model is fit on ``duration`` (time) and ``event`` (censoring
    indicator), using the features in ``feature_cols``.
    """
    cox_df = df[["duration", "event"] + feature_cols].copy()

    # Penalise to handle potential multicollinearity
    cph = CoxPHFitter(penalizer=0.01)
    cph.fit(
        cox_df,
        duration_col="duration",
        event_col="event",
        show_progress=False,
    )

    c_index = float(cph.concordance_index_)
    logger.info(f"Cox PH concordance index: {c_index:.4f}")

    return cph, c_index


# ── Binary classifier ────────────────────────────────────────────────

def _fit_classifier(
    df: pd.DataFrame, feature_cols: list[str]
) -> tuple[GradientBoostingClassifier, dict[str, float], dict[str, float]]:
    """Train a GradientBoosting classifier and return model + metrics.

    Uses a 80/20 stratified split for evaluation.
    """
    X = df[feature_cols].values
    y = df["event"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "auc_roc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "f1": round(float(f1_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred)), 4),
        "recall": round(float(recall_score(y_test, y_pred)), 4),
    }

    importances = {
        col: round(float(imp), 4)
        for col, imp in zip(feature_cols, clf.feature_importances_)
    }

    logger.info(f"Classifier metrics: {metrics}")
    return clf, metrics, importances


# ── Main agent function ──────────────────────────────────────────────

def run(records: list[CanonicalRecord]) -> ChurnPredictionResult:
    """Execute the Churn Prediction Agent.

    Steps
    -----
    1. Build feature matrix from canonical records.
    2. Fit Cox PH survival model → hazard rates, survival probabilities.
    3. Train GradientBoosting binary classifier → risk scores, metrics.
    4. Classify churn reasons per customer.
    5. Assemble per-customer predictions.

    Parameters
    ----------
    records : list[CanonicalRecord]
        Canonical-schema customer records.

    Returns
    -------
    ChurnPredictionResult
        Per-customer risk assessments, model metrics, and feature importances.
    """
    logger.info(f"Churn Prediction Agent: processing {len(records)} records")

    # Step 1 — Build feature matrix
    df = _records_to_survival_df(records)
    feature_cols = [
        c for c in df.columns if c not in ("customer_id", "duration", "event")
    ]

    # Step 2 — Cox PH survival model
    cph, c_index = _fit_cox_model(df, feature_cols)

    # Get survival functions for all customers
    cox_features = df[feature_cols]

    # Predict partial hazard (exp(Xβ)) for each customer
    partial_hazards = cph.predict_partial_hazard(
        df[["duration", "event"] + feature_cols]
    ).values.flatten()

    # Survival probability at 6 months (t=6)
    try:
        surv_funcs = cph.predict_survival_function(
            df[["duration", "event"] + feature_cols]
        )
        # Find closest time to t=6
        t_target = 6.0
        times = surv_funcs.index.values
        closest_t = times[np.argmin(np.abs(times - t_target))]
        surv_6m = surv_funcs.loc[closest_t].values
    except Exception as e:
        logger.warning(f"Could not compute survival functions: {e}")
        surv_6m = np.full(len(df), 0.5)

    # Median survival time
    try:
        median_surv = cph.predict_median(
            df[["duration", "event"] + feature_cols]
        ).values.flatten()
    except Exception as e:
        logger.warning(f"Could not compute median survival: {e}")
        median_surv = np.full(len(df), np.inf)

    # Step 3 — Binary classifier
    clf, classifier_metrics, feature_importances = _fit_classifier(df, feature_cols)

    # Predict risk scores for ALL customers (not just test set)
    risk_scores = clf.predict_proba(df[feature_cols].values)[:, 1]

    # Step 4 — Churn reason classification
    churn_reasons = df.apply(_classify_churn_reason, axis=1).tolist()

    # Step 5 — Assemble per-customer predictions
    predictions: list[CustomerChurnRisk] = []
    for i in range(len(df)):
        median_time = float(median_surv[i])
        if np.isinf(median_time) or np.isnan(median_time):
            median_time_out = None
        else:
            median_time_out = round(median_time, 2)

        predictions.append(
            CustomerChurnRisk(
                customer_id=str(df.iloc[i]["customer_id"]),
                risk_score=round(float(risk_scores[i]), 4),
                survival_probability_6m=round(
                    float(np.clip(surv_6m[i], 0, 1)), 4
                ),
                median_survival_time=median_time_out,
                churn_reason=churn_reasons[i],
                hazard_rate=round(float(partial_hazards[i]), 4),
            )
        )

    result = ChurnPredictionResult(
        predictions=predictions,
        classifier_metrics=classifier_metrics,
        survival_model_concordance=round(c_index, 4),
        feature_importances=feature_importances,
    )

    logger.info(
        f"Churn Prediction Agent complete: C-index={c_index:.4f}, "
        f"AUC={classifier_metrics['auc_roc']}"
    )
    return result


# ── LangChain LCEL wrapper ───────────────────────────────────────────

churn_prediction_runnable = RunnableLambda(run).with_config(
    {"run_name": "ChurnPredictionAgent"}
)
"""LangChain Runnable that wraps :func:`run`.

Usage::

    from agents.churn_prediction import churn_prediction_runnable
    result = churn_prediction_runnable.invoke(records)
"""
