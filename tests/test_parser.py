"""Tests for recommendation parser."""

import pytest
from datetime import datetime, timezone, timedelta

from action_agent.core.parser import RecommendationParser, ParseError


class TestRecommendationParser:
    """Tests for RecommendationParser."""

    def test_parse_valid_payload(self, valid_ux_payload):
        parser = RecommendationParser()
        rec = parser.parse(valid_ux_payload)
        assert rec.recommendation_id == "rec_test_001"
        assert rec.confidence == 0.91
        assert rec.recommended_action.type == "ux_experiment"

    def test_parse_minimal_payload(self):
        parser = RecommendationParser()
        payload = {
            "recommendation_id": "rec_min",
            "confidence": 0.7,
            "recommended_action": {
                "type": "alert",
                "target": "test",
                "description": "minimal test",
            },
        }
        rec = parser.parse(payload)
        assert rec.recommendation_id == "rec_min"
        assert rec.customer_segment == "all"  # default

    def test_parse_missing_required_field(self):
        parser = RecommendationParser()
        with pytest.raises(ParseError, match="validation error"):
            parser.parse({"confidence": 0.5})  # missing recommendation_id, recommended_action

    def test_parse_invalid_confidence(self):
        parser = RecommendationParser()
        with pytest.raises(ParseError):
            parser.parse({
                "recommendation_id": "rec_bad",
                "confidence": 1.5,  # out of range
                "recommended_action": {"type": "alert", "target": "x", "description": "y"},
            })

    def test_parse_expired_recommendation(self):
        parser = RecommendationParser()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with pytest.raises(ParseError, match="expired"):
            parser.parse({
                "recommendation_id": "rec_expired",
                "confidence": 0.8,
                "recommended_action": {"type": "alert", "target": "x", "description": "y"},
                "expires_at": past,
            })
