# Autonomous SaaS Business Intelligence Engine

A source-agnostic, multi-agent ML pipeline for SaaS churn analysis. The engine maps any customer data source onto a single canonical schema, runs three classical ML/statistical agents, then feeds their structured outputs through an LLM-based Strategy Agent that produces ranked business recommendations for the Action Agent.

## 🏗️ Architecture

```
Data Sources -> Adapters -> Canonical Schema -> [Agent 1, Agent 2, Agent 3] -> Strategy Agent
                                                                                    |
                                                                              Action Agent
```

| Agent | Purpose | Method |
|-------|---------|--------|
| **User Behavior** | Segment customers by behaviour | DBSCAN clustering + autoencoder anomaly scoring |
| **Churn Prediction** | Forecast revenue risk | Cox Proportional Hazards + Gradient Boosting |
| **Feature Analysis** | Causal effect of features on retention | Double Machine Learning (LinearDML) |
| **Strategy** | Reason over upstream outputs, produce recommendations | LLM (LangChain) with deterministic heuristic fallback |

All three agents read the canonical schema and return typed Pydantic outputs. They are wrapped as LangChain `RunnableLambda` instances for LCEL composability.

---

## 📊 Dataset: Telco Customer Churn

**Source:** `Dataset/WA_Fn-UseC_-Telco-Customer-Churn.csv` (copied to `data/raw/telco_churn.csv`)  
**Size:** 7,043 customers × 21 columns  
**Churn rate:** 26.5% (1,869 churned / 5,174 active)  
**Type:** Telco-style with a **direct churn label** — no proxy construction needed.

### Column Mapping

| Canonical Field | Source Column(s) | Mapping Logic |
|----------------|-----------------|---------------|
| `customer_id` | `customerID` | Direct |
| `signup_date` | Synthetic | `2023-12-31 − (tenure × 30 days)` |
| `plan_tier` | `Contract` | Direct: "Month-to-month" / "One year" / "Two year" |
| `mrr` | `MonthlyCharges` | Direct (Monthly Recurring Revenue) |
| `billing_cycle` | `Contract` | "monthly" / "annual" / "biennial" |
| `payment_status` | `PaymentMethod` | "auto_bank", "auto_card", "manual_mail", "manual_electronic" |
| `tenure_days` | `tenure` | `tenure × 30` (months → days) |
| `last_activity_date` | Synthetic | Reference date (2023-12-31) |
| `support_interactions` | `TechSupport` | 1 if "Yes", 0 otherwise (binary proxy) |
| `satisfaction_score` | — | `None` (not available in this source) |
| `churn_flag` | `Churn` | "Yes" → True, "No" → False |
| `churn_date` | Synthetic | Reference date for churned customers |

**Additional features** (in `service_features` dict): `gender`, `SeniorCitizen`, `Partner`, `Dependents`, `PhoneService`, `MultipleLines`, `InternetService`, `OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `StreamingTV`, `StreamingMovies`, `PaperlessBilling`, `TotalCharges`, `PaymentMethod`.

**Data quality:** 11 rows have blank `TotalCharges` (all `tenure == 0`). Imputed as `0.0`.

---

## 🧮 Mathematical Background

### Cox Proportional Hazards (Agent 2)

The Cox PH model estimates the instantaneous risk (hazard) of churn at time *t*:

```
h(t | X) = h₀(t) · exp(β₁X₁ + β₂X₂ + … + βₚXₚ)
```

- **h₀(t)** is the baseline hazard — a non-parametric function shared by all customers.
- **β** are log-hazard ratios: a positive β means the feature *increases* churn risk.
- **Survival function**: `S(t | X) = exp(−H₀(t) · exp(Xβ))` gives the probability of surviving past time *t*.
- **C-index** (concordance) measures model quality — analogous to AUC for time-to-event data. A C-index of 0.5 is random; above 0.7 is good.

**In plain language:** Instead of asking "will this customer churn?" (binary), Cox PH asks "when will they churn?" and gives a personalised survival curve. The model says: "Customer A has a 73% chance of still being active in 6 months; Customer B has only 28%."

### Double Machine Learning (Agent 3)

DML (Chernozhukov et al., 2018) estimates the *causal* effect of a treatment *T* on an outcome *Y*, controlling for confounders *X*:

```
Stage 1 (Nuisance estimation, cross-fitted):
    Ŷ = g(X)     →  residual: Ỹ = Y − Ŷ
    T̂ = f(X)     →  residual: T̃ = T − T̂

Stage 2 (Causal parameter):
    θ̂ = argmin_θ  Σ (Ỹ − θ · T̃)²
