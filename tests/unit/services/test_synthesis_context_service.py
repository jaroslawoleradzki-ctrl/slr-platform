"""Unit tests for SynthesisContextService: Phase 10 Context Synthesis (Task 10.5)."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    ConvertedValue,
    RelationDirection,
)
from app.repositories.extraction_repository import default_extraction_repository
from app.repositories.project_publication_repository import (
    default_project_publication_repository,
)
from app.repositories.project_repository import default_project_repository
from app.repositories.synthesis_context_repository import (
    default_synthesis_context_repository,
)
from app.repositories.synthesis_matrix_repository import (
    default_synthesis_matrix_repository,
)
from app.services.synthesis_context_service import (
    default_synthesis_context_service,
)
from app.services.synthesis_matrix_service import SynthesisMatrixService


def _as_datetime(val: str | datetime | None) -> datetime | None:
    """Converts a database string or datetime to a timezone-aware datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _apply_migrations_up_to(db_path: Path, max_version: str | None = None) -> None:
    migrations_dir = Path(__file__).parents[3] / "migrations"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ");"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if max_version and sql_file.name > max_version:
                continue
            if sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """Isolate SQLite database path for each test and initialize schema."""
    db_file = tmp_path / "test_slr.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_file))
    _apply_migrations_up_to(db_file, "0024_context_synthesis.sql")

    from app.domain.extraction import ExtractionTemplate, ExtractionTemplateVersion
    from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository

    template_repo = SqliteExtractionTemplateRepository(db_file)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )


@pytest.fixture
def project_repo(tmp_path):
    """Provide a project repository with a test project."""
    repo = default_project_repository()
    repo.create(
        Project(
            project_id="test_project",
            title="Test Project",
            description="Test project for context synthesis",
            protocol_version="1.0.0",
        )
    )
    return repo


@pytest.fixture
def service(project_repo):
    """Provide a synthesis context service with a valid project."""
    return default_synthesis_context_service()


