"""Unit tests for SynthesisSnapshotService (Task 10.7).

Checkpoint C: explicit snapshot creation, monotonic per-project versioning,
deterministic hashing tied to COMPLETE extraction evidence, stored (not live)
content, criterion-level QA preservation, and JSON/CSV export.
"""

import csv
import io
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

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
from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    ConvertedValue,
    RelationDirection,
    ResearchGapLinkType,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import ProjectNotFoundError, SqliteProjectRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)
from app.repositories.synthesis_classification_repository import SqliteSynthesisClassificationRepository
from app.repositories.synthesis_context_repository import SqliteSynthesisContextRepository
from app.repositories.synthesis_gap_repository import SqliteSynthesisGapRepository
from app.repositories.synthesis_matrix_repository import SqliteSynthesisMatrixRepository
from app.repositories.synthesis_mechanism_repository import SqliteSynthesisMechanismRepository
from app.repositories.synthesis_snapshot_repository import SqliteSynthesisSnapshotRepository
from app.services.synthesis_context_service import default_synthesis_context_service
from app.services.synthesis_gap_service import default_synthesis_gap_service
from app.services.synthesis_mechanism_service import default_synthesis_mechanism_service
from app.services.synthesis_snapshot_service import (
    SnapshotExportError,
    SnapshotNotFoundError,
    SynthesisSnapshotService,
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
def service_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_snapshot_service.db"
    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))

    repos = {
        "snapshot": SqliteSynthesisSnapshotRepository(db_path),
        "matrix": SqliteSynthesisMatrixRepository(db_path),
        "mechanism": SqliteSynthesisMechanismRepository(db_path),
        "context": SqliteSynthesisContextRepository(db_path),
        "gap": SqliteSynthesisGapRepository(db_path),
        "classification": SqliteSynthesisClassificationRepository(db_path),
        "extraction": SqliteExtractionRepository(db_path),
        "publication": SqliteProjectPublicationRepository(db_path),
        "project": SqliteProjectRepository(db_path),
        "qa": SqliteQualityAssessmentRepository(db_path),
        "qa_config": SqliteProjectQualityAssessmentConfigurationRepository(db_path),
        "qa_catalog": SqliteQualityAssessmentCatalogRepository(db_path),
    }

    service = SynthesisSnapshotService(
        snapshot_repo=repos["snapshot"],
        matrix_repo=repos["matrix"],
        mechanism_repo=repos["mechanism"],
        context_repo=repos["context"],
        gap_repo=repos["gap"],
        classification_repo=repos["classification"],
        extraction_repo=repos["extraction"],
        publication_repo=repos["publication"],
        project_repo=repos["project"],
        qa_repo=repos["qa"],
        qa_config_repo=repos["qa_config"],
        qa_catalog_repo=repos["qa_catalog"],
    )
    return db_path, repos, service


def _seed_project(db_path: str, proj_id: str) -> None:
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Snapshot Project", description=""))


def _seed_evidence(db_path: str, proj_id: str) -> dict:
    """Seeds a COMPLETE extraction revision + relation + pathway + context link + gap."""
    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    pub_repo = SqliteProjectPublicationRepository(db_path)
    ext_repo = SqliteExtractionRepository(db_path)
    matrix_repo = SqliteSynthesisMatrixRepository(db_path)

    pub_id = uuid4()
    group_item_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Snapshot Study", publication_year=2024)])
    rec = ext_repo.create_record(
        ExtractionRecord(
            project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
        )
    )
    rev = ext_repo.append_revision(
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
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Single Minute Exchange of Die",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Compressed Air",
                            source_locator="Table 1",
                        ),
                    ],
                )
            ],
        )
    )

    rel_id = uuid4()
    matrix_repo.save_analytical_relation(
        AnalyticalRelation(
            relation_id=rel_id,
            project_id=proj_id,
            publication_id=pub_id,
            latest_revision_id=rev.revision_id,
            group_item_id=group_item_id,
            item_index=1,
            source_practice="SMED Setup",
            source_effect="Compressed Air",
            direction=RelationDirection.POSITIVE,
            approval_state=ClassificationApprovalState.APPROVED,
        )
    )

    default_synthesis_mechanism_service().synchronize_mechanism_pathways(proj_id)
    default_synthesis_context_service().synchronize_context_from_extraction(proj_id)

    pathway = SqliteSynthesisMechanismRepository(db_path).list_pathways(proj_id)[0]
    context_link = SqliteSynthesisContextRepository(db_path).list_links(proj_id)[0]

    gap_service = default_synthesis_gap_service()
    gap = gap_service.create_research_gap(
        project_id=proj_id,
        gap_type="thematic",
        title="Under-studied practice",
        rationale="Only one source covers SMED for compressed air.",
        researcher_id="researcher-1",
    )
    gap_service.link_evidence(
        project_id=proj_id,
        gap_id=str(gap.gap_id),
        link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
        target_id=rel_id,
    )

    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev_id": rev.revision_id,
        "relation_id": rel_id,
        "pathway_id": pathway.pathway_id,
        "context_link_id": context_link["link_id"],
    }


