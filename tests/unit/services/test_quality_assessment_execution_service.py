from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.author import Author
from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.domain.screening import (
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)
from app.services.quality_assessment_execution_service import (
    CriterionResponseInput,
    DefaultQualityAssessmentExecutionService,
    MissingRequiredQualityCriterionResponseError,
    NoQualityAssessmentConfigurationError,
    PublicationNotEligibleForQualityAssessmentError,
    QualityAssessmentReadinessStatus,
)


@pytest.fixture
def env(tmp_path: Path):
    db_path = tmp_path / "execution_test.db"
    project_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    decision_repo = SqliteScreeningDecisionRepository(db_path)
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)

    service = DefaultQualityAssessmentExecutionService(
        project_repo=project_repo,
        publication_repo=pub_repo,
        screening_decision_repo=decision_repo,
        catalog_repo=catalog_repo,
        config_repo=config_repo,
        quality_assessment_repo=qa_repo,
    )

    # 1. Create project & publications
    project_repo.create(Project(project_id="proj_qa", title="QA Project"))

    pub1 = Publication(record_id=uuid4(), title="Paper 1", authors=[Author(display_name="Author A")])
    pub2 = Publication(record_id=uuid4(), title="Paper 2", authors=[Author(display_name="Author B")])
    pub3 = Publication(record_id=uuid4(), title="Paper 3", authors=[Author(display_name="Author C")])

    pub_repo.add_publications("proj_qa", [pub1, pub2, pub3])

    # 2. Seed tool & template v1
    tool = QualityAssessmentTool(tool_id="casp", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid1 = uuid4()
    crit1_id = uuid4()
    crit2_id = uuid4()

    crit1 = QualityAssessmentTemplateCriterion(
        criterion_id=crit1_id,
        template_id=tid1,
        display_order=1,
        question="Did the study address a clearly focused issue?",
        guidance="Look for population, intervention, outcome",
        is_required=True,
    )
    crit2 = QualityAssessmentTemplateCriterion(
        criterion_id=crit2_id,
        template_id=tid1,
        display_order=2,
        question="Was the cohort recruited in an acceptable way?",
        guidance="Look for selection bias",
        is_required=False,
    )

    tmpl1 = QualityAssessmentTemplate(
        template_id=tid1,
        tool_id="casp",
        template_key="cohort",
        name="CASP Cohort v1",
        version=1,
        criteria=[crit1, crit2],
    )
    catalog_repo.create_template_version(tmpl1)

    # 3. Configure proj_qa to use tmpl1
    config_repo.save_configuration(
        ProjectQualityAssessmentConfiguration(
            project_id="proj_qa",
            tool_id="casp",
            template_id=tid1,
        )
    )

    return (
        service,
        project_repo,
        pub_repo,
        decision_repo,
        catalog_repo,
        config_repo,
        qa_repo,
        pub1,
        pub2,
        pub3,
        tid1,
        crit1_id,
        crit2_id,
    )


def test_full_text_eligibility_and_reviewer_isolation(env):
    service, _, _, decision_repo, _, _, _, pub1, pub2, pub3, _, _, _ = env

    # Reviewer R1: FULL_TEXT INCLUDE for pub1, EXCLUDE for pub2
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Fits inclusion criteria",
        )
    )
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub2.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.EXCLUDE,
            rationale="Wrong population",
        )
    )

    # Reviewer R2: FULL_TEXT UNCERTAIN for pub1, INCLUDE for pub2
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R2",
            outcome=ScreeningOutcome.UNCERTAIN,
            rationale="Needs discussion",
        )
    )
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub2.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R2",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Good full text",
        )
    )

    # Overview check for R1
    overview_r1 = service.get_overview("proj_qa", "rev_R1")
    assert overview_r1.readiness == QualityAssessmentReadinessStatus.READY
    assert overview_r1.total_eligible == 1
    assert overview_r1.total_assessed == 0
    assert overview_r1.total_remaining == 1

    # Overview check for R2 (pub2 is eligible for R2, NOT pub1)
    overview_r2 = service.get_overview("proj_qa", "rev_R2")
    assert overview_r2.total_eligible == 1

    # Records check for R1
    records_r1 = service.list_eligible_records("proj_qa", "rev_R1")
    assert len(records_r1.items) == 1
    assert records_r1.items[0].publication.record_id == pub1.record_id

    # Records check for R2
    records_r2 = service.list_eligible_records("proj_qa", "rev_R2")
    assert len(records_r2.items) == 1
    assert records_r2.items[0].publication.record_id == pub2.record_id

    # Non-eligible publication (pub3 has no decision) save attempt by R1 -> Rejected
    with pytest.raises(PublicationNotEligibleForQualityAssessmentError):
        service.save_assessment("proj_qa", pub3.record_id, "rev_R1", [])


