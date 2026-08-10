from uuid import uuid4

import pytest

from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    MetadataRule,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.services.screening_decision_service import CriterionAssessmentInput, ScreeningDecisionService


def _service(tmp_path, publication: Publication):
    database = tmp_path / "decisions.db"
    publications = SqliteProjectPublicationRepository(database)
    publications.add_publications("lean_energy", [publication])
    criteria = SqliteScreeningCriterionRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    return criteria, decisions, ScreeningDecisionService(decisions, criteria, publications)


def _automatic(*, required: bool = True) -> ScreeningCriterion:
    return ScreeningCriterion(
        project_id="lean_energy",
        name="Published after 2021",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_required=required,
        evaluation_mode=ScreeningCriterionEvaluationMode.METADATA_RULE,
        metadata_rule=MetadataRule(field="publication_year", operator="greater_than", value=2021),
    )


def test_automatic_assessment_is_server_generated_and_auditable(tmp_path) -> None:
    publication = Publication(record_id=uuid4(), title="Record", publication_year=2024)
    criteria, decisions, service = _service(tmp_path, publication)
    automatic = criteria.create(_automatic())
    manual = criteria.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Manual relevance",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )
    )

    decision = service.record_decision(
        "lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT,
        ScreeningOutcome.INCLUDE, "reviewer", assessment_inputs=[
            CriterionAssessmentInput(criterion_id=manual.criterion_id, assessment_value=CriterionAssessmentValue.MET)
        ],
    )
    automatic_snapshot = next(item for item in decision.criterion_assessments if item.criterion_id == automatic.criterion_id)
    assert automatic_snapshot.assessment_value is CriterionAssessmentValue.MET
    assert automatic_snapshot.evaluation_mode is ScreeningCriterionEvaluationMode.METADATA_RULE
    assert automatic_snapshot.metadata_rule == automatic.metadata_rule
    assert automatic_snapshot.evaluated_metadata_value == 2024
    assert decisions.get("lean_energy", decision.decision_id) == decision


def test_client_cannot_spoof_automatic_assessment(tmp_path) -> None:
    publication = Publication(record_id=uuid4(), title="Record", publication_year=2020)
    criteria, _decisions, service = _service(tmp_path, publication)
    automatic = criteria.create(_automatic())

    with pytest.raises(ValueError, match="evaluated server-side"):
        service.record_decision(
            "lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT,
            ScreeningOutcome.INCLUDE, "reviewer", assessment_inputs=[
                CriterionAssessmentInput(criterion_id=automatic.criterion_id, assessment_value=CriterionAssessmentValue.MET)
            ],
        )


def test_required_automatic_criterion_with_missing_metadata_blocks_decision(tmp_path) -> None:
    publication = Publication(record_id=uuid4(), title="Record")
    criteria, _decisions, service = _service(tmp_path, publication)
    criteria.create(_automatic(required=True))

    with pytest.raises(ValueError, match="Missing required assessment"):
        service.record_decision(
            "lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT,
            ScreeningOutcome.UNCERTAIN, "reviewer",
        )
