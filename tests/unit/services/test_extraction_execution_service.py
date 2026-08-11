"""Unit tests for ExtractionExecutionService (Phase 9.4)."""

from uuid import uuid4

import pytest

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionConfigurationNotFoundError,
    ExtractionFieldDefinition,
    ExtractionIneligibleError,
    ExtractionRepeatingGroupDefinition,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ExtractionValidationError,
    FieldDataType,
    InvalidValueError,
    ValueOrigin,
    ValueStatus,
)
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import Project, SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.services.extraction_configuration_service import ExtractionConfigurationService
from app.services.extraction_eligibility_service import ExtractionEligibilityService
from app.services.extraction_execution_service import ExtractionExecutionService
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.screening_input_service import ScreeningInputService


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_execution.db"


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
def config_service(extraction_repo, template_repo, project_repo):
    return ExtractionConfigurationService(
        extraction_repo=extraction_repo,
        template_repo=template_repo,
        project_repo=project_repo,
    )


@pytest.fixture
def input_service(pub_repo):
    return ScreeningInputService(publication_repository=pub_repo)


@pytest.fixture
def multi_reviewer_service(input_service, temp_db):
    reporting_repo = ScreeningReportingRepository(temp_db)
    return MultiReviewerScreeningService(
        input_service=input_service,
        reporting=reporting_repo,
    )


@pytest.fixture
def eligibility_service(config_service, input_service, multi_reviewer_service, decision_repo):
    return ExtractionEligibilityService(
        config_service=config_service,
        input_service=input_service,
        multi_reviewer_service=multi_reviewer_service,
        decisions_repo=decision_repo,
    )


@pytest.fixture
def execution_service(config_service, eligibility_service, template_repo, extraction_repo):
    return ExtractionExecutionService(
        config_service=config_service,
        eligibility_service=eligibility_service,
        template_repo=template_repo,
        extraction_repo=extraction_repo,
    )


@pytest.fixture
def setup_environment(project_repo, template_repo, config_service, pub_repo, decision_repo):
    # Create project
    p = Project(project_id="proj_exec", title="Execution Project", description="Test")
    project_repo.create(p)

    # Register template & version
    tmpl = ExtractionTemplate(template_id="exec_tmpl", name="Execution Template")
    template_repo.register_template(tmpl)

    f_title = ExtractionFieldDefinition(
        field_key="study_title", name="Study Title", data_type=FieldDataType.TEXT, is_required=True, min_length=3
    )
    f_sample = ExtractionFieldDefinition(
        field_key="sample_size", name="Sample Size", data_type=FieldDataType.INTEGER, min_value=1, max_value=1000
    )
    f_design = ExtractionFieldDefinition(
        field_key="study_design",
        name="Study Design",
        data_type=FieldDataType.ENUM,
        allowed_values=["rct", "cohort", "case_control"],
    )

    group_f_age = ExtractionFieldDefinition(
        field_key="age_mean", name="Mean Age", data_type=FieldDataType.DECIMAL, is_required=True
    )
    g_arm = ExtractionRepeatingGroupDefinition(
        group_key="study_arms",
        name="Study Arms",
        min_items=1,
        max_items=3,
        field_definitions=[group_f_age],
    )

    ver = ExtractionTemplateVersion(
        template_id="exec_tmpl",
        version="1.0.0",
        name="v1",
        is_active=True,
        is_published=True,
        publication_fields=[f_title, f_sample, f_design],
        repeating_groups=[g_arm],
    )
    template_repo.register_version(ver)

    # Set project configuration
    config_service.set_configuration("proj_exec", "exec_tmpl", "1.0.0")

    # Seed eligible publication
    pub_id = uuid4()
    pub_repo.add_publications("proj_exec", [Publication(record_id=pub_id, title="Execution Publication")])
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_exec",
            publication_id=pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.INCLUDE,
        )
    )

    # Seed ineligible publication
    ineligible_pub_id = uuid4()
    pub_repo.add_publications("proj_exec", [Publication(record_id=ineligible_pub_id, title="Excluded Publication")])
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_exec",
            publication_id=ineligible_pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.EXCLUDE,
        )
    )

    return {
        "project_id": "proj_exec",
        "publication_id": pub_id,
        "ineligible_publication_id": ineligible_pub_id,
        "reviewer_id": "rev_1",
    }