def test_loss_and_restoration_of_eligibility(env):
    service, _, _, decision_repo, _, _, _, pub1, _, _, _, crit1_id, _ = env

    # 1. R1 FULL_TEXT INCLUDE for pub1
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Include initially",
        )
    )

    # Save Quality Assessment while eligible
    qa1 = service.save_assessment(
        project_id="proj_qa",
        publication_id=pub1.record_id,
        reviewer_id="rev_R1",
        response_inputs=[
            CriterionResponseInput(
                criterion_id=crit1_id,
                response_value=QualityAssessmentResponseValue.YES,
                justification="Clear focus",
            )
        ],
    )
    assert qa1.assessment_id is not None

    # 2. Decision changes to EXCLUDE
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.EXCLUDE,
            rationale="Discovered flaw upon re-read",
        )
    )

    # Pub1 disappears from current eligible records queue
    records = service.list_eligible_records("proj_qa", "rev_R1")
    assert len(records.items) == 0

    # Historical assessment remains 100% intact and readable
    history = service.get_assessment_history("proj_qa", pub1.record_id, "rev_R1")
    assert len(history) == 1
    assert history[0].assessment_id == qa1.assessment_id

    # Attempting new save while EXCLUDE is rejected
    with pytest.raises(PublicationNotEligibleForQualityAssessmentError):
        service.save_assessment(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            reviewer_id="rev_R1",
            response_inputs=[
                CriterionResponseInput(
                    criterion_id=crit1_id,
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="Flawed",
                )
            ],
        )

    # 3. Decision restored to INCLUDE
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Re-included after consensus",
        )
    )

    # Pub1 reappears in current QA queue with previous assessment
    records_restored = service.list_eligible_records("proj_qa", "rev_R1")
    assert len(records_restored.items) == 1
    assert records_restored.items[0].has_assessment is True


def test_missing_qa_configuration_blocks_readiness_and_save(env):
    service, _, _, decision_repo, _, config_repo, _, pub1, _, _, _, crit1_id, _ = env

    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Include",
        )
    )

    # Delete configuration
    config_repo.delete_for_project("proj_qa")

    # Readiness reflects missing config
    readiness = service.check_readiness("proj_qa", "rev_R1")
    assert readiness == QualityAssessmentReadinessStatus.NO_QUALITY_ASSESSMENT_CONFIGURATION

    # Save is blocked with NoQualityAssessmentConfigurationError
    with pytest.raises(NoQualityAssessmentConfigurationError):
        service.save_assessment(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            reviewer_id="rev_R1",
            response_inputs=[
                CriterionResponseInput(
                    criterion_id=crit1_id,
                    response_value=QualityAssessmentResponseValue.YES,
                    justification="Clear focus",
                )
            ],
        )


