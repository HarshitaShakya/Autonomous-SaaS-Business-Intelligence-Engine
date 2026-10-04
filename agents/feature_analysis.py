"""Agent 3 — Feature Analysis Agent (Validation Layer).

Measures the **causal** effect of product features on customer retention,
not just correlation.  Uses Double Machine Learning (DML) to answer:

    "Did using feature X *cause* the customer to stay, or is it just
    correlated with customers who were going to stay anyway?"

Mathematical background — Double Machine Learning
--------------------------------------------------
DML (Chernozhukov et al., 2018) is a two-stage procedure for estimating the
causal effect θ of a treatment T on an outcome Y, controlling for
high-dimensional confounders X:

    Stage 1 — Nuisance estimation (cross-fitted):
        Ŷ = g(X)     residual: Ỹ = Y − Ŷ
        T̂ = f(X)     residual: T̃ = T − T̂

    Stage 2 — Causal parameter:
        θ̂ = argmin_θ Σ (Ỹ − θ · T̃)²

By partialling out the confounders in Stage 1 with flexible ML models (here:
gradient boosting), Stage 2 gives a *debiased* estimate of the Average
Treatment Effect (ATE) with valid confidence intervals — even when the
confounder space is high-dimensional.

Implementation
--------------
We use ``econml.dml.LinearDML`` which implements the above with:
* ``model_y``: Gradient boosting regressor for the outcome nuisance.
* ``model_t``: Gradient boosting classifier for the treatment propensity.
* Cross-fitting to avoid over-fitting bias.

Each binary service feature (e.g. OnlineSecurity, TechSupport) is treated as
a separate treatment in turn, with the other features as confounders.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
)
from langchain_core.runnables import RunnableLambda

from schemas.canonical import CanonicalRecord
from schemas.agent_outputs import FeatureAnalysisResult, CausalFeatureEffect


# ── Feature engineering ──────────────────────────────────────────────

def _records_to_causal_df(records: list[CanonicalRecord]) -> pd.DataFrame:
    """Build a DataFrame for causal analysis from canonical records.

    Columns include:
    * **Outcome**: ``retention`` (1 − churn_flag)
    * **Treatments**: binary service features that we want to test causally
    * **Confounders**: demographic and tenure-related variables
    """
    rows: list[dict[str, Any]] = []

    for rec in records:
        sf = rec.service_features
        tenure_months = max(rec.tenure_days / 30, 0.5)
        internet = sf.get("InternetService", "No")

        rows.append({
            "customer_id": rec.customer_id,
            "retention": 0 if rec.churn_flag else 1,

            # ── Treatments (binary service features) ──
            "OnlineSecurity": int(sf.get("OnlineSecurity", 0) == 1),
            "TechSupport": int(sf.get("TechSupport", 0) == 1),
            "OnlineBackup": int(sf.get("OnlineBackup", 0) == 1),
            "DeviceProtection": int(sf.get("DeviceProtection", 0) == 1),
            "StreamingTV": int(sf.get("StreamingTV", 0) == 1),
            "StreamingMovies": int(sf.get("StreamingMovies", 0) == 1),
            "PhoneService": int(sf.get("PhoneService", 0) == 1),
            "MultipleLines": int(sf.get("MultipleLines", 0) == 1),
            "PaperlessBilling": int(sf.get("PaperlessBilling", 0) == 1),

            # Internet type as treatment (fiber vs non-fiber)
            "FiberOptic": 1 if internet == "Fiber optic" else 0,

            # Contract as treatment (long-term vs month-to-month)
            "LongTermContract": 0 if rec.plan_tier == "Month-to-month" else 1,

            # ── Confounders ──
            "tenure_months": tenure_months,
            "mrr": rec.mrr,
            "total_charges": float(sf.get("TotalCharges", 0.0)),
            "is_senior": int(sf.get("SeniorCitizen", 0)),
            "has_partner": int(sf.get("Partner", 0)),
            "has_dependents": int(sf.get("Dependents", 0)),
            "payment_auto": 1 if rec.payment_status.startswith("auto") else 0,
            "gender_male": 1 if sf.get("gender") == "Male" else 0,
        })

    return pd.DataFrame(rows)


# Treatment features to analyse and their human-readable descriptions
_TREATMENTS: dict[str, str] = {
    "OnlineSecurity": "Having Online Security service",
    "TechSupport": "Having Tech Support service",
    "OnlineBackup": "Having Online Backup service",
    "DeviceProtection": "Having Device Protection service",
    "StreamingTV": "Having Streaming TV service",
    "StreamingMovies": "Having Streaming Movies service",
    "PaperlessBilling": "Using Paperless Billing",
    "FiberOptic": "Having Fiber Optic internet (vs DSL/None)",
    "LongTermContract": "Having a long-term contract (1yr/2yr vs month-to-month)",
    "MultipleLines": "Having Multiple Phone Lines",
}

# Confounders — variables that affect both treatment and outcome
_CONFOUNDERS: list[str] = [
    "tenure_months",
    "mrr",
    "total_charges",
    "is_senior",
    "has_partner",
    "has_dependents",
    "payment_auto",
    "gender_male",
]


# ── DML estimation ──────────────────────────────────────────────────

def _estimate_single_treatment(
    df: pd.DataFrame,
    treatment_col: str,
    outcome_col: str = "retention",
    confounder_cols: list[str] | None = None,
) -> CausalFeatureEffect | None:
    """Estimate the ATE of a single binary treatment via LinearDML.

    Returns None if the treatment has insufficient variance (< 5% treated
    or < 5% untreated).
    """
    # Lazy import to keep module load fast
    from econml.dml import LinearDML

    if confounder_cols is None:
        confounder_cols = _CONFOUNDERS

    T = df[treatment_col].values
    Y = df[outcome_col].values
    X_confounders = df[confounder_cols].values

    # Skip if treatment has too little variance
    treat_pct = T.mean()
    if treat_pct < 0.05 or treat_pct > 0.95:
        logger.warning(
            f"Skipping {treatment_col}: treatment prevalence={treat_pct:.2%} "
            f"(insufficient variance)"
        )
        return None

    model_y = GradientBoostingRegressor(
        n_estimators=100, max_depth=3, random_state=42
    )
    model_t = GradientBoostingClassifier(
        n_estimators=100, max_depth=3, random_state=42
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dml = LinearDML(
            model_y=model_y,
            model_t=model_t,
            discrete_treatment=True,
            cv=3,
            random_state=42,
        )

        dml.fit(
            Y=Y.reshape(-1, 1),
            T=T.reshape(-1, 1),
            X=None,  # no heterogeneity features
            W=X_confounders,
        )

    # Extract ATE and confidence interval
    ate_raw = dml.ate()
    ate = float(np.asarray(ate_raw).flatten()[0])
    ci = dml.ate_interval(alpha=0.05)
    ci_lower = float(np.asarray(ci[0]).flatten()[0])
    ci_upper = float(np.asarray(ci[1]).flatten()[0])

    # Significance: CI doesn't cross zero
    is_significant = not (ci_lower <= 0 <= ci_upper)

    # Approximate p-value from the CI width and ATE
    # Using normal approximation: z = ATE / SE, where SE ≈ (ci_upper - ci_lower) / (2 * 1.96)
    se = (ci_upper - ci_lower) / (2 * 1.96)
    if se > 0:
        from scipy import stats as scipy_stats
        z = abs(ate) / se
        p_value = float(2 * (1 - scipy_stats.norm.cdf(z)))
    else:
        p_value = None

    logger.info(
        f"{treatment_col}: ATE={ate:.4f} [{ci_lower:.4f}, {ci_upper:.4f}] "
        f"{'*** significant' if is_significant else 'ns'}"
    )

    return CausalFeatureEffect(
        feature_name=treatment_col,
        treatment_description=_TREATMENTS.get(treatment_col, treatment_col),
        ate=round(ate, 6),
        ci_lower=round(ci_lower, 6),
        ci_upper=round(ci_upper, 6),
        p_value=round(p_value, 6) if p_value is not None else None,
        is_significant=is_significant,
    )


# ── Main agent function ──────────────────────────────────────────────

def run(records: list[CanonicalRecord]) -> FeatureAnalysisResult:
    """Execute the Feature Analysis Agent.

    For each treatment feature, estimates its causal effect on retention
    using Double Machine Learning, controlling for confounders.

    Parameters
    ----------
    records : list[CanonicalRecord]
        Canonical-schema customer records.

    Returns
    -------
    FeatureAnalysisResult
        Ranked list of features with causal effect estimates and CIs.
    """
    logger.info(f"Feature Analysis Agent: processing {len(records)} records")

    df = _records_to_causal_df(records)

    effects: list[CausalFeatureEffect] = []
    for treatment_col, description in _TREATMENTS.items():
        logger.info(f"Estimating causal effect of: {treatment_col}")
        effect = _estimate_single_treatment(df, treatment_col)
        if effect is not None:
            effects.append(effect)

    # Rank by absolute ATE (largest effect first)
    effects.sort(key=lambda e: abs(e.ate), reverse=True)

    result = FeatureAnalysisResult(
        effects=effects,
        method="LinearDML",
        confounders_used=list(_CONFOUNDERS),
        outcome_variable="retention",
        n_samples=len(df),
    )

    logger.info(
        f"Feature Analysis Agent complete: {len(effects)} features analysed, "
        f"{sum(1 for e in effects if e.is_significant)} significant"
    )
    return result


# ── LangChain LCEL wrapper ───────────────────────────────────────────

feature_analysis_runnable = RunnableLambda(run).with_config(
    {"run_name": "FeatureAnalysisAgent"}
)
"""LangChain Runnable that wraps :func:`run`.

Usage::

    from agents.feature_analysis import feature_analysis_runnable
    result = feature_analysis_runnable.invoke(records)
"""
