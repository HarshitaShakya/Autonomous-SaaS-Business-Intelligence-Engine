# Action Agent — Autonomous SaaS Business Intelligence Engine

The **Action Agent** is the autonomous execution layer of the Autonomous SaaS Business Intelligence Engine. It receives strategy recommendations from the Strategy Agent and converts them into controlled, verified, and auditable business actions.

## Architecture

```
              STRATEGY AGENT
                    │
                    ▼
           ┌──────────────────┐
           │ Recommendation   │
           │ Parser           │
           └────────┬─────────┘
                    ▼
           ┌──────────────────┐
           │ Action Planner   │
           │ + Idempotency    │
           └────────┬─────────┘
                    ▼
           ┌──────────────────┐
           │ Policy / Risk    │
           │ Engine           │
           └────────┬─────────┘
                    ▼
           ┌──────────────────┐
           │ Action Registry  │
           └─────┬────┬────┬──┘
                 │    │    │
                 ▼    ▼    ▼
              EXP.  PRICING  UX   ALERT  RETENTION
                 │    │    │     │      │
                 └────┼────┴─────┼──────┘
                      ▼
              ADAPTER LAYER (Mock / Live)
                      │
                      ▼
                VERIFICATION
                      │
                ┌─────┴─────┐
                ▼           ▼
             AUDIT       ROLLBACK
```

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone and install
cd "d:\Action agent"
pip install -e ".[dev]"

# Copy environment config
copy .env.example .env
```

### Run the Demo

```bash
python -m demo.run_demo
```

This executes six scenarios demonstrating every action type, idempotency, rollback, and audit logging — all without a running server.

### Start the HTTP Server

```bash
uvicorn action_agent.main:app --reload
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=action_agent --cov-report=term-missing
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/actions/execute` | Execute a strategy recommendation |
| `POST` | `/actions/preview` | Preview what would happen (no execution) |
| `GET` | `/actions/{action_id}` | Get action details |
| `POST` | `/actions/{action_id}/rollback` | Rollback a completed action |
| `POST` | `/actions/{action_id}/approve` | Approve a pending high-risk action |
| `GET` | `/actions/` | Query action history |
| `GET` | `/health` | Health check |

## Execution Modes

| Mode | Description |
|------|-------------|
| `DRY_RUN` (default) | Full pipeline executes but adapters simulate. No real external changes. |
| `LIVE` | Adapters call real external systems. HIGH risk actions require approval. |

Set via environment variable: `EXECUTION_MODE=DRY_RUN`

## Action Types

| Type | Handler | Adapter | Rollback |
|------|---------|---------|----------|
| `EXPERIMENT` | ExperimentActionHandler | ExperimentAdapter | ✅ |
| `PRICING_CHANGE` | PricingActionHandler | PricingAdapter | ✅ |
| `UX_UPDATE` | UXActionHandler | FeatureFlagAdapter | ✅ |
| `ALERT` | AlertActionHandler | NotificationAdapter | ❌ |
| `RETENTION_INTERVENTION` | RetentionActionHandler | ExperimentAdapter | ✅ |

## Strategy Agent Input Contract

```json
{
  "recommendation_id": "rec_123",
  "customer_segment": "high_churn_enterprise",
  "priority": "HIGH",
  "confidence": 0.91,
  "reason": "Causal analysis indicates onboarding friction drives churn",
  "recommended_action": {
    "type": "ux_experiment",
    "target": "redesigned_onboarding_v2",
    "description": "Enable redesigned onboarding for high-risk users",
    "expected_outcome": "increase_30_day_retention",
    "parameters": {
      "rollout_percentage": 20
    }
  },
  "expected_impact": {
    "metric": "retention_rate",
    "direction": "increase",
    "estimated_change": 0.08
  },
  "constraints": {
    "max_rollout_percentage": 50,
    "requires_approval": false
  }
}
```

## Execution Result

```json
{
  "action_id": "act_a1b2c3d4e5f6",
  "recommendation_id": "rec_123",
  "action_type": "UX_UPDATE",
  "execution_status": "SUCCESS",
  "verification_status": "PASSED",
  "execution_mode": "DRY_RUN",
  "risk_level": "LOW",
  "policy_decision": "APPROVED",
  "rollback_supported": true,
  "rollback_id": "act_a1b2c3d4e5f6"
}
```

## Policy Engine

Configurable via `.env`:

| Setting | LOW | MEDIUM | HIGH |
|---------|-----|--------|------|
| Min confidence | 0.5 | 0.7 | 0.85 |
| Max rollout % | 100 | 50 | 20 |
| Auto-approve | ✅ | ✅ | ❌ (LIVE only) |

## Connecting the Strategy Agent

### Option 1: HTTP (Microservice)

```python
import httpx

async def send_recommendation(rec: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/actions/execute",
            json=rec
        )
        return response.json()
```

### Option 2: Direct Python Import

```python
from action_agent.core.executor import ActionExecutor

# Build executor (see main.py for full setup)
result = await executor.execute(recommendation_payload)
```

## Adding New Action Types

1. Define enum: Add to `ActionType` in `schemas/action.py`
2. Create handler: Implement `ActionHandler` in `registry/`
3. Register: `registry.register(ActionType.NEW, NewHandler(adapter))`
4. Add adapter: Implement interface in `adapters/` + mock in `adapters/mock/`

No existing code changes needed — open/closed principle.

## Project Structure

```
action_agent/
├── schemas/          # Pydantic data contracts (THE integration point)
├── core/             # Business logic (parser, planner, policy, executor)
├── registry/         # Action type registry + handlers
├── adapters/         # External system abstraction + mocks
├── persistence/      # SQLite database + repositories
├── api/              # FastAPI routes
└── main.py           # App entry point

tests/                # 50+ tests covering every component
demo/                 # Demo payloads + CLI runner
```

## License

Internal project — Autonomous SaaS Business Intelligence Engine.