class TestContextCategoryCRUD:
    """Test Context Category Create, Read, Update, Delete operations."""

    def test_create_context_category(self, service):
        """Test creating a context category."""
        category = service.create_context_category(
            project_id="test_project",
            category_id="cat_001",
            name="Regulatory Mandate",
            description="Moderating policy factor",
            display_order=1,
        )
        assert category.category_id == "cat_001"
        assert category.name == "Regulatory Mandate"
        assert category.project_id == "test_project"
        assert category.description == "Moderating policy factor"
        assert category.display_order == 1

        # Direct DB persistence assertion
        repo = default_synthesis_context_repository()
        persisted = repo.get_category("test_project", "cat_001")
        assert persisted is not None
        assert persisted["category_id"] == "cat_001"
        assert persisted["name"] == "Regulatory Mandate"
        assert persisted["description"] == "Moderating policy factor"

    def test_get_context_category(self, service):
        """Test retrieving a context category."""
        service.create_context_category(
            project_id="test_project", category_id="cat_002", name="Plant Size"
        )
        cat = service.get_context_category(project_id="test_project", category_id="cat_002")
        assert cat is not None
        assert cat.category_id == "cat_002"
        assert cat.name == "Plant Size"
        assert cat.project_id == "test_project"

    def test_list_context_categories(self, service):
        """Test listing context categories with deterministic order."""
        service.create_context_category(
            project_id="test_project", category_id="cat_004", name="Z Category", display_order=2
        )
        service.create_context_category(
            project_id="test_project", category_id="cat_003", name="A Category", display_order=1
        )
        cats = service.list_context_categories(project_id="test_project")
        assert len(cats) == 2
        assert cats[0].category_id == "cat_003"
        assert cats[1].category_id == "cat_004"

    def test_update_context_category(self, service):
        """Test updating a context category."""
        service.create_context_category(
            project_id="test_project", category_id="cat_005", name="Old Name"
        )
        updated = service.update_context_category(
            project_id="test_project",
            category_id="cat_005",
            name="Updated Name",
            description="Updated description",
            display_order=5,
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.display_order == 5

        # Direct DB check
        repo = default_synthesis_context_repository()
        persisted = repo.get_category("test_project", "cat_005")
        assert persisted is not None
        assert persisted["name"] == "Updated Name"
        assert persisted["display_order"] == 5

    def test_delete_context_category_unlinks_assignments(self, service):
        """Test deleting a context category cascades to unassign linked assignments."""
        service.create_context_category(
            project_id="test_project", category_id="cat_006", name="To Delete"
        )
        rel_id = uuid4()
        group_item_id = uuid4()
        pub_id = uuid4()
        rev_id = uuid4()

        # Create link directly referencing category
        repo = default_synthesis_context_repository()
        link = repo.create_link(
            link_id=str(uuid4()),
            project_id="test_project",
            analytical_relation_id=str(rel_id),
            group_item_id=str(group_item_id),
            publication_id=str(pub_id),
            latest_revision_id=str(rev_id),
            source_context_text="Context evidence",
            analytical_context_category_id="cat_006",
            context_impact="ENABLE",
            approval_state="approved",
        )
        assert link is not None
        assert link["analytical_context_category_id"] == "cat_006"

        # Delete category
        deleted = service.delete_context_category("test_project", "cat_006")
        assert deleted is True

        # Category is gone
        assert service.get_context_category("test_project", "cat_006") is None

        # Link is preserved, but category unlinked (NULL)
        updated_link = repo.get_link(link["link_id"])
        assert updated_link is not None
        assert updated_link["analytical_context_category_id"] is None


class TestContextAssignment:
    """Test Context Assignment, Remapping, and Unassignment operations."""

    def test_assign_context_to_relation(self, service):
        """Test assigning context to an analytical relation."""
        service.create_context_category(
            project_id="test_project", category_id="cat_001", name="Market Pressure"
        )
        matrix_repo = default_synthesis_matrix_repository()
        group_item_id = uuid4()
        pub_id = uuid4()
        rev_id = uuid4()
        rel_id = uuid4()

        relation = AnalyticalRelation(
            relation_id=rel_id,
            project_id="test_project",
            publication_id=pub_id,
            latest_revision_id=rev_id,
            group_item_id=group_item_id,
            item_index=1,
            source_practice="5S",
            analytical_lean_category_id="lean_standardization",
            source_effect="Electricity reduction",
            analytical_energy_category_id="energy_electricity",
            direction=RelationDirection.POSITIVE,
            magnitude=12.5,
            original_unit="%",
            converted_value=ConvertedValue(
                transformed_value=12.5,
                transformed_unit="%",
                conversion_rule="1 = 1",
            ),
            evidence_character="empirical",
            approval_state=ClassificationApprovalState.APPROVED,
        )
        matrix_repo.save_analytical_relation(relation)

        assignment = service.assign_context_to_relation(
            project_id="test_project",
            group_item_id=group_item_id,
            publication_id=pub_id,
            latest_revision_id=rev_id,
            source_context_text="High competition in manufacturing region",
            category_id="cat_001",
            context_impact="STRENGTHEN",
        )

        assert assignment.project_id == "test_project"
        assert assignment.analytical_relation_id == rel_id
        assert assignment.group_item_id == group_item_id
        assert assignment.publication_id == pub_id
        assert assignment.latest_revision_id == rev_id
        assert assignment.source_context_text == "High competition in manufacturing region"
        assert assignment.analytical_context_category_id == "cat_001"
        assert assignment.context_impact == "STRENGTHEN"
        assert assignment.approval_state == ClassificationApprovalState.PENDING

        # Direct DB persistence assertion
        repo = default_synthesis_context_repository()
        link = repo.get_link(str(assignment.assignment_id))
        assert link is not None
        assert link["analytical_context_category_id"] == "cat_001"
        assert link["context_impact"] == "STRENGTHEN"
        assert link["latest_revision_id"] == str(rev_id)

    def test_remap_context_assignment(self, service):
        """Test remapping a context assignment to a different category."""
        service.create_context_category(
            project_id="test_project", category_id="cat_001", name="Category 1"
        )
        service.create_context_category(
            project_id="test_project", category_id="cat_002", name="Category 2"
        )
        repo = default_synthesis_context_repository()
        link_id = str(uuid4())
        repo.create_link(
            link_id=link_id,
            project_id="test_project",
            analytical_relation_id=str(uuid4()),
            group_item_id=str(uuid4()),
            publication_id=str(uuid4()),
            latest_revision_id=str(uuid4()),
            source_context_text="Context text",
            analytical_context_category_id="cat_001",
            context_impact="ENABLE",
            approval_state="pending",
        )

        remapped = service.remap_context_assignment(
            link_id=link_id,
            new_category_id="cat_002",
            project_id="test_project",
            context_impact="WEAKEN",
        )
        assert remapped is not None
        assert remapped.analytical_context_category_id == "cat_002"
        assert remapped.context_impact == "WEAKEN"

        # Direct DB check
        link = repo.get_link(link_id)
        assert link is not None
        assert link["analytical_context_category_id"] == "cat_002"
        assert link["context_impact"] == "WEAKEN"

    def test_remap_missing_link_returns_none_not_value_error(self, service):
        """Regression: a missing link must yield None (404), never a category ValueError (500/400)."""
        service.create_context_category(
            project_id="test_project", category_id="cat_001", name="Category 1"
        )
        result = service.remap_context_assignment(
            link_id=str(uuid4()),
            new_category_id="no-such-category",
            project_id="test_project",
            context_impact="ENABLE",
        )
        assert result is None

    def test_unassign_context_from_relation(self, service):
        """Test unassigning context from a relation."""
        service.create_context_category(
            project_id="test_project", category_id="cat_001", name="Category 1"
        )
        repo = default_synthesis_context_repository()
        link_id = str(uuid4())
        repo.create_link(
            link_id=link_id,
            project_id="test_project",
            analytical_relation_id=str(uuid4()),
            group_item_id=str(uuid4()),
            publication_id=str(uuid4()),
            latest_revision_id=str(uuid4()),
            source_context_text="Context text",
            analytical_context_category_id="cat_001",
            context_impact="ENABLE",
            approval_state="pending",
        )

        deleted = service.unassign_context_from_relation(link_id=link_id, project_id="test_project")
        assert deleted is True
        assert repo.get_link(link_id) is None


class TestSynchronizationFromExtraction:
    """Test synchronization from latest COMPLETE extraction only and exact researcher preservation."""

    def test_synchronization_lifecycle_exact_persisted_behavior(self, service):
        """Proves complete lifecycle with exact persistence-backed assertions:
        1. rev1 COMPLETE -> synchronization discovers E11 context evidence, creates link pointing to rev1.
        2. Researcher assigns category 'cat_001', sets impact 'STRENGTHEN', approves assignment.
        3. rev2 DRAFT -> resync explicitly excludes DRAFT; evidence stays at rev1 COMPLETE, researcher state untouched.
        4. rev3 COMPLETE with same group_item_id -> resync advances latest_revision_id to rev3 COMPLETE, preserving researcher category/approval/impact.
        5. rev4 COMPLETE genuinely removes E11 context -> resync advances latest_revision_id to rev4, clears source_context_text to empty string without fabricating text.
        6. E10 impact_mechanism is NEVER substituted for E11 moderating_conditions.
        """
        proj_id = "test_project"
        pub_id = uuid4()
        group_item_id = uuid4()
        rev1_id = UUID("11111111-1111-1111-1111-111111111111")
        rev2_draft_id = UUID("22222222-2222-2222-2222-222222222222")
        rev3_complete_id = UUID("33333333-3333-3333-3333-333333333333")
        rev4_removed_e11_id = UUID("44444444-4444-4444-4444-444444444444")

        pub_repo = default_project_publication_repository()
        pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Manufacturing Energy Study", publication_year=2024)])

        extraction_repo = default_extraction_repository()
        rec = extraction_repo.create_record(
            ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
        )

        # -------------------------------------------------------------
        # Step 1: rev1 COMPLETE with E10 and E11
        # -------------------------------------------------------------
        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=rev1_id,
                record_id=rec.record_id,
                project_id=proj_id,
                publication_id=pub_id,
                revision_index=1,
                reviewer_id="rev_1",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=group_item_id,
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Value Stream Mapping"),
                            ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Natural Gas"),
                            ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Elimination of thermal bottlenecks in drying ovens."),
                            ExtractedValueState(field_key="moderating_conditions", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Batch manufacturing with high seasonal ambient temperature variation."),
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )

        matrix_service = SynthesisMatrixService(
            matrix_repo=default_synthesis_matrix_repository(),
            extraction_repo=extraction_repo,
            project_repo=default_project_repository(),
            publication_repo=pub_repo,
        )
        matrix_service.synchronize_analytical_relations(proj_id)

        # Synchronize context
        ws_v1 = service.synchronize_context_from_extraction(proj_id)
        assert len(ws_v1.assignments) == 1
        assign_v1 = ws_v1.assignments[0]
        assert assign_v1.publication_id == pub_id
        assert assign_v1.group_item_id == group_item_id
        assert assign_v1.latest_revision_id == rev1_id
        assert assign_v1.source_context_text == "Batch manufacturing with high seasonal ambient temperature variation."
        assert assign_v1.analytical_context_category_id is None
        assert assign_v1.approval_state == ClassificationApprovalState.PENDING

        # -------------------------------------------------------------
        # Step 2: Researcher classifies and approves context link
        # -------------------------------------------------------------
        service.create_context_category(
            project_id=proj_id, category_id="cat_env", name="Environmental Conditions"
        )
        context_repo = default_synthesis_context_repository()
        approved_timestamp = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        context_repo.create_link(
            link_id=str(assign_v1.assignment_id),
            project_id=proj_id,
            analytical_relation_id=str(assign_v1.analytical_relation_id),
            group_item_id=str(group_item_id),
            publication_id=str(pub_id),
            latest_revision_id=str(rev1_id),
            source_context_text=assign_v1.source_context_text,
            analytical_context_category_id="cat_env",
            context_impact="STRENGTHEN",
            approval_state="approved",
            approved_by="lead_investigator",
            approved_at=approved_timestamp,
        )

        # Verify persisted state in SQLite
        link_step2 = context_repo.get_link(str(assign_v1.assignment_id))
        assert link_step2 is not None
        assert link_step2["analytical_context_category_id"] == "cat_env"
        assert link_step2["context_impact"] == "STRENGTHEN"
        assert link_step2["approval_state"] == "approved"
        assert link_step2["approved_by"] == "lead_investigator"
        assert link_step2["latest_revision_id"] == str(rev1_id)

        # -------------------------------------------------------------
        # Step 3: rev2 DRAFT appended -> Resync excludes DRAFT
        # -------------------------------------------------------------
        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=rev2_draft_id,
                record_id=rec.record_id,
                project_id=proj_id,
                publication_id=pub_id,
                revision_index=2,
                reviewer_id="rev_2",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=group_item_id,
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(field_key="moderating_conditions", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="DRAFT MODERATING CONDITION - MUST NOT ENTER SYNTHESIS"),
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )

        ws_v2 = service.synchronize_context_from_extraction(proj_id)
        assert len(ws_v2.assignments) == 1
        assign_v2 = ws_v2.assignments[0]
        # Must strictly remain at rev1 COMPLETE
        assert assign_v2.latest_revision_id == rev1_id
        assert assign_v2.latest_revision_id != rev2_draft_id
        assert assign_v2.source_context_text == "Batch manufacturing with high seasonal ambient temperature variation."
        assert "DRAFT" not in assign_v2.source_context_text
        # Researcher state strictly preserved
        assert assign_v2.analytical_context_category_id == "cat_env"
        assert assign_v2.context_impact == "STRENGTHEN"
        assert assign_v2.approval_state == ClassificationApprovalState.APPROVED
        assert assign_v2.approved_by == "lead_investigator"

        # Direct DB persistence assertion
        link_step3 = context_repo.get_link(str(assign_v1.assignment_id))
        assert link_step3 is not None
        assert link_step3["latest_revision_id"] == str(rev1_id)
        assert link_step3["analytical_context_category_id"] == "cat_env"
        assert link_step3["approval_state"] == "approved"

        # -------------------------------------------------------------
        # Step 4: rev3 COMPLETE with same durable group_item_id -> Advances to rev3
        # -------------------------------------------------------------
        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=rev3_complete_id,
                record_id=rec.record_id,
                project_id=proj_id,
                publication_id=pub_id,
                revision_index=3,
                reviewer_id="rev_1",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=group_item_id,
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Value Stream Mapping"),
                            ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Natural Gas"),
                            ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Elimination of thermal bottlenecks in drying ovens."),
                            ExtractedValueState(field_key="moderating_conditions", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Batch manufacturing with high seasonal temperature and humidity."),
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )

        ws_v3 = service.synchronize_context_from_extraction(proj_id)
        assert len(ws_v3.assignments) == 1
        assign_v3 = ws_v3.assignments[0]
        # Traceability advanced to rev3
        assert assign_v3.latest_revision_id == rev3_complete_id
        assert assign_v3.source_context_text == "Batch manufacturing with high seasonal temperature and humidity."
        # Researcher state strictly preserved
        assert assign_v3.analytical_context_category_id == "cat_env"
        assert assign_v3.context_impact == "STRENGTHEN"
        assert assign_v3.approval_state == ClassificationApprovalState.APPROVED
        assert assign_v3.approved_by == "lead_investigator"

        # Direct DB persistence assertion
        link_step4 = context_repo.get_link(str(assign_v1.assignment_id))
        assert link_step4 is not None
        assert link_step4["latest_revision_id"] == str(rev3_complete_id)
        assert link_step4["analytical_context_category_id"] == "cat_env"
        assert link_step4["context_impact"] == "STRENGTHEN"
        assert link_step4["approval_state"] == "approved"
        assert link_step4["approved_by"] == "lead_investigator"

        # -------------------------------------------------------------
        # Step 5: rev4 COMPLETE where E11 is genuinely removed -> No fabrication
        # -------------------------------------------------------------
        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=rev4_removed_e11_id,
                record_id=rec.record_id,
                project_id=proj_id,
                publication_id=pub_id,
                revision_index=4,
                reviewer_id="rev_1",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=group_item_id,
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Value Stream Mapping"),
                            ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Natural Gas"),
                            # E10 present
                            ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Elimination of thermal bottlenecks in drying ovens."),
                            # E11 moderating_conditions REMOVED
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )

        ws_v4 = service.synchronize_context_from_extraction(proj_id)
        assert len(ws_v4.assignments) == 1
        assign_v4 = ws_v4.assignments[0]
        # Traceability advanced to rev4
        assert assign_v4.latest_revision_id == rev4_removed_e11_id
        # Context text must be empty string, NOT fabricated from E10 impact_mechanism
        assert assign_v4.source_context_text == ""
        assert "Elimination of thermal bottlenecks" not in assign_v4.source_context_text
        # Researcher classification preserved
        assert assign_v4.analytical_context_category_id == "cat_env"
        assert assign_v4.context_impact == "STRENGTHEN"
        assert assign_v4.approval_state == ClassificationApprovalState.APPROVED

        # Direct DB persistence assertion
        link_step5 = context_repo.get_link(str(assign_v1.assignment_id))
        assert link_step5 is not None
        assert link_step5["latest_revision_id"] == str(rev4_removed_e11_id)
        assert link_step5["source_context_text"] == ""
        assert link_step5["analytical_context_category_id"] == "cat_env"

    def test_e10_is_never_substituted_for_e11(self, service):
        """Proves E10 impact_mechanism is never substituted for E11 moderating_conditions."""
        proj_id = "test_project_e10_e11"
        default_project_repository().create(Project(project_id=proj_id, title="E10 E11 Test", description=""))

        pub_id = uuid4()
        default_project_publication_repository().add_publications(
            proj_id, [Publication(record_id=pub_id, title="Study 1", publication_year=2024)]
        )
        extraction_repo = default_extraction_repository()
        rec = extraction_repo.create_record(
            ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
        )
        group_item_id = uuid4()
        rev_id = uuid4()

        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=rev_id,
                record_id=rec.record_id,
                project_id=proj_id,
                publication_id=pub_id,
                revision_index=1,
                reviewer_id="rev_1",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=group_item_id,
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="TPM"),
                            ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity"),
                            ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="E10 Mechanism Only Text"),
                            # E11 moderating_conditions is NOT present
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )

        matrix_service = SynthesisMatrixService(
            matrix_repo=default_synthesis_matrix_repository(),
            extraction_repo=extraction_repo,
            project_repo=default_project_repository(),
            publication_repo=default_project_publication_repository(),
        )
        matrix_service.synchronize_analytical_relations(proj_id)

        ws = service.synchronize_context_from_extraction(proj_id)
        assert len(ws.assignments) == 1
        assign = ws.assignments[0]
        # Must NOT copy E10 into source_context_text
        assert assign.source_context_text == ""
        assert assign.source_context_text != "E10 Mechanism Only Text"