def test_assessment_save_completeness_and_validation(env):
    service, _, _, decision_repo, _, _, _, pub1, _, _, _, crit1_id, crit2_id = env

    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Include",
        )
    )

    # 1. Missing required criterion (crit1_id is required)
    with pytest.raises(MissingRequiredQualityCriterionResponseError):
        service.save_assessment("proj_qa", pub1.record_id, "rev_R1", [])

    # 2. Blank justification rejected for NO / CANNOT_DETERMINE
    with pytest.raises(ValueError, match="justification"):
        service.save_assessment(
            "proj_qa",
            pub1.record_id,
            "rev_R1",
            [
                CriterionResponseInput(
                    criterion_id=crit1_id,
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="   ",
                )
            ],
        )

    # 2b. Empty justification accepted for YES
    saved_yes = service.save_assessment(
        "proj_qa",
        pub1.record_id,
        "rev_R1",
        [
            CriterionResponseInput(
                criterion_id=crit1_id,
                response_value=QualityAssessmentResponseValue.YES,
                justification="",
            )
        ],
    )
    assert saved_yes is not None
    assert saved_yes.responses[0].justification == ""

    # 3. Duplicate criterion response rejected
    with pytest.raises(ValueError, match="Duplicate"):
        service.save_assessment(
            "proj_qa",
            pub1.record_id,
            "rev_R1",
            [
                CriterionResponseInput(
                    criterion_id=crit1_id,
                    response_value=QualityAssessmentResponseValue.YES,
                    justification="Justification 1",
                ),
                CriterionResponseInput(
                    criterion_id=crit1_id,
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="Justification 2",
                ),
            ],
        )

    # 4. Valid assessment save (YES, NO, CANNOT_DETERMINE allowed)
    qa = service.save_assessment(
        "proj_qa",
        pub1.record_id,
        "rev_R1",
        [
            CriterionResponseInput(
                criterion_id=crit1_id,
                response_value=QualityAssessmentResponseValue.YES,
                justification="Focused population",
            ),
            CriterionResponseInput(
                criterion_id=crit2_id,
                response_value=QualityAssessmentResponseValue.CANNOT_DETERMINE,
                justification="Selection details omitted in paper",
            ),
        ],
    )
    assert qa.assessment_id is not None
    assert len(qa.responses) == 2


def test_append_only_save_and_template_version_binding(env):
    service, _, _, decision_repo, catalog_repo, config_repo, _, pub1, _, _, tid1, crit1_id, _ = env

    decision_repo.save(
        ScreeningDecision(
            project_id="proj_qa",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_R1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Include",
        )
    )

    # 1. Save initial assessment under template v1
    qa_v1 = service.save_assessment(
        "proj_qa",
        pub1.record_id,
        "rev_R1",
        [
            CriterionResponseInput(
                criterion_id=crit1_id,
                response_value=QualityAssessmentResponseValue.YES,
                justification="Assessment 1 under v1",
            )
        ],
    )
    assert qa_v1.template_id == tid1

    # 2. Upgrade template config to v2
    tid2 = uuid4()
    crit1_v2_id = uuid4()
    crit1_v2 = QualityAssessmentTemplateCriterion(
        criterion_id=crit1_v2_id,
        template_id=tid2,
        display_order=1,
        question="Did the study address a clearly focused issue? (v2)",
        is_required=True,
    )
    tmpl2 = QualityAssessmentTemplate(
        template_id=tid2,
        tool_id="casp",
        template_key="cohort",
        name="CASP Cohort v2",
        version=2,
        criteria=[crit1_v2],
    )
    catalog_repo.create_template_version(tmpl2)

    config_repo.save_configuration(
        ProjectQualityAssessmentConfiguration(
            project_id="proj_qa",
            tool_id="casp",
            template_id=tid2,
        )
    )

    # 3. Save second assessment (re-assessment under v2)
    qa_v2 = service.save_assessment(
        "proj_qa",
        pub1.record_id,
        "rev_R1",
        [
            CriterionResponseInput(
                criterion_id=crit1_v2_id,
                response_value=QualityAssessmentResponseValue.NO,
                justification="Assessment 2 under v2",
            )
        ],
    )
    assert qa_v2.template_id == tid2
    assert qa_v2.assessment_id != qa_v1.assessment_id

    # 4. History check: Both assessments exist, ordered latest first
    history = service.get_assessment_history("proj_qa", pub1.record_id, "rev_R1")
    assert len(history) == 2
    assert history[0].template_id == tid2
    assert history[1].template_id == tid1