class TestExtractionExecutionService:
    def test_first_revision_creates_index_1_and_subsequent_creates_index_2(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        val1 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Initial Title",
        )
        rev1 = execution_service.submit_revision(
            env["project_id"], env["publication_id"], env["reviewer_id"], [val1]
        )
        assert rev1.revision_index == 1

        val2 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Updated Title",
        )
        rev2 = execution_service.submit_revision(
            env["project_id"], env["publication_id"], env["reviewer_id"], [val2]
        )
        assert rev2.revision_index == 2

        history = execution_service.get_revision_history(env["project_id"], env["publication_id"])
        assert len(history) == 2
        assert history[0].revision_index == 1
        assert history[0].publication_values[0].text_value == "Initial Title"
        assert history[1].revision_index == 2
        assert history[1].publication_values[0].text_value == "Updated Title"

    def test_eligible_vs_ineligible_publication(self, execution_service, setup_environment):
        env = setup_environment
        val = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
        )

        # Eligible accepts
        rev = execution_service.submit_revision(
            env["project_id"], env["publication_id"], env["reviewer_id"], [val]
        )
        assert rev is not None

        # Ineligible rejects
        with pytest.raises(ExtractionIneligibleError):
            execution_service.submit_revision(
                env["project_id"], env["ineligible_publication_id"], env["reviewer_id"], [val]
            )

    def test_unconfigured_project_raises_configuration_not_found(self, execution_service):
        with pytest.raises(ExtractionConfigurationNotFoundError):
            execution_service.submit_revision("unconfigured_proj", uuid4(), "rev_1", [])

    def test_value_status_consistency_validation(self, execution_service):
        # PRESENT without typed value fails
        with pytest.raises(InvalidValueError, match="PRESENT must have at least one typed value"):
            ExtractedValueState(
                field_key="study_title",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
            )

        # NOT_REPORTED with typed value fails
        with pytest.raises(InvalidValueError, match="must have all typed values set to None"):
            ExtractedValueState(
                field_key="study_title",
                status=ValueStatus.NOT_REPORTED,
                origin=ValueOrigin.REPORTED,
                text_value="Should not be here",
            )

        # NOT_APPLICABLE with typed value fails
        with pytest.raises(InvalidValueError, match="must have all typed values set to None"):
            ExtractedValueState(
                field_key="study_title",
                status=ValueStatus.NOT_APPLICABLE,
                origin=ValueOrigin.REPORTED,
                text_value="Should not be here",
            )

    def test_required_not_reported_and_not_applicable_satisfies_completeness(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        val_nr = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.NOT_REPORTED,
            origin=ValueOrigin.REPORTED,
        )
        arm_val1 = ExtractedValueState(
            field_key="age_mean",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            float_value=45.5,
        )
        group_item1 = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=1,
            values=[arm_val1],
        )

        rev = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_nr],
            [group_item1],
            mark_complete=True,
        )
        assert rev.completeness_status == ExtractionCompletenessStatus.COMPLETE

        # Also for NOT_APPLICABLE
        val_na = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.NOT_APPLICABLE,
            origin=ValueOrigin.REPORTED,
        )
        arm_val2 = ExtractedValueState(
            field_key="age_mean",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            float_value=45.5,
        )
        group_item2 = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=1,
            values=[arm_val2],
        )
        rev2 = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_na],
            [group_item2],
            mark_complete=True,
        )
        assert rev2.completeness_status == ExtractionCompletenessStatus.COMPLETE

    def test_save_draft_with_missing_required_results_in_in_progress(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        # Missing required field "study_title" and repeating group "study_arms"
        val_sample = ExtractedValueState(
            field_key="sample_size",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            int_value=100,
        )
        rev = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_sample],
            mark_complete=False,
        )
        assert rev.completeness_status == ExtractionCompletenessStatus.IN_PROGRESS

    def test_attempt_complete_with_missing_required_raises_validation_error(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        val_sample = ExtractedValueState(
            field_key="sample_size",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            int_value=100,
        )
        with pytest.raises(ExtractionValidationError, match="Cannot mark extraction as COMPLETE"):
            execution_service.submit_revision(
                env["project_id"],
                env["publication_id"],
                env["reviewer_id"],
                [val_sample],
                mark_complete=True,
            )

    def test_invalid_enum_and_out_of_bounds_numeric_fail(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        val_enum = ExtractedValueState(
            field_key="study_design",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="invalid_design_type",
        )
        with pytest.raises(ExtractionValidationError, match="is not in allowed_values"):
            execution_service.submit_revision(
                env["project_id"],
                env["publication_id"],
                env["reviewer_id"],
                [val_enum],
            )

        val_bound = ExtractedValueState(
            field_key="sample_size",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            int_value=5000,  # Max is 1000
        )
        with pytest.raises(ExtractionValidationError, match="exceeds max_value"):
            execution_service.submit_revision(
                env["project_id"],
                env["publication_id"],
                env["reviewer_id"],
                [val_bound],
            )

    def test_repeating_group_cardinality_and_child_field_enforcement(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        val_title1 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
        )

        # 0 items when min_items=1 yields IN_PROGRESS for draft, fails for complete
        rev_draft = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_title1],
            group_items=[],
            mark_complete=False,
        )
        assert rev_draft.completeness_status == ExtractionCompletenessStatus.IN_PROGRESS

        # 4 items when max_items=3 fails even for draft (structural)
        val_title2 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
        )
        items_exceed = [
            ExtractedGroupItemState(
                group_key="study_arms",
                item_index=i,
                values=[
                    ExtractedValueState(
                        field_key="age_mean",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        float_value=30.0 + i,
                    )
                ],
            )
            for i in range(1, 5)
        ]
        with pytest.raises(ExtractionValidationError, match="allows at most"):
            execution_service.submit_revision(
                env["project_id"],
                env["publication_id"],
                env["reviewer_id"],
                [val_title2],
                group_items=items_exceed,
                mark_complete=False,
            )

    def test_provenance_and_reviewer_attribution_survive_persistence(
        self, execution_service, setup_environment
    ):
        env = setup_environment
        val = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REVIEWER_CODED,
            text_value="Attributed Title",
            source_page="Page 12",
            source_section="Methods 2.1",
            source_locator="Table 1",
            source_quote="Extract from paper",
            reviewer_note="Note by reviewer",
        )
        rev = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val],
        )
        assert rev.reviewer_id == env["reviewer_id"]

        fetched = execution_service.get_latest_revision(env["project_id"], env["publication_id"])
        assert fetched is not None
        assert fetched.reviewer_id == env["reviewer_id"]
        v = fetched.publication_values[0]
        assert v.origin == ValueOrigin.REVIEWER_CODED
        assert v.source_page == "Page 12"
        assert v.source_section == "Methods 2.1"
        assert v.source_locator == "Table 1"
        assert v.source_quote == "Extract from paper"
        assert v.reviewer_note == "Note by reviewer"