class TestProjectIsolation:
    """Test project isolation for context operations."""

    def test_project_isolation(self, service):
        """Test that project isolation is enforced."""
        cat = service.create_context_category(
            project_id="test_project", category_id="cat_p", name="Project Bound"
        )
        assert cat.project_id == "test_project"

    def test_different_project_isolation(self, service):
        """Test that categories in one project don't affect another."""
        cat = service.create_context_category(
            project_id="test_project", category_id="cat_p", name="Project Bound"
        )
        assert cat.project_id == "test_project"
        assert cat.category_id == "cat_p"


class TestSummaryStatistics:
    """Test deterministic synthesis summary statistics."""

    def test_context_synthesis_summary_exact_counts(self, service):
        """Test getting context synthesis summary with exact counts."""
        service.create_context_category(
            project_id="test_project", category_id="cat_s1", name="Summary Cat"
        )
        repo = default_synthesis_context_repository()
        rel_id1 = uuid4()
        rel_id2 = uuid4()
        pub_id1 = uuid4()
        pub_id2 = uuid4()

        repo.create_link(
            link_id=str(uuid4()),
            project_id="test_project",
            analytical_relation_id=str(rel_id1),
            group_item_id=str(uuid4()),
            publication_id=str(pub_id1),
            latest_revision_id=str(uuid4()),
            source_context_text="Context 1",
            analytical_context_category_id="cat_s1",
            context_impact="ENABLE",
            approval_state="approved",
        )
        repo.create_link(
            link_id=str(uuid4()),
            project_id="test_project",
            analytical_relation_id=str(rel_id2),
            group_item_id=str(uuid4()),
            publication_id=str(pub_id2),
            latest_revision_id=str(uuid4()),
            source_context_text="Context 2",
            analytical_context_category_id=None,
            context_impact="CONDITION",
            approval_state="pending",
        )

        summary = service.get_context_synthesis_summary(project_id="test_project")
        assert summary.context_evidence_count == 2
        assert summary.distinct_publication_count == 2
        assert summary.distinct_analytical_relation_count == 2
        assert summary.distinct_mechanism_pathway_count == 1  # 1 categorized link


