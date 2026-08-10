from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.screening import (
    AIRecommendation,
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)


def test_create_human_include_decision() -> None:
    decision = ScreeningDecision(
        project_id="proj-1",
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
    )

    assert decision.project_id == "proj-1"
    assert decision.outcome is ScreeningOutcome.INCLUDE
    assert decision.reviewer_id == "reviewer-1"


def test_reject_blank_project_id_for_decision() -> None:
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
            project_id="proj-1",
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            decided_at=datetime(2026, 7, 22, 8, 0),
        )


# --- ScreeningCriterion Unit Tests ---


def test_create_valid_screening_criterion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-123",
        name="Empirical Evaluation",
        description="Must present empirical user evaluation.",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        display_order=1,
    )
    assert criterion.project_id == "proj-123"
    assert criterion.name == "Empirical Evaluation"
    assert criterion.description == "Must present empirical user evaluation."
    assert criterion.criterion_type is ScreeningCriterionType.INCLUSION
    assert criterion.screening_stage is ScreeningCriterionStage.TITLE_ABSTRACT
    assert criterion.display_order == 1
    assert criterion.is_active is True
    assert criterion.is_required is True


def test_criterion_type_inclusion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Inclusion Test",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    assert criterion.criterion_type == ScreeningCriterionType.INCLUSION


def test_criterion_type_exclusion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Exclusion Test",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
    )
    assert criterion.criterion_type == ScreeningCriterionType.EXCLUSION


def test_screening_stage_title_abstract() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Title & Abstract Stage",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    assert criterion.screening_stage == ScreeningCriterionStage.TITLE_ABSTRACT


def test_screening_stage_full_text() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Full Text Stage",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
    )
    assert criterion.screening_stage == ScreeningCriterionStage.FULL_TEXT


def test_screening_stage_both() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Both Stages",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
    )
    assert criterion.screening_stage == ScreeningCriterionStage.BOTH


def test_required_criterion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Required Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        is_required=True,
    )
    assert criterion.is_required is True


def test_optional_criterion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Optional Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        is_required=False,
    )
    assert criterion.is_required is False


def test_active_criterion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Active Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
    )
    assert criterion.is_active is True


def test_inactive_criterion() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Inactive Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=False,
    )
    assert criterion.is_active is False


def test_display_order_zero() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Order Zero",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        display_order=0,
    )
    assert criterion.display_order == 0


def test_display_order_positive() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Order Positive",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        display_order=10,
    )
    assert criterion.display_order == 10


def test_reject_negative_display_order() -> None:
    with pytest.raises(ValidationError):
        ScreeningCriterion(
            project_id="proj-1",
            name="Negative Order",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
            display_order=-1,
        )


def test_explicit_and_default_criterion_id() -> None:
    # Test default UUID generation
    criterion_default = ScreeningCriterion(
        project_id="proj-1",
        name="Default ID",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    assert criterion_default.criterion_id is not None

    # Test explicit UUID passing
    explicit_id = uuid4()
    criterion_explicit = ScreeningCriterion(
        criterion_id=explicit_id,
        project_id="proj-1",
        name="Explicit ID",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    assert criterion_explicit.criterion_id == explicit_id


def test_reject_invalid_criterion_id_uuid() -> None:
    with pytest.raises(ValidationError):
        ScreeningCriterion(
            criterion_id="invalid-uuid-string",  # type: ignore[arg-type]
            project_id="proj-1",
            name="Invalid UUID",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )


def test_reject_blank_project_id() -> None:
    with pytest.raises(ValidationError, match="text fields must not be blank"):
        ScreeningCriterion(
            project_id="   ",
            name="Blank Project",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )


def test_reject_blank_name() -> None:
    with pytest.raises(ValidationError, match="text fields must not be blank"):
        ScreeningCriterion(
            project_id="proj-1",
            name="   ",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )


def test_trim_normalization_name_and_description() -> None:
    criterion = ScreeningCriterion(
        project_id="  proj-1  ",
        name="  Trimmed Name  ",
        description="   Trimmed Description   ",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    assert criterion.project_id == "proj-1"
    assert criterion.name == "Trimmed Name"
    assert criterion.description == "Trimmed Description"

    # Blank whitespace description normalizes to None
    criterion_empty_desc = ScreeningCriterion(
        project_id="proj-1",
        name="Name",
        description="   ",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    assert criterion_empty_desc.description is None


def test_deterministic_serialization() -> None:
    cid = uuid4()
    criterion = ScreeningCriterion(
        criterion_id=cid,
        project_id="proj-123",
        name="Empirical Study",
        description="Must be empirical.",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        display_order=5,
        is_active=True,
        is_required=False,
    )
    data_dict = criterion.model_dump()
    assert data_dict["criterion_id"] == cid
    assert data_dict["project_id"] == "proj-123"
    assert data_dict["name"] == "Empirical Study"
    assert data_dict["criterion_type"] == "inclusion"
    assert data_dict["screening_stage"] == "both"
    assert data_dict["display_order"] == 5

    data_json = criterion.model_dump_json()
    assert f'"criterion_id":"{cid}"' in data_json or f'"criterion_id": "{cid}"' in data_json
    assert '"criterion_type":"inclusion"' in data_json or '"criterion_type": "inclusion"' in data_json
    assert '"screening_stage":"both"' in data_json or '"screening_stage": "both"' in data_json


def test_enum_serialization_values() -> None:
    criterion = ScreeningCriterion(
        project_id="proj-1",
        name="Enum Check",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
    )
    assert criterion.criterion_type.value == "exclusion"
    assert criterion.screening_stage.value == "full_text"


def test_project_scoped_identity_stability() -> None:
    cid = uuid4()
    c1 = ScreeningCriterion(
        criterion_id=cid,
        project_id="proj-100",
        name="Original Name",
        description="Original Description",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )

    c2 = ScreeningCriterion(
        criterion_id=cid,
        project_id="proj-100",
        name="Updated Name",
        description="Updated Description",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )

    assert c1.criterion_id == c2.criterion_id == cid
    assert c1.project_id == c2.project_id == "proj-100"
    assert c1.name != c2.name
