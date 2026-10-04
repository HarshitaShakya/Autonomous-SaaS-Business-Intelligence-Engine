# Autonomous SaaS Business Intelligence Engine

A source-agnostic, multi-agent ML pipeline for SaaS churn analysis. The engine maps any customer data source onto a single canonical schema, then runs three classical ML/statistical agents to produce structured outputs that a future LLM-based Strategy Agent can consume.

## 🏗️ Architecture

```
Data Sources → Adapters → Canonical Schema → [Agent 1, Agent 2, Agent 3] → Strategy Agent (future)
                                                                                    ↓
                                                                              Action Agent (future)
```

| Agent | Purpose | Method |
|-------|---------|--------|
| **User Behavior** | Segment customers by behaviour | DBSCAN clustering + autoencoder anomaly scoring |
| **Churn Prediction** | Forecast revenue risk | Cox Proportional Hazards + Gradient Boosting |
| **Feature Analysis** | Causal effect of features on retention | Double Machine Learning (LinearDML) |

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
│   └── agent_outputs.py         # Output models for all three agents
├── adapters/
│   ├── __init__.py              # Adapter registry
│   └── telco_churn_adapter.py   # Telco churn → CanonicalRecord
├── agents/
│   ├── __init__.py              # Package docs
│   ├── user_behavior.py         # Agent 1: DBSCAN + autoencoder
│   ├── churn_prediction.py      # Agent 2: Cox PH + GBM
│   └── feature_analysis.py      # Agent 3: LinearDML
├── testing_ui/
│   └── app.py                   # Streamlit agent-testing dashboard
├── data/
│   └── raw/
│       └── telco_churn.csv      # Raw dataset
├── notebooks/
│   └── eda.ipynb                # Exploratory data analysis
├── pipeline.py                  # End-to-end orchestration
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

This JSON is structured for consumption by a future LLM-based Strategy Agent.

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
| LangChain | langchain-core | LCEL RunnableLambda wrappers (no LLM calls) |
| Logging | loguru | Clean, structured logging |

---

## 📄 License

[Insert License Information Here]
