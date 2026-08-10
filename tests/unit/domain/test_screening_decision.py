from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)


def test_create_valid_include_decision() -> None:
    pub_id = uuid4()
    cid = uuid4()
    assessment = CriterionAssessment(
        criterion_id=cid,
        criterion_name="Empirical Evaluation",
        criterion_type=ScreeningCriterionType.INCLUSION,
        criterion_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        criterion_is_required=True,
        assessment_value=CriterionAssessmentValue.MET,
        notes="Strong empirical evidence provided",
    )
    decision = ScreeningDecision(
        project_id="proj-123",
        publication_id=pub_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
        rationale="Meets all inclusion criteria.",
        criterion_assessments=[assessment],
    )

    assert decision.project_id == "proj-123"
    assert decision.publication_id == pub_id
    assert decision.stage is ScreeningStage.TITLE_ABSTRACT
    assert decision.outcome is ScreeningOutcome.INCLUDE
    assert decision.reviewer_id == "reviewer-1"
    assert decision.rationale == "Meets all inclusion criteria."
    assert len(decision.criterion_assessments) == 1
    assert decision.criterion_assessments[0].criterion_id == cid
    assert decision.criterion_assessments[0].criterion_is_required is True


def test_create_valid_exclude_decision() -> None:
    decision = ScreeningDecision(
        project_id="proj-123",
        publication_id=uuid4(),
        stage=ScreeningStage.FULL_TEXT,
        outcome=ScreeningOutcome.EXCLUDE,
        reviewer_id="reviewer-2",
        rationale="Off-topic domain.",
    )
    assert decision.outcome is ScreeningOutcome.EXCLUDE
    assert decision.stage is ScreeningStage.FULL_TEXT


def test_create_valid_uncertain_decision() -> None:
    decision = ScreeningDecision(
        project_id="proj-123",
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.UNCERTAIN,
        reviewer_id="reviewer-1",
    )
    assert decision.outcome is ScreeningOutcome.UNCERTAIN


def test_reject_blank_project_id() -> None:
    with pytest.raises(ValidationError, match="text fields must not be blank"):
        ScreeningDecision(
            project_id="   ",
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
        )


def test_reject_blank_reviewer_id() -> None:
    with pytest.raises(ValidationError, match="text fields must not be blank"):
        ScreeningDecision(
            project_id="proj-1",
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="   ",
        )


def test_normalize_rationale_whitespace() -> None:
    decision = ScreeningDecision(
        project_id="proj-1",
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
        rationale="   Detailed rationale text   ",
    )
    assert decision.rationale == "Detailed rationale text"

    decision_empty = ScreeningDecision(
        project_id="proj-1",
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
        rationale="   ",
    )
    assert decision_empty.rationale is None


def test_reject_duplicate_criterion_assessments() -> None:
    cid = uuid4()
    a1 = CriterionAssessment(
        criterion_id=cid,
        criterion_name="Name 1",
        criterion_type=ScreeningCriterionType.INCLUSION,
        criterion_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        criterion_is_required=True,
        assessment_value=CriterionAssessmentValue.MET,
    )
    a2 = CriterionAssessment(
        criterion_id=cid,
        criterion_name="Name 2",
        criterion_type=ScreeningCriterionType.INCLUSION,
        criterion_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        criterion_is_required=True,
        assessment_value=CriterionAssessmentValue.NOT_MET,
    )
    with pytest.raises(ValidationError, match="Duplicate criterion assessment"):
        ScreeningDecision(
            project_id="proj-1",
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            criterion_assessments=[a1, a2],
        )


def test_reject_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ScreeningDecision(
            project_id="proj-1",
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            decided_at=datetime(2026, 8, 10, 12, 0, 0),
        )


def test_deterministic_serialization_and_deserialization() -> None:
    pub_id = uuid4()
    cid = uuid4()
    assessment = CriterionAssessment(
        criterion_id=cid,
        criterion_name="Required Inclusion Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        criterion_stage=ScreeningCriterionStage.BOTH,
        criterion_is_required=True,
        assessment_value=CriterionAssessmentValue.MET,
    )
    decision = ScreeningDecision(
        project_id="proj-999",
        publication_id=pub_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-dev",
        rationale="Solid methodology.",
        criterion_assessments=[assessment],
    )

    json_str = decision.model_dump_json()
    restored = ScreeningDecision.model_validate_json(json_str)

    assert restored.decision_id == decision.decision_id
    assert restored.project_id == "proj-999"
    assert restored.publication_id == pub_id
    assert restored.stage is ScreeningStage.TITLE_ABSTRACT
    assert restored.outcome is ScreeningOutcome.INCLUDE
    assert restored.reviewer_id == "reviewer-dev"
    assert restored.rationale == "Solid methodology."
    assert len(restored.criterion_assessments) == 1
    assert restored.criterion_assessments[0].criterion_id == cid
    assert restored.criterion_assessments[0].criterion_is_required is True