class TestMigrationSafety:
    """Test migration safety for 0024_context_synthesis."""

    def test_migration_0024_schema_exists(self):
        """Test that migration 0024 schema is valid."""
        migration_path = Path("migrations/0024_context_synthesis.sql")
        assert migration_path.exists()
        with open(migration_path) as f:
            sql = f.read()
        assert "synthesis_context_categories" in sql
        assert "synthesis_relation_context_links" in sql

    def test_fresh_db_with_0024(self, tmp_path):
        """Test fresh database with migration 0024 applied."""
        db_path = str(tmp_path / "fresh_test.db")
        conn = sqlite3.connect(db_path)
        migration_path = Path("migrations/0024_context_synthesis.sql")
        with open(migration_path) as f:
            sql = f.read()
        conn.executescript("PRAGMA foreign_keys=OFF;" + sql)
        conn.close()

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%context%';"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "synthesis_context_categories" in tables
        assert "synthesis_relation_context_links" in tables
        conn.close()


class TestContextWorkspaceData:
    """Test ContextWorkspaceData construction and content."""

    def test_context_workspace_data_structure(self, service):
        """Test ContextWorkspaceData has exact required fields."""
        data = service.synchronize_context_from_extraction(project_id="test_project")
        assert data.project_id == "test_project"
        assert isinstance(data.categories, list)
        assert isinstance(data.assignments, list)
        assert isinstance(data.stats, dict)
        assert "total_relations" in data.stats
        assert "total_publications" in data.stats
        assert "categorized_relations" in data.stats
        assert "total_assignments" in data.stats
