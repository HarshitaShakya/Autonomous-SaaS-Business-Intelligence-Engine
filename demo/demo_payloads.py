"""Example Strategy Agent payloads for demonstration.

These are realistic recommendation payloads that demonstrate every
action type the Action Agent supports.
"""

# ---------------------------------------------------------------------------
# Scenario 1: UX Experiment — Onboarding redesign
# ---------------------------------------------------------------------------
ONBOARDING_EXPERIMENT = {
    "recommendation_id": "rec_001_onboarding",
    "customer_segment": "high_churn_enterprise",
    "priority": "HIGH",
    "confidence": 0.91,
    "reason": (
        "Customers in the high_churn_enterprise segment have a churn probability of 0.84. "
        "Causal analysis via Double/Debiased Machine Learning indicates that onboarding "
        "friction (measured by time-to-first-value > 7 days) is the strongest causal driver "
        "of churn in this segment, with an Average Treatment Effect of -0.12 on 30-day retention."
    ),
    "recommended_action": {
        "type": "ux_experiment",
        "target": "redesigned_onboarding_v2",
        "description": "Enable the redesigned guided onboarding flow for high-churn enterprise users",
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
        "requires_approval": False
    }
}

# ---------------------------------------------------------------------------
# Scenario 2: A/B Experiment — Email cadence
# ---------------------------------------------------------------------------
EMAIL_EXPERIMENT = {
    "recommendation_id": "rec_002_email",
    "customer_segment": "trial_users",
    "priority": "MEDIUM",
    "confidence": 0.78,
    "reason": (
        "Feature analysis shows trial users receiving > 5 emails/week have 23% lower "
        "conversion rates. Causal inference suggests reducing cadence to 2 emails/week "
        "could improve trial-to-paid conversion."
    ),
    "recommended_action": {
        "type": "experiment",
        "target": "email_cadence_ab",
        "description": "A/B test reduced email frequency (2/week vs 5/week) for trial users",
        "expected_outcome": "increase_trial_conversion",
        "parameters": {
            "rollout_percentage": 15
        }
    },
    "expected_impact": {
        "metric": "trial_conversion",
        "direction": "increase",
        "estimated_change": 0.03
    }
}

# ---------------------------------------------------------------------------
# Scenario 3: Pricing discount — At-risk SMB retention
# ---------------------------------------------------------------------------
PRICING_DISCOUNT = {
    "recommendation_id": "rec_003_pricing",
    "customer_segment": "at_risk_smb",
    "priority": "HIGH",
    "confidence": 0.88,
    "reason": (
        "SMB accounts with < 3 active users and declining login frequency have "
        "0.72 churn probability. Price sensitivity analysis shows a 15% discount "
        "is the break-even retention incentive for this cohort."
    ),
    "recommended_action": {
        "type": "pricing_change",
        "target": "smb_retention_discount",
        "description": "Offer 15% discount to at-risk SMB segment for 30 days",
        "parameters": {
            "discount_percentage": 15.0,
            "duration_days": 30
        }
    },
    "expected_impact": {
        "metric": "retention_rate",
        "direction": "increase",
        "estimated_change": 0.05
    }
}

# ---------------------------------------------------------------------------
# Scenario 4: Alert — Churn spike
# ---------------------------------------------------------------------------
CHURN_ALERT = {
    "recommendation_id": "rec_004_alert",
    "customer_segment": "enterprise",
    "priority": "CRITICAL",
    "confidence": 0.95,
    "reason": (
        "Anomaly detection identified a 15% week-over-week increase in enterprise "
        "churn probability. Root cause appears to be a degraded API response time "
        "affecting the reporting dashboard feature."
    ),
    "recommended_action": {
        "type": "alert",
        "target": "churn_spike_enterprise",
        "description": "Notify product and revenue teams of enterprise churn spike",
        "parameters": {
            "channel": "product_team",
            "severity": "CRITICAL",
            "title": "⚠️ Enterprise Churn Spike Detected",
            "message": (
                "Enterprise segment churn probability increased 15% WoW. "
                "Root cause: API latency affecting reporting dashboard. "
                "Immediate investigation recommended."
            )
        }
    }
}

# ---------------------------------------------------------------------------
# Scenario 5: Retention intervention
# ---------------------------------------------------------------------------
RETENTION_INTERVENTION = {
    "recommendation_id": "rec_005_retention",
    "customer_segment": "churning_mid_market",
    "priority": "HIGH",
    "confidence": 0.82,
    "reason": (
        "Mid-market accounts showing disengagement pattern (30% drop in weekly "
        "active users over 4 weeks). Personalised outreach from CSM has shown "
        "40% save rate in historical data."
    ),
    "recommended_action": {
        "type": "retention_intervention",
        "target": "csm_outreach",
        "description": "Trigger personalised CSM outreach for churning mid-market accounts",
        "parameters": {
            "rollout_percentage": 10
        }
    },
    "expected_impact": {
        "metric": "retention_rate",
        "direction": "increase",
        "estimated_change": 0.06
    }
}

# ---------------------------------------------------------------------------
# Scenario 6: Low confidence — should be rejected
# ---------------------------------------------------------------------------
LOW_CONFIDENCE = {
    "recommendation_id": "rec_006_low_conf",
    "customer_segment": "unknown_segment",
    "confidence": 0.25,
    "recommended_action": {
        "type": "experiment",
        "target": "risky_feature",
        "description": "Low-confidence recommendation that should be rejected",
        "parameters": {
            "rollout_percentage": 50
        }
    }
}

# All scenarios for batch execution
ALL_SCENARIOS = [
    ("UX Onboarding Experiment", ONBOARDING_EXPERIMENT),
    ("Email Cadence A/B Test", EMAIL_EXPERIMENT),
    ("SMB Pricing Discount", PRICING_DISCOUNT),
    ("Enterprise Churn Alert", CHURN_ALERT),
    ("Retention Intervention", RETENTION_INTERVENTION),
    ("Low Confidence (Rejection)", LOW_CONFIDENCE),
]
