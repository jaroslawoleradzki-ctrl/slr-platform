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
        field_key="study_title",
        name="Study Title",
        data_type=FieldDataType.TEXT,
        is_required=True,
        min_length=3,
        allowed_statuses=[ValueStatus.PRESENT, ValueStatus.NOT_REPORTED, ValueStatus.NOT_APPLICABLE, ValueStatus.UNCLEAR],
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
    def test_first_revision_creates_index_1_and_subsequent_creates_index_2(self, execution_service, setup_environment):
        env = setup_environment
        val1 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Initial Title",
            source_locator="Title in source record",
        )
        rev1 = execution_service.submit_revision(env["project_id"], env["publication_id"], env["reviewer_id"], [val1])
        assert rev1.revision_index == 1

        val2 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Updated Title",
            source_locator="Title in source record",
        )
        rev2 = execution_service.submit_revision(env["project_id"], env["publication_id"], env["reviewer_id"], [val2])
        assert rev2.revision_index == 2

        history = execution_service.get_revision_history(env["project_id"], env["publication_id"])
        assert len(history) == 2
        assert history[0].revision_index == 1
        assert history[0].publication_values[0].text_value == "Initial Title"
        assert history[1].revision_index == 2
        assert history[1].publication_values[0].text_value == "Updated Title"

    def test_exact_read_model_round_trip_creates_fresh_value_snapshots(self, execution_service, setup_environment):
        """The service, not the caller, owns new value identities per revision."""
        env = setup_environment
        first = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [
                ExtractedValueState(
                    field_key="study_title",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Initial title",
                    source_locator="Title in source record",
                )
            ],
            [
                ExtractedGroupItemState(
                    group_key="study_arms",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="age_mean",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            float_value=42.0,
                            source_locator="Results table",
                        )
                    ],
                )
            ],
        )
        read_model = execution_service.get_latest_revision(env["project_id"], env["publication_id"])
        assert read_model == first

        # Deliberately reuse every ID received through the read-model/API
        # equivalent.  submit_revision must regenerate snapshot value IDs.
        second = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            read_model.publication_values,
            read_model.group_items,
        )
        history = execution_service.get_revision_history(env["project_id"], env["publication_id"])
        assert len(history) == 2
        assert second.revision_index == 2
        assert history[0].publication_values[0].value_id != history[1].publication_values[0].value_id
        assert history[0].group_items[0].values[0].value_id != history[1].group_items[0].values[0].value_id
        assert history[0].group_items[0].group_item_id == history[1].group_items[0].group_item_id
        assert history[0] == first

    def test_eligible_vs_ineligible_publication(self, execution_service, setup_environment):
        env = setup_environment
        val = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
            source_locator="Title in source record",
        )

        # Eligible accepts
        rev = execution_service.submit_revision(env["project_id"], env["publication_id"], env["reviewer_id"], [val])
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
        )
        arm_val1 = ExtractedValueState(
            field_key="age_mean",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            float_value=45.5,
            source_locator="Results table",
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
        )
        arm_val2 = ExtractedValueState(
            field_key="age_mean",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            float_value=45.5,
            source_locator="Results table",
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

    def test_save_draft_with_missing_required_results_in_in_progress(self, execution_service, setup_environment):
        env = setup_environment
        # Missing required field "study_title" and repeating group "study_arms"
        val_sample = ExtractedValueState(
            field_key="sample_size",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            int_value=100,
            source_locator="Results table",
        )
        rev = execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_sample],
            mark_complete=False,
        )
        assert rev.completeness_status == ExtractionCompletenessStatus.IN_PROGRESS

    def test_attempt_complete_with_missing_required_raises_validation_error(self, execution_service, setup_environment):
        env = setup_environment
        val_sample = ExtractedValueState(
            field_key="sample_size",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            int_value=100,
            source_locator="Results table",
        )
        with pytest.raises(ExtractionValidationError, match="Cannot mark extraction as COMPLETE"):
            execution_service.submit_revision(
                env["project_id"],
                env["publication_id"],
                env["reviewer_id"],
                [val_sample],
                mark_complete=True,
            )

    def test_invalid_enum_and_out_of_bounds_numeric_fail(self, execution_service, setup_environment):
        env = setup_environment
        val_enum = ExtractedValueState(
            field_key="study_design",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="invalid_design_type",
            source_locator="Methods section",
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
            source_locator="Results table",
        )
        with pytest.raises(ExtractionValidationError, match="exceeds max_value"):
            execution_service.submit_revision(
                env["project_id"],
                env["publication_id"],
                env["reviewer_id"],
                [val_bound],
            )

    def test_repeating_group_cardinality_and_child_field_enforcement(self, execution_service, setup_environment):
        env = setup_environment
        val_title1 = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
            source_locator="Title in source record",
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
            source_locator="Title in source record",
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
                        source_locator="Results table",
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

    def test_provenance_and_reviewer_attribution_survive_persistence(self, execution_service, setup_environment):
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

    def test_progress_metrics_and_percentage_calculation(self, execution_service, setup_environment):
        env = setup_environment
        # Initially 1 eligible publication, NOT_STARTED
        prog = execution_service.get_progress(env["project_id"], env["reviewer_id"])
        assert prog["total_eligible_publications"] == 1
        assert prog["not_started_count"] == 1
        assert prog["completion_percentage"] == 0.0

        # Submit complete revision
        val_title = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
            source_locator="Title in source record",
        )
        arm_val = ExtractedValueState(
            field_key="age_mean",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            float_value=45.5,
            source_locator="Results table",
        )
        group_item = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=1,
            values=[arm_val],
        )
        execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_title],
            [group_item],
            mark_complete=True,
        )

        prog2 = execution_service.get_progress(env["project_id"], env["reviewer_id"])
        assert prog2["total_eligible_publications"] == 1
        assert prog2["complete_count"] == 1
        assert prog2["completion_percentage"] == 100.0

    def test_record_summaries_list_metadata_and_status(self, execution_service, setup_environment):
        env = setup_environment
        summaries = execution_service.list_record_summaries(env["project_id"], env["reviewer_id"])
        assert len(summaries) == 1
        assert summaries[0]["publication_id"] == env["publication_id"]
        assert summaries[0]["extraction_status"] == ExtractionCompletenessStatus.NOT_STARTED.value

    def test_matrix_preserves_1_to_n_independent_group_item_rows(self, execution_service, setup_environment):
        env = setup_environment
        val_title = ExtractedValueState(
            field_key="study_title",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Valid Title",
            source_locator="Title in source record",
        )
        arm1 = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="age_mean",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    float_value=25.0,
                    source_locator="Results table",
                )
            ],
        )
        arm2 = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=2,
            values=[
                ExtractedValueState(
                    field_key="age_mean",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    float_value=40.0,
                    source_locator="Results table",
                )
            ],
        )

        execution_service.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            [val_title],
            [arm1, arm2],
            mark_complete=True,
        )

        matrix = execution_service.get_matrix(env["project_id"], env["reviewer_id"])
        assert matrix["total_relationships"] == 2
        # Section 11 invariant: 2 items in 1 publication render as 2 separate matrix rows!
        assert len(matrix["items"]) == 2
        assert matrix["items"][0]["item_index"] == 1
        assert matrix["items"][1]["item_index"] == 2

    def test_durable_group_item_id_contract_across_service_revisions(
        self, setup_environment, execution_service: ExtractionExecutionService
    ):
        """End-to-end service verification of Section 3.1 durable group_item_id contract:
        1. New group item receives durable ID
        2. Editing values preserves ID
        3. Reordering preserves IDs
        4. Inserting new item preserves existing IDs
        5. Deleting one item preserves remaining IDs
        6. IDs survive full persistence/readback cycle
        7. Stable across append-only revisions and matrix/dataset views
        """
        env = setup_environment
        project_id = env["project_id"]
        pub_id = env["publication_id"]
        rev_id = env["reviewer_id"]

        def make_title():
            return ExtractedValueState(
                field_key="study_title",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Empirical Lean Energy Study",
                source_locator="Title in source record",
            )

        # --- Revision 1: Initial creation of 2 items (A and B) ---
        item_a = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=25.0, source_locator="Results table"
                )
            ],
        )
        item_b = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=2,
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=30.0, source_locator="Results table"
                )
            ],
        )
        r1_result = execution_service.submit_revision(
            project_id, pub_id, rev_id, [make_title()], [item_a, item_b], mark_complete=False
        )
        assert len(r1_result.group_items) == 2
        uuid_a = r1_result.group_items[0].group_item_id
        uuid_b = r1_result.group_items[1].group_item_id
        assert uuid_a is not None and uuid_b is not None
        assert uuid_a != uuid_b

        # --- Revision 2: Insert new item X at top, edit item A values, shift B ---
        item_x = ExtractedGroupItemState(
            group_key="study_arms",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=20.0, source_locator="Results table"
                )
            ],
        )
        item_a_edited = ExtractedGroupItemState(
            group_item_id=uuid_a,  # Keep UUID
            group_key="study_arms",
            item_index=2,  # Shifted index
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=27.5, source_locator="Results table"
                )
            ],  # Edited value
        )
        item_b_shifted = ExtractedGroupItemState(
            group_item_id=uuid_b,  # Keep UUID
            group_key="study_arms",
            item_index=3,  # Shifted index
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=30.0, source_locator="Results table"
                )
            ],
        )
        r2_result = execution_service.submit_revision(
            project_id, pub_id, rev_id, [make_title()], [item_x, item_a_edited, item_b_shifted], mark_complete=False
        )
        assert len(r2_result.group_items) == 3
        uuid_x = r2_result.group_items[0].group_item_id
        assert uuid_x not in (uuid_a, uuid_b)
        assert r2_result.group_items[1].group_item_id == uuid_a
        assert r2_result.group_items[1].item_index == 2
        assert r2_result.group_items[1].values[0].float_value == 27.5
        assert r2_result.group_items[2].group_item_id == uuid_b
        assert r2_result.group_items[2].item_index == 3

        # --- Revision 3: Delete item A, reorder B to index 1 and X to index 2 ---
        item_b_reordered = ExtractedGroupItemState(
            group_item_id=uuid_b,  # Keep UUID
            group_key="study_arms",
            item_index=1,  # Reordered
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=30.0, source_locator="Results table"
                )
            ],
        )
        item_x_reordered = ExtractedGroupItemState(
            group_item_id=uuid_x,  # Keep UUID
            group_key="study_arms",
            item_index=2,  # Reordered
            values=[
                ExtractedValueState(
                    field_key="age_mean", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, float_value=20.0, source_locator="Results table"
                )
            ],
        )
        r3_result = execution_service.submit_revision(
            project_id, pub_id, rev_id, [make_title()], [item_b_reordered, item_x_reordered], mark_complete=True
        )
        assert len(r3_result.group_items) == 2
        assert r3_result.group_items[0].group_item_id == uuid_b
        assert r3_result.group_items[0].item_index == 1
        assert r3_result.group_items[1].group_item_id == uuid_x
        assert r3_result.group_items[1].item_index == 2

        # Check Matrix view retains durable group_item_id
        matrix = execution_service.get_matrix(project_id, rev_id)
        assert matrix["total_relationships"] == 2
        assert [row["group_item_id"] for row in matrix["items"]] == [uuid_b, uuid_x]

        # Check History preservation across all 3 revisions
        history = execution_service.get_revision_history(project_id, pub_id)
        assert len(history) == 3
        # Rev 1: [A, B]
        assert [item.group_item_id for item in history[0].group_items] == [uuid_a, uuid_b]
        assert history[0].group_items[0].values[0].float_value == 25.0
        # Rev 2: [X, A, B]
        assert [item.group_item_id for item in history[1].group_items] == [uuid_x, uuid_a, uuid_b]
        assert history[1].group_items[1].values[0].float_value == 27.5
        # Rev 3: [B, X]
        assert [item.group_item_id for item in history[2].group_items] == [uuid_b, uuid_x]
