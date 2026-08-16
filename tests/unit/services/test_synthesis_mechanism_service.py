"""Unit tests for SynthesisMechanismService (Phase 10 Task 10.4)."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    EnergyEffectCategory,
    EvidenceCharacter,
    LeanPracticeCategory,
    RelationDirection,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import (
    SqliteExtractionTemplateRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import (
    SqliteProjectRepository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentRepository,
)
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
)
from app.services.synthesis_matrix_service import SynthesisMatrixService
from app.services.synthesis_mechanism_service import (
    MechanismAssignmentError,
    MechanismCategoryConflictError,
    MechanismCategoryNotFoundError,
    SynthesisMechanismService,
)


def _apply_migrations_up_to(db_path: Path, max_version: str | None = None) -> None:
    migrations_dir = Path(__file__).parents[3] / "migrations"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
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


@pytest.fixture
def env(tmp_path: Path):
    db_path = tmp_path / "test_mechanism_service.db"
    _apply_migrations_up_to(db_path, "0022_mechanism_synthesis.sql")

    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    project_repo = SqliteProjectRepository(db_path)
    publication_repo = SqliteProjectPublicationRepository(db_path)
    extraction_repo = SqliteExtractionRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)
    classification_repo = SqliteSynthesisClassificationRepository(db_path)
    matrix_repo = SqliteSynthesisMatrixRepository(db_path)
    mechanism_repo = SqliteSynthesisMechanismRepository(db_path)

    adapter = SynthesisExtractionAdapter(extraction_repo=extraction_repo, qa_repo=qa_repo)

    service = SynthesisMechanismService(
        mechanism_repo=mechanism_repo,
        matrix_repo=matrix_repo,
        classification_repo=classification_repo,
        extraction_repo=extraction_repo,
        publication_repo=publication_repo,
        project_repo=project_repo,
        adapter=adapter,
    )

    matrix_service = SynthesisMatrixService(
        matrix_repo=matrix_repo,
        classification_repo=classification_repo,
        extraction_repo=extraction_repo,
        project_repo=project_repo,
        qa_repo=qa_repo,
        publication_repo=publication_repo,
    )

    return {
        "db_path": db_path,
        "service": service,
        "matrix_service": matrix_service,
        "project_repo": project_repo,
        "publication_repo": publication_repo,
        "extraction_repo": extraction_repo,
        "classification_repo": classification_repo,
        "matrix_repo": matrix_repo,
        "mechanism_repo": mechanism_repo,
    }


def test_zero_seed_categories_for_new_project(env):
    """A new project starts with 0 hardcoded mechanism categories."""
    service: SynthesisMechanismService = env["service"]
    project_repo: SqliteProjectRepository = env["project_repo"]

    proj_id = "test-project-zero-seed"
    project_repo.create(Project(project_id=proj_id, title="Zero Seed Project", description=""))

    cats = service.list_categories(proj_id)
    assert cats == []


def test_category_management_workflow(env):
    service: SynthesisMechanismService = env["service"]
    project_repo: SqliteProjectRepository = env["project_repo"]

    proj_id = "test-cat-mgmt"
    project_repo.create(Project(project_id=proj_id, title="Cat Mgmt Project", description=""))

    # 1. Create
    cat = service.create_category(
        project_id=proj_id,
        category_id="idle_reduction",
        name="Idle-Time Reduction",
        description="Minimizing standby power consumption.",
        display_order=1,
    )
    assert cat.category_id == "idle_reduction"
    assert cat.name == "Idle-Time Reduction"

    # 2. Duplicate creation raises conflict
    with pytest.raises(MechanismCategoryConflictError):
        service.create_category(
            project_id=proj_id,
            category_id="idle_reduction",
            name="Idle-Time Reduction Duplicate",
        )

    # 3. Update
    updated = service.update_category(
        project_id=proj_id,
        category_id="idle_reduction",
        name="Standby & Idle Reduction",
        description="Updated",
        display_order=2,
    )
    assert updated.name == "Standby & Idle Reduction"

    # 4. Delete
    assert service.delete_category(proj_id, "idle_reduction") is True
    with pytest.raises(MechanismCategoryNotFoundError):
        service.get_category(proj_id, "idle_reduction")


def test_discovery_of_source_mechanism_text_and_synchronization(env):
    """Verifies that Phase 9 source mechanism text (E10) is discovered and linked to analytical relations."""
    service: SynthesisMechanismService = env["service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]
    matrix_repo: SqliteSynthesisMatrixRepository = env["matrix_repo"]

    proj_id = "test-proj-discovery"
    project_repo.create(Project(project_id=proj_id, title="Discovery Project", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub_id,
                title="Kaizen Energy Study in Automotive",
                publication_year=2023,
            )
        ],
    )

    rec = extraction_repo.create_record(
        ExtractionRecord(
            project_id=proj_id,
            publication_id=pub_id,
            template_id="lean_energy",
            template_version="1.0.0",
        )
    )

    # Create Phase 9 extraction revision with repeating group item
    group_item_id = uuid4()
    source_mech = "Turned off conveyor belts during idle production gaps, eliminating baseline electricity draw."
    item = ExtractedGroupItemState(
        group_item_id=group_item_id,
        group_key="lean_energy_relationships",
        item_index=1,
        values=[
            ExtractedValueState(
                field_key="lean_practice",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Kaizen Event",
                source_locator="Table 1",
            ),
            ExtractedValueState(
                field_key="energy_effect_indicator",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Electricity Draw",
                source_locator="Table 1",
            ),
            ExtractedValueState(
                field_key="impact_mechanism",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value=source_mech,
                source_locator="Table 1",
            ),
        ],
    )
    rev = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[item],
        )
    )

    # Create Task 10.3 Analytical Relation
    rel_id = uuid4()
    rel = AnalyticalRelation(
        relation_id=rel_id,
        project_id=proj_id,
        publication_id=pub_id,
        latest_revision_id=rev.revision_id,
        group_item_id=group_item_id,
        item_index=1,
        source_practice="Kaizen Event",
        source_effect="Electricity Draw",
        direction=RelationDirection.POSITIVE,
        evidence_character=EvidenceCharacter.EMPIRICAL,
        approval_state=ClassificationApprovalState.APPROVED,
    )
    matrix_repo.save_analytical_relation(rel)

    # Synchronize pathways
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert len(pathways) == 1
    assert pathways[0].analytical_relation_id == rel_id
    assert pathways[0].group_item_id == group_item_id
    assert pathways[0].source_mechanism_text == source_mech
    assert pathways[0].analytical_mechanism_category_id is None
    assert pathways[0].approval_state == ClassificationApprovalState.PENDING


def test_assignment_approval_and_synthesis_chain_aggregation(env):
    """Tests assigning analytical mechanism category, explicit approval, and synthesis chain aggregation."""
    service: SynthesisMechanismService = env["service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    classification_repo: SqliteSynthesisClassificationRepository = env["classification_repo"]
    matrix_repo: SqliteSynthesisMatrixRepository = env["matrix_repo"]

    proj_id = "test-proj-synthesis"
    project_repo.create(Project(project_id=proj_id, title="Synthesis Project", description=""))

    # Create taxonomy categories
    classification_repo.create_lean_category(
        LeanPracticeCategory(category_id="kaizen", name="Kaizen & Continuous Improvement", project_id=proj_id)
    )
    classification_repo.create_energy_category(
        EnergyEffectCategory(category_id="electricity", name="Electricity Consumption", project_id=proj_id)
    )
    service.create_category(
        project_id=proj_id,
        category_id="idle_reduction",
        name="Idle-Time Mitigation",
        description="Causal reduction of standby draw",
    )

    # Create 2 publications with 2 relations
    pub1_id = uuid4()
    pub2_id = uuid4()
    publication_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub1_id,
                title="Study 1",
                publication_year=2021,
            ),
            Publication(
                record_id=pub2_id,
                title="Study 2",
                publication_year=2022,
            ),
        ],
    )

    rel1_id = uuid4()
    rel1 = AnalyticalRelation(
        relation_id=rel1_id,
        project_id=proj_id,
        publication_id=pub1_id,
        latest_revision_id=uuid4(),
        group_item_id=uuid4(),
        item_index=1,
        source_practice="Kaizen Event",
        analytical_lean_category_id="kaizen",
        source_effect="Power reduction",
        analytical_energy_category_id="electricity",
        direction=RelationDirection.POSITIVE,
        approval_state=ClassificationApprovalState.APPROVED,
    )
    matrix_repo.save_analytical_relation(rel1)

    rel2_id = uuid4()
    rel2 = AnalyticalRelation(
        relation_id=rel2_id,
        project_id=proj_id,
        publication_id=pub2_id,
        latest_revision_id=uuid4(),
        group_item_id=uuid4(),
        item_index=1,
        source_practice="Kaizen Blitz",
        analytical_lean_category_id="kaizen",
        source_effect="Electricity savings",
        analytical_energy_category_id="electricity",
        direction=RelationDirection.POSITIVE,
        approval_state=ClassificationApprovalState.APPROVED,
    )
    matrix_repo.save_analytical_relation(rel2)

    # Sync and retrieve workspace
    data = service.get_mechanism_workspace_data(proj_id)
    assert len(data.pathways) == 2
    assert data.stats.unmapped_count == 2

    # Assign category to pathway 1
    p1 = data.pathways[0].pathway
    assigned_p1 = service.assign_mechanism_category(
        project_id=proj_id,
        pathway_id=p1.pathway_id,
        category_id="idle_reduction",
        is_review_synthesized=True,
        notes="Reviewer inferred mechanism based on process description.",
    )
    assert assigned_p1.analytical_mechanism_category_id == "idle_reduction"
    assert assigned_p1.is_review_synthesized is True
    assert assigned_p1.approval_state == ClassificationApprovalState.PENDING

    # Cannot approve unmapped pathway
    p2 = data.pathways[1].pathway
    with pytest.raises(MechanismAssignmentError):
        service.approve_mechanism_pathway(proj_id, p2.pathway_id, "reviewer_1")

    # Approve pathway 1
    approved_p1 = service.approve_mechanism_pathway(proj_id, p1.pathway_id, "lead_reviewer")
    assert approved_p1.approval_state == ClassificationApprovalState.APPROVED
    assert approved_p1.approved_by == "lead_reviewer"
    assert approved_p1.approved_at is not None

    # Check updated workspace data
    updated_data = service.get_mechanism_workspace_data(proj_id)
    assert updated_data.stats.mapped_count == 1
    assert updated_data.stats.approved_count == 1
    assert len(updated_data.synthesis_chains) == 1

    chain = updated_data.synthesis_chains[0]
    assert chain.lean_category_id == "kaizen"
    assert chain.mechanism_category_id == "idle_reduction"
    assert chain.energy_category_id == "electricity"
    assert chain.pathway_count == 1
    assert chain.publication_count == 1
    assert chain.relation_count == 1


def test_source_evidence_immutability(env):
    """Proves that Phase 9 source mechanism text remains 100% byte-for-byte immutable across category edits/deletions."""
    service: SynthesisMechanismService = env["service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]
    matrix_repo: SqliteSynthesisMatrixRepository = env["matrix_repo"]

    proj_id = "test-proj-immutability"
    project_repo.create(Project(project_id=proj_id, title="Immutability Project", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub_id,
                title="Study",
                publication_year=2023,
            )
        ],
    )

    rec = extraction_repo.create_record(
        ExtractionRecord(
            project_id=proj_id,
            publication_id=pub_id,
            template_id="lean_energy",
            template_version="1.0.0",
        )
    )

    original_source_text = "Reduced machine idle time lowered electricity consumption."
    group_item_id = uuid4()
    item = ExtractedGroupItemState(
        group_item_id=group_item_id,
        group_key="lean_energy_relationships",
        item_index=1,
        values=[
            ExtractedValueState(
                field_key="impact_mechanism",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value=original_source_text,
                source_locator="Table 1",
            ),
        ],
    )
    rev = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[item],
        )
    )

    rel_id = uuid4()
    rel = AnalyticalRelation(
        relation_id=rel_id,
        project_id=proj_id,
        publication_id=pub_id,
        latest_revision_id=rev.revision_id,
        group_item_id=group_item_id,
        item_index=1,
        source_practice="Kaizen",
        source_effect="Power",
        approval_state=ClassificationApprovalState.APPROVED,
    )
    matrix_repo.save_analytical_relation(rel)

    service.create_category(
        project_id=proj_id,
        category_id="idle_reduction",
        name="Idle-time reduction",
    )

    # 1. Sync
    pathways = service.synchronize_mechanism_pathways(proj_id)
    p_id = pathways[0].pathway_id
    assert pathways[0].source_mechanism_text == original_source_text

    # 2. Assign category
    service.assign_mechanism_category(proj_id, p_id, "idle_reduction")

    # 3. Re-assign / unassign category
    service.assign_mechanism_category(proj_id, p_id, None)

    # 4. Verify Phase 9 extraction revision is untouched
    persisted_rev = extraction_repo.get_latest_revision(proj_id, pub_id)
    assert persisted_rev is not None
    assert persisted_rev.group_items[0].values[0].text_value == original_source_text

    # 5. Verify pathway source mechanism text is untouched
    data = service.get_mechanism_workspace_data(proj_id)
    assert data.pathways[0].pathway.source_mechanism_text == original_source_text


def test_project_isolation(env):
    """Proves cross-project protection: project A category cannot be assigned to project B pathway."""
    service: SynthesisMechanismService = env["service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    matrix_repo: SqliteSynthesisMatrixRepository = env["matrix_repo"]

    proj_a = "proj-a"
    proj_b = "proj-b"
    project_repo.create(Project(project_id=proj_a, title="Project A", description=""))
    project_repo.create(Project(project_id=proj_b, title="Project B", description=""))

    service.create_category(proj_a, "cat_a", "Category A")
    service.create_category(proj_b, "cat_b", "Category B")

    rel_b = AnalyticalRelation(
        relation_id=uuid4(),
        project_id=proj_b,
        publication_id=uuid4(),
        latest_revision_id=uuid4(),
        group_item_id=uuid4(),
        item_index=1,
        source_practice="5S",
        source_effect="Power",
        approval_state=ClassificationApprovalState.APPROVED,
    )
    matrix_repo.save_analytical_relation(rel_b)
    pathways_b = service.synchronize_mechanism_pathways(proj_b)
    p_b_id = pathways_b[0].pathway_id

    # Assigning Project A's category to Project B's pathway fails with CategoryNotFoundError
    with pytest.raises(MechanismCategoryNotFoundError):
        service.assign_mechanism_category(proj_b, p_b_id, "cat_a")

    # Querying Project A's workspace returns 0 pathways
    data_a = service.get_mechanism_workspace_data(proj_a)
    assert len(data_a.pathways) == 0
    assert len(data_a.categories) == 1
    assert data_a.categories[0].category_id == "cat_a"


def test_complete_rev1_and_draft_rev2_uses_rev1(env):
    """Proves that when rev1 is COMPLETE and rev2 is DRAFT, synthesis strictly uses rev1."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-rev1-rev2"
    project_repo.create(Project(project_id=proj_id, title="Rev Test", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Study 1", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    group_item_id = uuid4()
    # Rev 1 = COMPLETE
    rev1 = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="rev1_reviewer",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen Rev1", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity Rev1", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Mechanism Rev1", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    # Rev 2 = DRAFT (newer, but incomplete draft)
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=2,
            reviewer_id="rev2_reviewer",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen Rev2 Draft", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity Rev2 Draft", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Mechanism Rev2 Draft", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    # 1. Matrix relations (Task 10.3) must resolve rev1
    relations = matrix_service.synchronize_analytical_relations(proj_id)
    assert len(relations) == 1
    assert relations[0].latest_revision_id == rev1.revision_id
    assert relations[0].source_practice == "Kaizen Rev1"
    assert relations[0].source_effect == "Electricity Rev1"

    # 2. Mechanism pathways (Task 10.4) must resolve rev1
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert len(pathways) == 1
    assert pathways[0].latest_revision_id == rev1.revision_id
    assert pathways[0].source_mechanism_text == "Mechanism Rev1"


def test_draft_only_extraction_excluded_from_synthesis(env):
    """Proves that a study with only DRAFT extractions is completely excluded from synthesis."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-draft-only"
    project_repo.create(Project(project_id=proj_id, title="Draft Only", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Draft Study", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    # Append DRAFT revision only
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="5S Draft", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Energy Draft", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Mechanism Draft", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    # Synthesis must be empty
    relations = matrix_service.synchronize_analytical_relations(proj_id)
    assert len(relations) == 0

    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert len(pathways) == 0


def test_later_complete_rev3_advances_synthesis(env):
    """Proves that when rev3 is marked COMPLETE after rev2 DRAFT, synthesis advances to rev3."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-rev3-advance"
    project_repo.create(Project(project_id=proj_id, title="Rev3 Test", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Study 1", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    group_item_id = uuid4()
    # Rev 1 = COMPLETE
    rev1 = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Rev1 Mechanism Text", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert pathways[0].latest_revision_id == rev1.revision_id
    assert pathways[0].source_mechanism_text == "Rev1 Mechanism Text"

    # Rev 2 = DRAFT -> still uses Rev 1
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=2,
            reviewer_id="reviewer_2",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen Draft", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity Draft", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Rev2 Draft Mechanism", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert pathways[0].latest_revision_id == rev1.revision_id
    assert pathways[0].source_mechanism_text == "Rev1 Mechanism Text"

    # Rev 3 = COMPLETE -> advances to Rev 3
    rev3 = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=3,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen Final", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity Final", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Rev3 Complete Mechanism Text", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert pathways[0].latest_revision_id == rev3.revision_id
    assert pathways[0].source_mechanism_text == "Rev3 Complete Mechanism Text"


def test_e10_absent_and_e11_present_produces_none_source_mechanism_text(env):
    """Proves that when E10 mechanism is absent and E11 moderating conditions is present, source_mechanism_text is None."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-e10-absent"
    project_repo.create(Project(project_id=proj_id, title="E10 Absent Test", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Context Study", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    group_item_id = uuid4()
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="5S", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Fuel", source_locator="Table 1"),
                        # E11 present, E10 absent
                        ExtractedValueState(field_key="moderating_conditions", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="High ambient operating temperature in factory.", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert len(pathways) == 1
    # Must NOT copy moderating conditions into source_mechanism_text
    assert pathways[0].source_mechanism_text is None


def test_e10_present_and_e11_present_exact_e10_wins(env):
    """Proves that when both E10 (mechanism) and E11 (context) are present, exact E10 text is captured."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-e10-e11-both"
    project_repo.create(Project(project_id=proj_id, title="Both E10 E11", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Both Study", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    group_item_id = uuid4()
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="TPM", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Preventative motor lubrication cuts frictional resistance.", source_locator="Table 1"),
                        ExtractedValueState(field_key="moderating_conditions", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Continuous assembly operations with high uptime.", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)
    assert len(pathways) == 1
    assert pathways[0].source_mechanism_text == "Preventative motor lubrication cuts frictional resistance."


def test_task_10_3_and_10_4_resolve_same_complete_evidence_revision(env):
    """Proves Task 10.3 AnalyticalRelation and Task 10.4 MechanismPathway share exact latest_revision_id."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-shared-rev"
    project_repo.create(Project(project_id=proj_id, title="Shared Rev", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Shared Study", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    group_item_id = uuid4()
    rev1 = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="VSM", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Peak Demand", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Staggering heavy furnace startup across shifts.", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    relations = matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)

    assert len(relations) == 1
    assert len(pathways) == 1
    assert relations[0].latest_revision_id == rev1.revision_id
    assert pathways[0].latest_revision_id == rev1.revision_id
    assert pathways[0].analytical_relation_id == relations[0].relation_id


def test_researcher_assignments_preserved_when_newer_draft_appears(env):
    """Proves researcher category assignment, approval, and review flag are preserved when a newer DRAFT revision is added."""
    service: SynthesisMechanismService = env["service"]
    matrix_service: SynthesisMatrixService = env["matrix_service"]
    project_repo: SqliteProjectRepository = env["project_repo"]
    publication_repo: SqliteProjectPublicationRepository = env["publication_repo"]
    extraction_repo: SqliteExtractionRepository = env["extraction_repo"]

    proj_id = "test-proj-preservation"
    project_repo.create(Project(project_id=proj_id, title="Preservation Test", description=""))

    pub_id = uuid4()
    publication_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Study", publication_year=2024)])

    rec = extraction_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )

    group_item_id = uuid4()
    rev1 = extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity", source_locator="Table 1"),
                        ExtractedValueState(field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Turning off idle conveyers.", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    # 1. Setup category and sync
    service.create_category(proj_id, "idle_cutoff", "Idle Cutoff")
    matrix_service.synchronize_analytical_relations(proj_id)
    pathways = service.synchronize_mechanism_pathways(proj_id)
    p_id = pathways[0].pathway_id

    # 2. Assign category, flag review_synthesized, approve
    service.assign_mechanism_category(proj_id, p_id, "idle_cutoff", is_review_synthesized=True, notes="Expert synthesis")
    service.approve_mechanism_pathway(proj_id, p_id, reviewer_id="lead_reviewer")

    # 3. Add newer DRAFT revision
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=2,
            reviewer_id="drafting_reviewer",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Kaizen Incomplete", source_locator="Table 1"),
                        ExtractedValueState(field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="Electricity Incomplete", source_locator="Table 1"),
                    ],
                )
            ],
        )
    )

    # 4. Re-sync matrix and mechanisms
    matrix_service.synchronize_analytical_relations(proj_id)
    re_synced = service.synchronize_mechanism_pathways(proj_id)
    assert len(re_synced) == 1
    p = re_synced[0]

    # Verify everything preserved and pointing to rev1
    assert p.latest_revision_id == rev1.revision_id
    assert p.source_mechanism_text == "Turning off idle conveyers."
    assert p.analytical_mechanism_category_id == "idle_cutoff"
    assert p.is_review_synthesized is True
    assert p.approval_state == ClassificationApprovalState.APPROVED
    assert p.approved_by == "lead_reviewer"
    assert p.notes == "Expert synthesis"

