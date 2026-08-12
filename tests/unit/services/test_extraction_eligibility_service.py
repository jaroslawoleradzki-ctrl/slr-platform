"""Unit tests for ExtractionEligibilityService (Phase 9.3)."""

from uuid import UUID, uuid4

import pytest

from app.domain.extraction import (
    ExtractionEligibilityStatus,
    ExtractionFieldDefinition,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    FieldDataType,
)
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import Project, SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services.extraction_configuration_service import ExtractionConfigurationService
from app.services.extraction_eligibility_service import ExtractionEligibilityService
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.screening_input_service import ScreeningInputService


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_eligibility.db"


@pytest.fixture
def project_repo(temp_db):
    return SqliteProjectRepository(temp_db)


@pytest.fixture
def template_repo(temp_db):
    return SqliteExtractionTemplateRepository(temp_db)


@pytest.fixture
def extraction_repo(temp_db):
    return SqliteExtractionRepository(temp_db)


@pytest.fixture
def pub_repo(temp_db):
    return SqliteProjectPublicationRepository(temp_db)


@pytest.fixture
def decision_repo(temp_db):
    return SqliteScreeningDecisionRepository(temp_db)


@pytest.fixture
def conflict_repo(temp_db):
    return SqliteConflictResolutionRepository(temp_db)


@pytest.fixture
def assignment_repo(temp_db):
    return SqliteScreeningReviewerAssignmentRepository(temp_db)


@pytest.fixture
def config_service(extraction_repo, template_repo, project_repo):
    return ExtractionConfigurationService(
        extraction_repo=extraction_repo,
        template_repo=template_repo,
        project_repo=project_repo,
    )


@pytest.fixture
def reporting_repo(temp_db):
    return ScreeningReportingRepository(temp_db)


@pytest.fixture
def multi_reviewer_service(assignment_repo, conflict_repo, input_service, reporting_repo):
    return MultiReviewerScreeningService(
        assignments=assignment_repo,
        resolutions=conflict_repo,
        input_service=input_service,
        reporting=reporting_repo,
    )


@pytest.fixture
def input_service(pub_repo):
    return ScreeningInputService(
        publication_repository=pub_repo,
    )


@pytest.fixture
def eligibility_service(config_service, input_service, multi_reviewer_service, decision_repo):
    return ExtractionEligibilityService(
        config_service=config_service,
        input_service=input_service,
        multi_reviewer_service=multi_reviewer_service,
        decisions_repo=decision_repo,
        qa_completion_reader=MockQACompletionReader(configured_projects=set(), completed=set()),
    )


@pytest.fixture
def setup_configured_project(project_repo, template_repo, config_service):
    p = Project(project_id="proj_elig", title="Eligible Proj", description="Test")
    project_repo.create(p)

    tmpl = ExtractionTemplate(template_id="t1", name="Template 1")
    template_repo.register_template(tmpl)
    ver = ExtractionTemplateVersion(
        template_id="t1",
        version="1.0.0",
        name="v1",
        is_active=True,
        is_published=True,
        publication_fields=[
            ExtractionFieldDefinition(field_key="k1", name="Key 1", data_type=FieldDataType.TEXT)
        ],
    )
    template_repo.register_version(ver)
    config_service.set_configuration("proj_elig", "t1", "1.0.0")
    return p


class MockQACompletionReader:
    def __init__(
        self,
        configured_projects: set[str],
        completed: set[tuple[str, UUID, str]],
    ) -> None:
        self.configured_projects = configured_projects
        self.completed = completed

    def is_configured(self, project_id: str) -> bool:
        return project_id in self.configured_projects

    def has_completed_assessment(
        self, project_id: str, publication_id: UUID, reviewer_id: str
    ) -> bool:
        return (project_id, publication_id, reviewer_id) in self.completed


