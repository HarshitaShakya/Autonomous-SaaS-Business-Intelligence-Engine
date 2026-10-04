"""Pydantic schemas for the Autonomous SaaS BI Engine.

Re-exports the canonical input schema and all agent output schemas
so downstream code can do:

    from schemas import CanonicalRecord, BehaviorAnalysisResult, ...
"""

from schemas.canonical import CanonicalRecord
from schemas.agent_outputs import (
    BehaviorAnalysisResult,
    ChurnPredictionResult,
    FeatureAnalysisResult,
    ClusterProfile,
    CustomerCluster,
    CustomerChurnRisk,
    CausalFeatureEffect,
)
from schemas.strategy_outputs import (
    ActionTypeEnum,
    CausalEvidence,
    SegmentRecommendation,
    SegmentRiskEvidence,
    StrategyAgentInput,
    StrategyAgentResult,
)

__all__ = [
    "CanonicalRecord",
    "BehaviorAnalysisResult",
    "ChurnPredictionResult",
    "FeatureAnalysisResult",
    "ClusterProfile",
    "CustomerCluster",
    "CustomerChurnRisk",
    "CausalFeatureEffect",
    "ActionTypeEnum",
    "CausalEvidence",
    "SegmentRecommendation",
    "SegmentRiskEvidence",
    "StrategyAgentInput",
    "StrategyAgentResult",
]