def _seed_qa_template(db_path: str, proj_id: str) -> QualityAssessmentTemplate:
    catalog = SqliteQualityAssessmentCatalogRepository(db_path)
    tool = QualityAssessmentTool(tool_id="qa_tool", name="QA Tool")
    template_id = uuid4()
    template = QualityAssessmentTemplate(
        template_id=template_id,
        tool_id="qa_tool",
        template_key="default",
        name="Default QA",
        version=1,
        criteria=[
            QualityAssessmentTemplateCriterion(
                criterion_id=uuid4(),
                template_id=template_id,
                display_order=1,
                question="Clear objectives?",
            )
        ],
    )
    catalog.create_tool(tool)
    catalog.create_template_version(template)

    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)
    config_repo.save_configuration(
        ProjectQualityAssessmentConfiguration(
            project_id=proj_id,
            tool_id="qa_tool",
            template_id=template.template_id,
        )
    )
    return template


# ---------------------------------------------------------------------------
# C1-C2: Explicit creation & versioning
# ---------------------------------------------------------------------------


def test_c1_create_snapshot_explicit(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c1"
    _seed_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)

    snap = service.create_snapshot(proj_id, "researcher-1")
    assert snap.project_id == proj_id
    assert snap.version == 1
    assert snap.actor == "researcher-1"
    assert len(snap.extraction_dataset_hash) == 64
    assert len(snap.classification_version) == 64
    assert len(snap.content_hash) == 64
    assert snap.content.project_id == proj_id
    assert len(snap.content.relations) == 1
    assert len(snap.content.mechanism_pathways) == 1
    assert len(snap.content.context_assignments) == 1
    assert len(snap.content.research_gaps) == 1
    assert len(snap.content.research_gap_links) == 1


def test_c2_versions_monotonic_per_project(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c2"
    _seed_project(db_path, proj_id)

    v1 = service.create_snapshot(proj_id, "researcher-1")
    v2 = service.create_snapshot(proj_id, "researcher-1")
    v3 = service.create_snapshot(proj_id, "researcher-1")
    assert [v1.version, v2.version, v3.version] == [1, 2, 3]

    versions = [s.version for s in service.list_snapshots(proj_id)]
    assert versions == [1, 2, 3]


def test_c2_versions_never_reused_across_recreation(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c2-reuse"
    _seed_project(db_path, proj_id)

    service.create_snapshot(proj_id, "r")
    service.create_snapshot(proj_id, "r")
    service.create_snapshot(proj_id, "r")
    # Re-creating identical content still yields a new version; never reuses 1.
    assert service.create_snapshot(proj_id, "r").version == 4


def test_c2_versions_independent_per_project(service_env):
    db_path, repos, service = service_env
    proj_a = "proj-c2a"
    proj_b = "proj-c2b"
    _seed_project(db_path, proj_a)
    _seed_project(db_path, proj_b)

    service.create_snapshot(proj_a, "r")
    service.create_snapshot(proj_a, "r")
    assert service.create_snapshot(proj_b, "r").version == 1
    assert service.create_snapshot(proj_b, "r").version == 2


# ---------------------------------------------------------------------------
# C3-C5: Deterministic hashes and COMPLETE-only semantics
# ---------------------------------------------------------------------------


def test_c3_dataset_hash_is_deterministic_across_identical_recreations(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c3"
    _seed_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)

    h1 = service.create_snapshot(proj_id, "r").extraction_dataset_hash
    h2 = service.create_snapshot(proj_id, "r").extraction_dataset_hash
    assert h1 == h2


def test_c4_relevant_data_change_changes_dataset_hash(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c4"
    _seed_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)

    h_before = service.create_snapshot(proj_id, "r").extraction_dataset_hash

    ext_repo = repos["extraction"]
    rec = ext_repo.list_records(proj_id)[0]
    pub_id = rec.publication_id
    ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=2,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Changed Practice Value",
                            source_locator="Table 1",
                        )
                    ],
                )
            ],
        )
    )

    h_after = service.create_snapshot(proj_id, "r").extraction_dataset_hash
    assert h_before != h_after