class TestExtractionEligibilityService:
    def test_unconfigured_project_returns_no_extraction_configuration(
        self, eligibility_service, project_repo, pub_repo
    ):
        p = Project(project_id="proj_no_cfg", title="No Cfg", description="Test")
        project_repo.create(p)
        pub_id = uuid4()
        pub_repo.add_publications("proj_no_cfg", [Publication(record_id=pub_id, title="Test Pub")])

        res = eligibility_service.evaluate_publication("proj_no_cfg", pub_id)
        assert res.is_eligible is False
        assert res.status == ExtractionEligibilityStatus.NO_EXTRACTION_CONFIGURATION

    def test_single_reviewer_full_text_include_is_eligible(
        self, eligibility_service, setup_configured_project, pub_repo, decision_repo
    ):
        pub_id = uuid4()
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_id, title="Included Pub")])

        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )

        res = eligibility_service.evaluate_publication("proj_elig", pub_id, reviewer_id="rev_1")
        assert res.is_eligible is True
        assert res.status == ExtractionEligibilityStatus.ELIGIBLE

    def test_single_reviewer_full_text_exclude_or_uncertain_blocked(
        self, eligibility_service, setup_configured_project, pub_repo, decision_repo
    ):
        pub_ex = uuid4()
        pub_unc = uuid4()
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_ex, title="Excluded Pub")])
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_unc, title="Uncertain Pub")])

        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_ex,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.EXCLUDE,
            )
        )
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_unc,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.UNCERTAIN,
            )
        )

        res_ex = eligibility_service.evaluate_publication("proj_elig", pub_ex, reviewer_id="rev_1")
        assert res_ex.is_eligible is False
        assert res_ex.status == ExtractionEligibilityStatus.BLOCKED_SCREENING_EXCLUDED

        res_unc = eligibility_service.evaluate_publication("proj_elig", pub_unc, reviewer_id="rev_1")
        assert res_unc.is_eligible is False
        assert res_unc.status == ExtractionEligibilityStatus.BLOCKED_SCREENING_UNCERTAIN

    def test_multi_reviewer_agreement_include_is_eligible(
        self, eligibility_service, setup_configured_project, pub_repo, decision_repo, assignment_repo
    ):
        pub_id = uuid4()
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_id, title="Multi Agreement Pub")])

        assignment_repo.replace_active("proj_elig", ScreeningStage.FULL_TEXT, ["rev_1", "rev_2"])
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                reviewer_id="rev_2",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )
        d1 = ScreeningDecision(
            project_id="proj_elig",
            publication_id=pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.INCLUDE,
        )
        d2 = ScreeningDecision(
            project_id="proj_elig",
            publication_id=pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_2",
            outcome=ScreeningOutcome.INCLUDE,
        )
        decision_repo.save(d1)
        decision_repo.save(d2)

        res = eligibility_service.evaluate_publication("proj_elig", pub_id)
        assert res.is_eligible is True
        assert res.status == ExtractionEligibilityStatus.ELIGIBLE

    def test_multi_reviewer_conflict_blocked(
        self, eligibility_service, setup_configured_project, pub_repo, decision_repo, assignment_repo
    ):
        pub_id = uuid4()
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_id, title="Conflict Pub")])

        assignment_repo.replace_active("proj_elig", ScreeningStage.FULL_TEXT, ["rev_1", "rev_2"])
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                reviewer_id="rev_2",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_2",
                outcome=ScreeningOutcome.EXCLUDE,
            )
        )

        res = eligibility_service.evaluate_publication("proj_elig", pub_id)
        assert res.is_eligible is False
        assert res.status == ExtractionEligibilityStatus.BLOCKED_SCREENING_CONFLICT

    def test_qa_configured_and_incomplete_blocked(
        self, config_service, input_service, multi_reviewer_service, decision_repo, setup_configured_project, pub_repo
    ):
        pub_id = uuid4()
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_id, title="QA Required Pub")])
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )

        qa_reader = MockQACompletionReader(
            configured_projects={"proj_elig"}, completed=set()
        )
        svc = ExtractionEligibilityService(
            config_service=config_service,
            input_service=input_service,
            multi_reviewer_service=multi_reviewer_service,
            decisions_repo=decision_repo,
            qa_completion_reader=qa_reader,
        )

        res = svc.evaluate_publication("proj_elig", pub_id, reviewer_id="rev_1")
        assert res.is_eligible is False
        assert res.status == ExtractionEligibilityStatus.BLOCKED_QA_INCOMPLETE

    def test_qa_configured_and_completed_eligible(
        self, config_service, input_service, multi_reviewer_service, decision_repo, setup_configured_project, pub_repo
    ):
        pub_id = uuid4()
        pub_repo.add_publications("proj_elig", [Publication(record_id=pub_id, title="QA Completed Pub")])
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )

        qa_reader = MockQACompletionReader(
            configured_projects={"proj_elig"},
            completed={("proj_elig", pub_id, "rev_1")},
        )
        svc = ExtractionEligibilityService(
            config_service=config_service,
            input_service=input_service,
            multi_reviewer_service=multi_reviewer_service,
            decisions_repo=decision_repo,
            qa_completion_reader=qa_reader,
        )

        res = svc.evaluate_publication("proj_elig", pub_id, reviewer_id="rev_1")
        assert res.is_eligible is True
        assert res.status == ExtractionEligibilityStatus.ELIGIBLE

    def test_qa_completion_is_reviewer_project_and_publication_scoped(
        self,
        config_service,
        input_service,
        multi_reviewer_service,
        decision_repo,
        setup_configured_project,
        pub_repo,
    ):
        publication_id = uuid4()
        other_publication_id = uuid4()
        pub_repo.add_publications(
            "proj_elig",
            [
                Publication(record_id=publication_id, title="Scoped QA"),
                Publication(record_id=other_publication_id, title="Other publication"),
            ],
        )
        for reviewer_id in ("rev_1", "rev_2"):
            decision_repo.save(
                ScreeningDecision(
                    project_id="proj_elig",
                    publication_id=publication_id,
                    stage=ScreeningStage.FULL_TEXT,
                    reviewer_id=reviewer_id,
                    outcome=ScreeningOutcome.INCLUDE,
                )
            )

        qa_reader = MockQACompletionReader(
            configured_projects={"proj_elig", "other-project"},
            completed={
                ("proj_elig", publication_id, "rev_1"),
                ("proj_elig", other_publication_id, "rev_2"),
                ("other-project", publication_id, "rev_2"),
            },
        )
        service = ExtractionEligibilityService(
            config_service=config_service,
            input_service=input_service,
            multi_reviewer_service=multi_reviewer_service,
            decisions_repo=decision_repo,
            qa_completion_reader=qa_reader,
        )

        assert service.evaluate_publication(
            "proj_elig", publication_id, reviewer_id="rev_1"
        ).is_eligible
        blocked = service.evaluate_publication(
            "proj_elig", publication_id, reviewer_id="rev_2"
        )
        assert blocked.is_eligible is False
        assert blocked.status is ExtractionEligibilityStatus.BLOCKED_QA_INCOMPLETE

    def test_screening_exclusion_wins_even_when_qa_is_complete(
        self,
        config_service,
        input_service,
        multi_reviewer_service,
        decision_repo,
        setup_configured_project,
        pub_repo,
    ):
        publication_id = uuid4()
        pub_repo.add_publications(
            "proj_elig", [Publication(record_id=publication_id, title="Excluded")]
        )
        decision_repo.save(
            ScreeningDecision(
                project_id="proj_elig",
                publication_id=publication_id,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_1",
                outcome=ScreeningOutcome.EXCLUDE,
            )
        )
        service = ExtractionEligibilityService(
            config_service=config_service,
            input_service=input_service,
            multi_reviewer_service=multi_reviewer_service,
            decisions_repo=decision_repo,
            qa_completion_reader=MockQACompletionReader(
                configured_projects={"proj_elig"},
                completed={("proj_elig", publication_id, "rev_1")},
            ),
        )

        result = service.evaluate_publication(
            "proj_elig", publication_id, reviewer_id="rev_1"
        )
        assert result.is_eligible is False
        assert result.status is ExtractionEligibilityStatus.BLOCKED_SCREENING_EXCLUDED

    def test_missing_full_text_decision_is_not_eligible(
        self, eligibility_service, setup_configured_project, pub_repo
    ):
        publication_id = uuid4()
        pub_repo.add_publications(
            "proj_elig", [Publication(record_id=publication_id, title="Undecided")]
        )

        result = eligibility_service.evaluate_publication(
            "proj_elig", publication_id, reviewer_id="rev_1"
        )
        assert result.is_eligible is False
        assert result.status is ExtractionEligibilityStatus.BLOCKED_SCREENING_INCOMPLETE
