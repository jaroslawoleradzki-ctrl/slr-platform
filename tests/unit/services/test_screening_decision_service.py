from uuid import uuid4

import pytest

from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.screening_criterion_repository import (
    SqliteScreeningCriterionRepository,
)
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.services.screening_decision_service import (
    CriterionAssessmentInput,
    ScreeningDecisionService,
)


@pytest.fixture
def service(tmp_path) -> ScreeningDecisionService:
    db_path = tmp_path / "test_service.db"
    pub_repo = SqliteProjectPublicationRepository(db_path)
    crit_repo = SqliteScreeningCriterionRepository(db_path)
    dec_repo = SqliteScreeningDecisionRepository(db_path)
    return ScreeningDecisionService(
        decision_repository=dec_repo,
        criterion_repository=crit_repo,
        publication_repository=pub_repo,
    )


def test_record_valid_decision_with_authoritative_assessment(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"

    # Add publication to working collection
    pub = Publication(title="Empirical Paper on Systematic Reviews")
    service.publication_repo.add_publications(project_id, [pub])

    # Add active criterion
    criterion = ScreeningCriterion(
        project_id=project_id,
        name="Empirical Method",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
        is_required=True,
    )
    service.criterion_repo.create(criterion)

    # Record decision via service passing lightweight assessment input
    input_assessment = CriterionAssessmentInput(
        criterion_id=criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.MET,
        notes="Empirical method is clearly described",
    )

    decision = service.record_decision(
        project_id=project_id,
        publication_id=pub.record_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
        rationale="All criteria met",
        assessment_inputs=[input_assessment],
    )

    assert decision.project_id == project_id
    assert decision.publication_id == pub.record_id
    assert decision.outcome is ScreeningOutcome.INCLUDE
    assert len(decision.criterion_assessments) == 1

    # Check authoritative snapshot populated server-side
    snapshot = decision.criterion_assessments[0]
    assert snapshot.criterion_id == criterion.criterion_id
    assert snapshot.criterion_name == "Empirical Method"
    assert snapshot.criterion_type is ScreeningCriterionType.INCLUSION
    assert snapshot.criterion_stage is ScreeningCriterionStage.TITLE_ABSTRACT
    assert snapshot.criterion_is_required is True
    assert snapshot.assessment_value is CriterionAssessmentValue.MET
    assert snapshot.notes == "Empirical method is clearly described"


def test_reject_publication_not_in_project(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    with pytest.raises(ValueError, match="Publication .* not found in project"):
        service.record_decision(
            project_id=project_id,
            publication_id=uuid4(),
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
        )


def test_reject_criterion_belonging_to_other_project(
    service: ScreeningDecisionService,
) -> None:
    project_id_1 = "lean_energy"
    project_id_2 = "ai_architecture"

    pub = Publication(title="Paper in project 1")
    service.publication_repo.add_publications(project_id_1, [pub])

    # Criterion created in project 2
    foreign_criterion = ScreeningCriterion(
        project_id=project_id_2,
        name="Foreign Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
    )
    service.criterion_repo.create(foreign_criterion)

    input_assessment = CriterionAssessmentInput(
        criterion_id=foreign_criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.MET,
    )

    with pytest.raises(ValueError, match="Criterion .* not found in project"):
        service.record_decision(
            project_id=project_id_1,
            publication_id=pub.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            assessment_inputs=[input_assessment],
        )


def test_reject_inactive_criterion_in_new_decision(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    pub = Publication(title="Paper")
    service.publication_repo.add_publications(project_id, [pub])

    criterion = ScreeningCriterion(
        project_id=project_id,
        name="Legacy Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=False,
    )
    service.criterion_repo.create(criterion)

    input_assessment = CriterionAssessmentInput(
        criterion_id=criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.MET,
    )

    with pytest.raises(ValueError, match="Cannot assess inactive criterion"):
        service.record_decision(
            project_id=project_id,
            publication_id=pub.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            assessment_inputs=[input_assessment],
        )


def test_reject_stage_incompatible_criterion(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    pub = Publication(title="Paper")
    service.publication_repo.add_publications(project_id, [pub])

    criterion_fulltext = ScreeningCriterion(
        project_id=project_id,
        name="Full Text Only Criterion",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
        is_active=True,
    )
    service.criterion_repo.create(criterion_fulltext)

    input_assessment = CriterionAssessmentInput(
        criterion_id=criterion_fulltext.criterion_id,
        assessment_value=CriterionAssessmentValue.NOT_MET,
    )

    # Attempt assessing full_text criterion during TITLE_ABSTRACT decision
    with pytest.raises(ValueError, match="is incompatible with decision stage"):
        service.record_decision(
            project_id=project_id,
            publication_id=pub.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            assessment_inputs=[input_assessment],
        )


def test_reject_missing_required_criterion_assessment(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    pub = Publication(title="Paper")
    service.publication_repo.add_publications(project_id, [pub])

    req_criterion = ScreeningCriterion(
        project_id=project_id,
        name="Required Topic Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
        is_required=True,
    )
    service.criterion_repo.create(req_criterion)

    # Attempt decision without providing assessment for required criterion
    with pytest.raises(ValueError, match="Missing required assessment"):
        service.record_decision(
            project_id=project_id,
            publication_id=pub.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            assessment_inputs=[],
        )


def test_reject_not_assessed_for_required_criterion(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    pub = Publication(title="Paper")
    service.publication_repo.add_publications(project_id, [pub])

    req_criterion = ScreeningCriterion(
        project_id=project_id,
        name="Required Topic Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
        is_required=True,
    )
    service.criterion_repo.create(req_criterion)

    input_assessment = CriterionAssessmentInput(
        criterion_id=req_criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.NOT_ASSESSED,
    )

    with pytest.raises(ValueError, match="Missing required assessment"):
        service.record_decision(
            project_id=project_id,
            publication_id=pub.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            assessment_inputs=[input_assessment],
        )


def test_reject_duplicate_criterion_assessment_input(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    pub = Publication(title="Paper")
    service.publication_repo.add_publications(project_id, [pub])

    criterion = ScreeningCriterion(
        project_id=project_id,
        name="Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
    )
    service.criterion_repo.create(criterion)

    a1 = CriterionAssessmentInput(
        criterion_id=criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.MET,
    )
    a2 = CriterionAssessmentInput(
        criterion_id=criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.NOT_MET,
    )

    with pytest.raises(ValueError, match="Duplicate assessment input"):
        service.record_decision(
            project_id=project_id,
            publication_id=pub.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer-1",
            assessment_inputs=[a1, a2],
        )


def test_final_outcome_is_not_derived_automatically(
    service: ScreeningDecisionService,
) -> None:
    project_id = "lean_energy"
    pub = Publication(title="Paper")
    service.publication_repo.add_publications(project_id, [pub])

    excl_criterion = ScreeningCriterion(
        project_id=project_id,
        name="Language Exclusion",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
        is_required=True,
    )
    service.criterion_repo.create(excl_criterion)

    # Exclusion criterion is MET (exclusion applies), but reviewer explicitly selects UNCERTAIN outcome for further review
    input_assessment = CriterionAssessmentInput(
        criterion_id=excl_criterion.criterion_id,
        assessment_value=CriterionAssessmentValue.MET,
        notes="Non-English abstract, flag for translator",
    )

    decision = service.record_decision(
        project_id=project_id,
        publication_id=pub.record_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.UNCERTAIN,
        reviewer_id="reviewer-1",
        rationale="Needs language confirmation",
        assessment_inputs=[input_assessment],
    )

    # Outcome remains UNCERTAIN as explicitly provided by reviewer
    assert decision.outcome is ScreeningOutcome.UNCERTAIN
    assert decision.criterion_assessments[0].assessment_value is CriterionAssessmentValue.MET