```

- **Stage 1** removes the influence of confounders using flexible ML models (gradient boosting). The residuals Ỹ and T̃ represent the "unexplained" parts of outcome and treatment.
- **Stage 2** estimates the Average Treatment Effect (ATE) θ from these residuals, with valid confidence intervals.

**In plain language:** Imagine you observe that customers with TechSupport churn less. But is that *because* TechSupport keeps them, or because long-tenured, engaged customers just tend to have TechSupport? DML answers: "After controlling for tenure, spending, demographics, and other services, having TechSupport *causally* increases retention probability by X%."

---

## 📁 Repository Structure

```
├── schemas/
│   ├── __init__.py              # Re-exports all models
│   ├── canonical.py             # CanonicalRecord — the universal contract
│   ├── agent_outputs.py         # Output models for Agents 1–3
│   └── strategy_outputs.py      # Output models for Strategy Agent (Agent 4)
├── adapters/
│   ├── __init__.py              # Adapter registry
│   └── telco_churn_adapter.py   # Telco churn -> CanonicalRecord
├── agents/
│   ├── __init__.py              # Package docs
│   ├── user_behavior.py         # Agent 1: DBSCAN + autoencoder
│   ├── churn_prediction.py      # Agent 2: Cox PH + GBM
│   ├── feature_analysis.py      # Agent 3: LinearDML
│   └── strategy_agent.py        # Agent 4: LLM reasoning + heuristic fallback
├── action_agent/                # Action Agent (teammate's module)
│   ├── agent.py                 # LangGraph workflow
│   ├── schemas.py               # StrategyRecommendation input contract
│   └── tools.py                 # GrowthBook, Stripe, Slack mock tools
├── testing_ui/
│   └── app.py                   # Streamlit agent-testing dashboard
├── data/
│   └── raw/
│       └── telco_churn.csv      # Raw dataset
├── notebooks/
│   └── eda.ipynb                # Exploratory data analysis
├── pipeline.py                  # End-to-end orchestration (all 4 agents)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```


---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Pipeline

```bash
# Default: loads data/raw/, auto-detects adapter, prints summary
python pipeline.py

# Save full JSON output
python pipeline.py --output results/output.json

# Explicit adapter selection
python pipeline.py --adapter telco_churn --data-dir data/raw/
```

### 3. Output

The pipeline produces:
- **Console summary** with cluster profiles, model metrics, and causal effects
- **Full JSON** saved to `data/pipeline_output.json` (or custom `--output` path)

This JSON includes Strategy Agent recommendations and pre-formatted Action Agent inputs.

---

## 🧠 Strategy Agent (Agent 4) — Output Schema Contract

The Strategy Agent is the critical integration point between the three ML agents and the Action Agent. Its output schema is **the** contract that both the Action Agent and human reviewers consume.

### Pipeline Position

```
[User Behavior, Churn Prediction, Feature Analysis]
    -> Strategy Agent (this module)
        -> Action Agent (human-approved execution)
```

### What It Does

1. **Aggregates** churn risk at the segment level (deterministic — not LLM).
2. **Ranks** causally significant features from Feature Analysis.
3. **Reasons** over segments + causal evidence (LLM or heuristic fallback).
4. **Produces** one `SegmentRecommendation` per flagged segment, ranked by estimated impact.

### Top-Level Output: `StrategyAgentResult`

| Field | Type | Description |
|-------|------|-------------|
| `recommendations` | `list[SegmentRecommendation]` | Ranked recommendations, one per flagged segment |
| `segments_analysed` | `int` | Total clusters from User Behavior Agent |
| `segments_flagged` | `int` | Segments that received a recommendation |
| `significant_features_available` | `int` | Causally significant features from Feature Analysis |
| `pipeline_metadata` | `dict` | LLM provider, model, latency, reasoning engine |

### Per-Segment Recommendation: `SegmentRecommendation`

| Field | Type | Description |
|-------|------|-------------|
| `recommendation_id` | `str` | Unique ID (e.g. `rec_a1b2c3d4`) |
| `action_type` | `ActionTypeEnum` | **Constrained** to: `trigger_a_b_test`, `apply_stripe_discount`, `send_cs_alert` |
| `action_parameters` | `dict` | Tool-specific parameters matching Action Agent schemas |
| `segment_risk` | `SegmentRiskEvidence` | Aggregated churn metrics for the target cluster |
| `causal_evidence` | `CausalEvidence` | Feature-level causal effect with full CI preserved |
| `justification` | `str` | **Human-readable narrative** naming segment, risk evidence, and causal evidence |
| `confidence_score` | `float [0,1]` | Derived from CI width (narrow=high confidence), NOT LLM self-assessment |
| `estimated_impact` | `float` | `ATE x segment_size` — expected additional retained customers |
| `urgency` | `str` | `critical`, `high`, `medium`, or `low` |
| `segment_label` | `str` | Human-readable segment descriptor |

### Mapping to Action Agent Input

The `to_action_agent_inputs()` utility converts each recommendation to the Action Agent's `StrategyRecommendation` schema:

| SegmentRecommendation | -> | StrategyRecommendation |
|-----------------------|----|------------------------|
| `recommendation_id` | | `recommendation_id` |
| `action_type.value` | | `action_type` |
| `segment_label` | | `target_entity` |
| `justification` | | `description` and `justification` |
| `action_parameters` | | `parameters` |
| `confidence_score` | | `confidence_score` |

### Action Types (Constrained)

The `action_type` field is an enum pinned to exactly what the Action Agent implements:

