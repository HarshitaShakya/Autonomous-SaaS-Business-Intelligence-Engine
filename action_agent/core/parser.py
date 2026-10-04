"""Recommendation parser.

Validates and normalises a raw StrategyRecommendation into a
consistent internal form, catching malformed payloads early.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from action_agent.schemas.recommendation import StrategyRecommendation


class ParseError(Exception):
    """Raised when a recommendation payload cannot be parsed."""

    def __init__(self, message: str, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class RecommendationParser:
    """Parses and validates raw recommendation payloads."""

    def parse(self, raw: dict) -> StrategyRecommendation:
        """Convert a dict payload into a validated StrategyRecommendation.

        Raises ParseError on invalid input with structured detail.
        """
        try:
            rec = StrategyRecommendation.model_validate(raw)
        except ValidationError as exc:
            raise ParseError(
                message=f"Invalid recommendation payload: {exc.error_count()} validation error(s)",
                details=[
                    {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                    for e in exc.errors()
                ],
            ) from exc

        # Check expiry
        if rec.expires_at is not None:
            now = datetime.now(timezone.utc)
            expires = rec.expires_at
            # Ensure both are offset-aware
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < now:
                raise ParseError(
                    message=f"Recommendation '{rec.recommendation_id}' has expired "
                    f"(expired at {rec.expires_at.isoformat()})."
                )

        return rec