def test_c5_draft_revision_does_not_change_dataset_hash(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c5"
    _seed_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)

    h_before = service.create_snapshot(proj_id, "r").extraction_dataset_hash

    ext_repo = repos["extraction"]
    rec = ext_repo.list_records(proj_id)[0]
    ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=seeded["pub_id"],
            revision_index=2,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Draft practice value",
                            source_locator="Table 1",
                        )
                    ],
                )
            ],
        )
    )

    h_after = service.create_snapshot(proj_id, "r").extraction_dataset_hash
    assert h_before == h_after


# ---------------------------------------------------------------------------
# C6-C8: Stored content & QA preservation
# ---------------------------------------------------------------------------


def test_c6_snapshot_content_is_stored_state_not_live_pointer(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c6"
    _seed_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)

    snap = service.create_snapshot(proj_id, "r")
    assert len(snap.content.relations) == 1

    # Mutating the synthesis state after snapshot creation must not change the stored snapshot.
    matrix_repo = repos["matrix"]
    rel = matrix_repo.list_analytical_relations(proj_id)[0]
    matrix_repo.update_converted_value(
        proj_id,
        rel.relation_id,
        ConvertedValue(transformed_value=999.0, transformed_unit="kwh", conversion_rule="changed"),
    )

    stored = service.get_snapshot_by_version(proj_id, snap.version)
    assert len(stored.content.relations) == 1
    assert stored.content.relations[0].converted_value is None


def test_c7_qa_profile_is_criterion_level(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c7"
    _seed_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)
    template = _seed_qa_template(db_path, proj_id)

    qa_repo = repos["qa"]
    assessment_id = uuid4()
    qa_repo.save_assessment(
        QualityAssessment(
            assessment_id=assessment_id,
            project_id=proj_id,
            publication_id=seeded["pub_id"],
            reviewer_id="reviewer_1",
            template_id=template.template_id,
            responses=[
                QualityAssessmentResponse(
                    assessment_id=assessment_id,
                    criterion_id=template.criteria[0].criterion_id,
                    question_snapshot="Clear objectives?",
                    response_value=QualityAssessmentResponseValue.YES,
                    justification="Described in introduction.",
                )
            ],
        )
    )

    snap = service.create_snapshot(proj_id, "r")
    assert len(snap.content.qa_profiles) == 1
    profile = snap.content.qa_profiles[0]
    assert profile.criteria_assessments[0].question_text == "Clear objectives?"
    assert profile.criteria_assessments[0].response_value == "YES"
    assert "score" not in profile.model_dump()