| Value | Action Agent Tool | Risk Level | Use Case |
|-------|-------------------|------------|----------|
| `trigger_a_b_test` | GrowthBook experiment | Low (auto) | Product feature experiments |
| `apply_stripe_discount` | Stripe retention coupon | **High (HITL)** | Payment-driven churn |
| `send_cs_alert` | Slack/CRM notification | Low (auto) | Manual outreach |

### Grounding Guarantees

- **No invented numbers.** All risk scores, ATE values, CI bounds, and cluster sizes in the justification come from upstream agents. The LLM prompt explicitly forbids stating numbers not in the input.
- **CI fidelity.** The `CausalEvidence` sub-model carries the original `ci_lower`, `ci_upper`, and `ci_width` from Feature Analysis. If the CI is wide (>0.3), the justification says "suggestive but imprecise evidence" and `confidence_score` is lowered.
- **Deterministic fallback.** When no LLM API key is configured, the same output schema is produced by a rule-based engine, so the pipeline runs end-to-end without external dependencies.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STRATEGY_LLM_MODEL` | `openai:gpt-4o` | LangChain model string (supports any provider via `init_chat_model`) |
| `STRATEGY_LLM_TEMPERATURE` | `0.0` | LLM temperature (0 = deterministic) |
| `OPENAI_API_KEY` | — | Required for OpenAI models. If absent, heuristic fallback is used. |

### Example Output (Heuristic Mode)

```json
{
  "recommendation_id": "rec_a1b2c3d4",
  "action_type": "trigger_a_b_test",
  "segment_label": "New - Low-spend - Minimal-service",
  "urgency": "high",
  "confidence_score": 0.93,
  "estimated_impact": 83.6,
  "justification": "Segment 'New - Low-spend - Minimal-service' (cluster 0, 1729 customers) has a mean churn risk of 48% with a 6-month survival probability of 75%. The dominant churn driver is 'dissatisfaction'. Feature Analysis identifies 'Having TechSupport' as the strongest causal lever for retention, with strong statistical confidence (ATE = +0.0484, 95% CI = [0.0141, 0.0826]). An A/B test is recommended to validate whether deploying 'Having TechSupport' reduces churn in this segment.",
  "causal_evidence": {
    "feature_name": "TechSupport",
    "ate": 0.0484,
    "ci_lower": 0.0141,
    "ci_upper": 0.0826,
    "ci_width": 0.0685,
    "is_significant": true
  }
}
```

---

## 🧪 Agent Testing Dashboard

A standalone Streamlit UI for testing the three ML agents individually during
development.  It imports the existing agent code directly — no logic is
reimplemented.

### Running the Dashboard

```bash
# From the project root
streamlit run testing_ui/app.py
```

### Features

| Feature | Details |
|---------|---------|
| **Agent selector** | Tabs for User Behavior, Churn Prediction, Feature Analysis |
| **Data selection** | Full dataset, random sample of N customers, or a single `customer_id` |
| **Structured output** | Cluster profiles table, PCA scatter, sortable risk table, survival curves, ATE chart with CIs |
| **Run metadata** | Records processed, wall-clock time |
| **Error surfacing** | Agent errors appear as readable messages in the UI (not just terminal tracebacks) |

> **Tip:** The Feature Analysis agent is slow on the full dataset (~30-60 s).
> Use a random sample of 200–500 records for faster iteration.

---

## 🔌 Adding a New Data Source

To add a second data source (e.g. Stripe billing data, a different CRM):

1. **Create the adapter**: `adapters/stripe_adapter.py`

```python
from adapters import register
from schemas.canonical import CanonicalRecord

@register("stripe")
def load(path: str | Path) -> list[CanonicalRecord]:
    # Read your raw data
    # Map each row to a CanonicalRecord
    # Return the list
    ...
```

2. **Register it**: Add `from adapters import stripe_adapter` to `adapters/__init__.py`

3. **Run**: `python pipeline.py --adapter stripe --data-dir path/to/stripe/data`

**No changes to any agent are needed.** The three agents only read the canonical schema — they never see raw column names.

---

## 🔧 Tech Stack

| Purpose | Library | Why |
|---------|---------|-----|
| Schema/validation | Pydantic v2 | Type-safe contracts; LangChain-native |
| Data processing | pandas, numpy | Industry standard for tabular data |
| Clustering | scikit-learn (DBSCAN) | Robust, well-documented density-based clustering |
| Anomaly scoring | scikit-learn (MLPRegressor) | Lightweight autoencoder without PyTorch dependency |
| Survival analysis | lifelines | Pure Python Cox PH with excellent API |
| Binary classification | scikit-learn (GradientBoosting) | Strong baseline with feature importances |
| Causal inference | econml (LinearDML) | Microsoft Research; DML with valid CIs |
| LangChain | langchain, langchain-core, langchain-openai | LCEL wrappers + Strategy Agent LLM reasoning |
| LLM abstraction | langchain `init_chat_model` | Provider-agnostic; switch with env var |
| Logging | loguru | Clean, structured logging |

---

## 📄 License

[Insert License Information Here]
