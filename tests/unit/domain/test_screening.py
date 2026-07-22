from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.screening import (
    AIRecommendation,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)


def test_create_human_include_decision() -> None:
    decision = ScreeningDecision(
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        human_outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
    )

    assert decision.human_outcome is ScreeningOutcome.INCLUDE
    assert decision.reviewer_id == "reviewer-1"
    assert decision.ai_recommendation is None


def test_create_ai_only_recommendation() -> None:
    recommendation = AIRecommendation(
        outcome=ScreeningOutcome.UNCERTAIN,
        confidence=0.62,
        model_name="local-screening-model",
        rationale="Insufficient information in the abstract.",
    )
    decision = ScreeningDecision(
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        ai_recommendation=recommendation,
    )

    assert decision.human_outcome is None
    assert decision.ai_recommendation == recommendation


def test_human_and_ai_results_are_stored_separately() -> None:
    decision = ScreeningDecision(
        publication_id=uuid4(),
        stage=ScreeningStage.FULL_TEXT,
        human_outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-2",
        ai_recommendation=AIRecommendation(
            outcome=ScreeningOutcome.EXCLUDE,
            confidence=0.91,
            model_name="screening-model",
        ),
    )

    assert decision.human_outcome is ScreeningOutcome.INCLUDE
    assert decision.ai_recommendation is not None
    assert decision.ai_recommendation.outcome is ScreeningOutcome.EXCLUDE


def test_exclusion_requires_reason() -> None:
    with pytest.raises(ValidationError, match="exclusion_reason is required"):
        ScreeningDecision(
            publication_id=uuid4(),
            stage=ScreeningStage.FULL_TEXT,
            human_outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="reviewer-1",
        )


def test_non_exclusion_rejects_exclusion_reason() -> None:
    with pytest.raises(ValidationError, match="only valid for an exclusion"):
        ScreeningDecision(
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            human_outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            exclusion_reason="Wrong population",
        )


def test_human_outcome_requires_reviewer() -> None:
    with pytest.raises(ValidationError, match="reviewer_id is required"):
        ScreeningDecision(
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            human_outcome=ScreeningOutcome.UNCERTAIN,
        )


def test_decision_requires_human_or_ai_result() -> None:
    with pytest.raises(ValidationError, match="human outcome or AI recommendation"):
        ScreeningDecision(
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
        )


def test_ai_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        AIRecommendation(
            outcome=ScreeningOutcome.INCLUDE,
            confidence=1.1,
            model_name="screening-model",
        )


def test_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ScreeningDecision(
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            human_outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            decided_at=datetime(2026, 7, 22, 8, 0),
        )