def test_c8_classification_version_derived_from_configuration(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c8"
    _seed_project(db_path, proj_id)

    version_without_qa = service.create_snapshot(proj_id, "r").classification_version

    template = _seed_qa_template(db_path, proj_id)
    _seed_evidence(db_path, proj_id)

    version_with_qa = service.create_snapshot(proj_id, "r").classification_version
    assert version_with_qa != version_without_qa
    assert len(version_with_qa) == 64
    assert template.template_id is not None


# ---------------------------------------------------------------------------
# C9-C11: Read operations & error semantics
# ---------------------------------------------------------------------------


def test_c9_get_snapshot_by_version_and_id(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c9"
    _seed_project(db_path, proj_id)
    snap = service.create_snapshot(proj_id, "r")

    by_version = service.get_snapshot_by_version(proj_id, 1)
    assert by_version.snapshot_id == snap.snapshot_id

    by_id = service.get_snapshot(proj_id, str(snap.snapshot_id))
    assert by_id.version == 1


def test_c10_get_missing_snapshot_raises(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c10"
    _seed_project(db_path, proj_id)

    with pytest.raises(SnapshotNotFoundError):
        service.get_snapshot_by_version(proj_id, 99)
    with pytest.raises(SnapshotNotFoundError):
        service.get_snapshot(proj_id, str(uuid4()))


def test_c11_missing_project_raises(service_env):
    db_path, repos, service = service_env
    with pytest.raises(ProjectNotFoundError):
        service.create_snapshot("missing-project", "r")
    with pytest.raises(ProjectNotFoundError):
        service.list_snapshots("missing-project")


# ---------------------------------------------------------------------------
# C12-C14: Export contracts
# ---------------------------------------------------------------------------


def test_c12_json_export_is_complete(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c12"
    _seed_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)
    snap = service.create_snapshot(proj_id, "r")

    exported = service.export_snapshot(proj_id, snap.version, "json")
    assert exported["snapshot_id"] == str(snap.snapshot_id)
    assert exported["version"] == 1
    assert exported["extraction_dataset_hash"] == snap.extraction_dataset_hash
    assert len(exported["content"]["relations"]) == 1
    assert len(exported["content"]["mechanism_pathways"]) == 1
    assert len(exported["content"]["research_gaps"]) == 1


def test_c13_csv_export_relations_matrix(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c13"
    _seed_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)
    snap = service.create_snapshot(proj_id, "r")

    exported = service.export_snapshot(proj_id, snap.version, "csv")
    assert exported["format"] == "csv"
    reader = csv.DictReader(io.StringIO(exported["content_csv"]))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["source_practice"] == "SMED Setup"
    assert rows[0]["direction"] == "positive"


def test_c14_unsupported_export_format_raises(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c14"
    _seed_project(db_path, proj_id)
    snap = service.create_snapshot(proj_id, "r")
    with pytest.raises(SnapshotExportError):
        service.export_snapshot(proj_id, snap.version, "xml")


# ---------------------------------------------------------------------------
# C15-C16: Project isolation & no update path
# ---------------------------------------------------------------------------


def test_c15_cross_project_isolation(service_env):
    db_path, repos, service = service_env
    proj_a = "proj-c15a"
    proj_b = "proj-c15b"
    _seed_project(db_path, proj_a)
    _seed_project(db_path, proj_b)
    _seed_evidence(db_path, proj_a)

    snap_a = service.create_snapshot(proj_a, "r")
    snap_b = service.create_snapshot(proj_b, "r")
    assert len(snap_a.content.relations) == 1
    assert len(snap_b.content.relations) == 0

    # Project B's version 1 is its own snapshot, never project A's.
    assert service.get_snapshot_by_version(proj_b, 1).snapshot_id == snap_b.snapshot_id
    # Project A's snapshot_id is not retrievable from project B.
    with pytest.raises(SnapshotNotFoundError):
        service.get_snapshot(proj_b, str(snap_a.snapshot_id))


def test_c16_no_update_or_delete_path(service_env):
    db_path, repos, service = service_env
    proj_id = "proj-c16"
    _seed_project(db_path, proj_id)

    assert not hasattr(service, "update_snapshot")
    assert not hasattr(service, "delete_snapshot")
    assert not hasattr(repos["snapshot"], "update_snapshot")

    snap = service.create_snapshot(proj_id, "r")
    stored = service.get_snapshot_by_version(proj_id, snap.version)
    assert stored.content_hash == snap.content_hash
