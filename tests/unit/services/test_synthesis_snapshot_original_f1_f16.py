"""Original Task 10.7 adversarial F1-F16 acceptance checklist (evidence-based).

This module implements the ORIGINAL F1-F16 checklist verbatim for the Synthesis
Snapshot engine, proving that snapshots are immutable reproductions of the
eligible COMPLETE extraction dataset:

F1   rev1 COMPLETE -> create S1 -> rev2 DRAFT. PROVE S1 unchanged.
F2   rev1 COMPLETE -> create S1 -> rev3 COMPLETE changes relevant evidence ->
     create S2. PROVE live synthesis advances appropriately; S1 remains
     unchanged; S2 represents newer state; S1 and S2 differ where relevant.
F3   create S1 -> change terminology classification. PROVE S1 unchanged.
F4   create S1 -> change mechanism classification. PROVE S1 unchanged.
F5   create S1 -> change context classification. PROVE S1 unchanged.
F6   create S1 -> edit a Research Gap. PROVE S1 unchanged.
F7   create S1 -> delete/change live Research Gap or live analytical evidence
     where allowed. PROVE S1 remains retrievable and reproducible.
F8   assemble logically identical synthesis input in different ordering.
     PROVE same deterministic dataset/content hash.
F9   change relevant eligible evidence. PROVE dataset/content identity changes.
F10  DRAFT-only relation/revision. PROVE excluded from eligible snapshot
     dataset identity/evidence.
F11  cross-project snapshot access. PROVE Project A cannot retrieve/export
     Project B snapshot; snapshot creation is project-scoped.
F12  attempt to mutate historical snapshot content. PROVE no repository/service
     /API mutation path exists and persisted historical content is unchanged.
F13  criterion-level QA. PROVE criterion responses + justifications preserved;
     no aggregate QA score, quality tier, or confidence weighting.
F14  attempt arbitrary fields quality_score, confidence, snapshot_score.
     PROVE rejected/not part of the Task 10.7 contract.
F15  snapshot creation. PROVE explicit researcher action only; seeding/changing
     synthesis state MUST NOT auto-create a snapshot.
F16  Task 10.7 implementation diff. PROVE no built-in AI/LLM dependency or
     automatic AI interpretation.

Revision status note: the codebase models DRAFT as the non-eligible status
``ExtractionCompletenessStatus.IN_PROGRESS`` (there is no literal "DRAFT" enum).
All F1/F2 tests therefore use IN_PROGRESS for the draft revision and assert that
only COMPLETE revisions drive the dataset identity.
"""

import csv
import io
import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.main import app
from app.api.routers.synthesis_snapshots import router as synthesis_snapshot_router
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
    QAProfileSummary,
    RelationDirection,
    ResearchGapLinkType,
    SynthesisSnapshot,
    SynthesisSnapshotContent,
    TermType,
    build_extraction_dataset_items,
    compute_content_hash,
    compute_extraction_dataset_hash,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
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
from app.services.synthesis_classification_service import default_synthesis_classification_service
from app.services.synthesis_context_service import default_synthesis_context_service
from app.services.synthesis_gap_service import default_synthesis_gap_service
from app.services.synthesis_matrix_service import default_synthesis_matrix_service
from app.services.synthesis_mechanism_service import default_synthesis_mechanism_service
from app.services.synthesis_snapshot_service import (
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
    db_path = tmp_path / "test_original_f1_f16.db"
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


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_original_f1_f16_api.db"
    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))
    return TestClient(app), db_path


def _seed_project(db_path: str, proj_id: str) -> None:
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Snapshot Project", description=""))


def _register_template(db_path: str) -> None:
    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )


def _add_publication(db_path: str, proj_id: str) -> UUID:
    pub_id = uuid4()
    SqliteProjectPublicationRepository(db_path).add_publications(
        proj_id, [Publication(record_id=pub_id, title="Snapshot Study", publication_year=2024)]
    )
    return pub_id


def _append_revision(
    db_path: str,
    rec: ExtractionRecord,
    proj_id: str,
    pub_id: UUID,
    revision_index: int,
    status: ExtractionCompletenessStatus,
    group_item_id: UUID | None = None,
    practice: str = "Single Minute Exchange of Die",
    effect: str = "Compressed Air",
) -> ExtractionRevision:
    ext_repo = SqliteExtractionRepository(db_path)
    return ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=revision_index,
            reviewer_id="reviewer_1",
            completeness_status=status,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id or uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value=practice,
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value=effect,
                            source_locator="Table 1",
                        ),
                    ],
                )
            ],
        )
    )


def _save_relation(
    db_path: str, proj_id: str, pub_id: UUID, rev: ExtractionRevision, group_item_id: UUID
) -> str:
    relation_id = uuid4()
    SqliteSynthesisMatrixRepository(db_path).save_analytical_relation(
        AnalyticalRelation(
            relation_id=relation_id,
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
    return str(relation_id)


def _seed_baseline(db_path: str, proj_id: str) -> dict:
    """Seeds COMPLETE rev1 + relation + pathway + context link + gap (full evidence)."""
    _register_template(db_path)
    pub_id = _add_publication(db_path, proj_id)
    rec = SqliteExtractionRepository(db_path).create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
    )
    group_item_id = uuid4()
    rev = _append_revision(
        db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
    )
    relation_id = _save_relation(db_path, proj_id, pub_id, rev, group_item_id)

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
        target_id=relation_id,
    )

    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev_id": rev.revision_id,
        "relation_id": relation_id,
        "pathway_id": pathway.pathway_id,
        "context_link_id": context_link["link_id"],
        "gap_id": str(gap.gap_id),
        "record": rec,
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

    SqliteProjectQualityAssessmentConfigurationRepository(db_path).save_configuration(
        ProjectQualityAssessmentConfiguration(
            project_id=proj_id,
            tool_id="qa_tool",
            template_id=template.template_id,
        )
    )
    return template


# ---------------------------------------------------------------------------
# F1: COMPLETE snapshot survives a later DRAFT revision unchanged
# ---------------------------------------------------------------------------


class TestF1SnapshotUnchangedAfterDraftRevision:
    def test_s1_content_hash_dataset_hash_and_content_frozen(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f1"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        group_item_id = uuid4()
        rev1 = _append_revision(
            db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
        )
        _save_relation(db_path, proj_id, pub_id, rev1, group_item_id)

        s1 = service.create_snapshot(proj_id, "researcher-1")
        content_before = s1.content.model_dump(mode="json")

        # rev2 DRAFT (IN_PROGRESS) with changed evidence
        _append_revision(
            db_path,
            rec,
            proj_id,
            pub_id,
            2,
            ExtractionCompletenessStatus.IN_PROGRESS,
            practice="Kanban",
            effect="Electrical Consumption",
        )

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert stored.content_hash == s1.content_hash
        assert stored.extraction_dataset_hash == s1.extraction_dataset_hash
        assert stored.content.model_dump(mode="json") == content_before

    def test_s1_references_exact_revision_group_item_and_publication(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f1-ids"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        group_item_id = uuid4()
        rev1 = _append_revision(
            db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
        )
        _save_relation(db_path, proj_id, pub_id, rev1, group_item_id)

        s1 = service.create_snapshot(proj_id, "researcher-1")
        _append_revision(
            db_path, rec, proj_id, pub_id, 2, ExtractionCompletenessStatus.IN_PROGRESS, practice="Kanban"
        )

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        rel = stored.content.relations[0]
        assert rel.latest_revision_id == rev1.revision_id
        assert rel.group_item_id == group_item_id
        assert rel.publication_id == pub_id

    def test_live_complete_resolution_never_advances_to_draft(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f1-live"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        group_item_id = uuid4()
        rev1 = _append_revision(
            db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
        )
        s1 = service.create_snapshot(proj_id, "researcher-1")

        _append_revision(
            db_path, rec, proj_id, pub_id, 2, ExtractionCompletenessStatus.IN_PROGRESS, practice="Kanban"
        )
        s2 = service.create_snapshot(proj_id, "researcher-1")

        # The draft revision is excluded from the eligible dataset identity.
        assert s2.extraction_dataset_hash == s1.extraction_dataset_hash
        latest = repos["extraction"].get_latest_complete_revision(proj_id, pub_id)
        assert latest is not None
        assert latest.revision_id == rev1.revision_id


# ---------------------------------------------------------------------------
# F2: a later COMPLETE revision advances live synthesis but S1 stays frozen
# ---------------------------------------------------------------------------


class TestF2Snapshot1FrozenWhenSynthesisAdvances:
    def test_s1_frozen_s2_newer_and_they_differ(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f2"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        group_item_id = uuid4()
        rev1 = _append_revision(
            db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
        )
        _save_relation(db_path, proj_id, pub_id, rev1, group_item_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")
        content_before = s1.content.model_dump(mode="json")

        # rev2 DRAFT, then rev3 COMPLETE changes relevant evidence.
        _append_revision(
            db_path, rec, proj_id, pub_id, 2, ExtractionCompletenessStatus.IN_PROGRESS, practice="Kanban"
        )
        rev3 = _append_revision(
            db_path,
            rec,
            proj_id,
            pub_id,
            3,
            ExtractionCompletenessStatus.COMPLETE,
            group_item_id,
            practice="Kanban",
            effect="Electrical Consumption",
        )

        # Live synthesis advances to rev3; re-materialize the matrix relation.
        latest = repos["extraction"].get_latest_complete_revision(proj_id, pub_id)
        assert latest is not None
        assert latest.revision_id == rev3.revision_id
        default_synthesis_matrix_service().synchronize_analytical_relations(proj_id)

        s2 = service.create_snapshot(proj_id, "researcher-1")

        # S1 unchanged.
        s1_stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert s1_stored.content_hash == s1.content_hash
        assert s1_stored.extraction_dataset_hash == s1.extraction_dataset_hash
        assert s1_stored.content.model_dump(mode="json") == content_before
        assert s1_stored.content.relations[0].latest_revision_id == rev1.revision_id

        # S2 represents newer state.
        assert s2.extraction_dataset_hash != s1.extraction_dataset_hash
        assert s2.content_hash != s1.content_hash
        assert s2.content.relations[0].latest_revision_id == rev3.revision_id


# ---------------------------------------------------------------------------
# F3-F7: historical content reloaded from persistence, not re-read live
# ---------------------------------------------------------------------------


class TestF3TerminologyClassificationChangeDoesNotAffectS1:
    def test_s1_unchanged_after_terminology_change(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f3"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")
        content_before = s1.content.model_dump(mode="json")

        classification = default_synthesis_classification_service()
        classification.create_lean_category(proj_id, "cat-lean-1", "Setup Reduction")
        classification.set_term_mapping(
            proj_id, TermType.LEAN_PRACTICE, "Single Minute Exchange of Die", "cat-lean-1"
        )

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert stored.content_hash == s1.content_hash
        assert stored.content.model_dump(mode="json") == content_before
        assert stored.content.term_mappings == []
        assert stored.content.lean_categories == []
        assert seeded["relation_id"] is not None


class TestF4MechanismClassificationChangeDoesNotAffectS1:
    def test_s1_unchanged_after_mechanism_category_added(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f4"
        _seed_project(db_path, proj_id)
        _seed_baseline(db_path, proj_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")
        content_before = s1.content.model_dump(mode="json")

        default_synthesis_mechanism_service().create_category(proj_id, "mech-cat-1", "Mechanism Category")

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert stored.content_hash == s1.content_hash
        assert stored.content.model_dump(mode="json") == content_before
        assert stored.content.mechanism_categories == []


class TestF5ContextClassificationChangeDoesNotAffectS1:
    def test_s1_unchanged_after_context_category_added(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f5"
        _seed_project(db_path, proj_id)
        _seed_baseline(db_path, proj_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")
        content_before = s1.content.model_dump(mode="json")

        default_synthesis_context_service().create_context_category(proj_id, "ctx-cat-1", "Context Category")

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert stored.content_hash == s1.content_hash
        assert stored.content.model_dump(mode="json") == content_before
        assert stored.content.context_categories == []


class TestF6ResearchGapEditDoesNotAffectS1:
    def test_s1_unchanged_after_gap_edited(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f6"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")
        content_before = s1.content.model_dump(mode="json")

        default_synthesis_gap_service().update_research_gap(
            proj_id, seeded["gap_id"], title="Changed gap title"
        )

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert stored.content_hash == s1.content_hash
        assert stored.content.model_dump(mode="json") == content_before
        assert stored.content.research_gaps[0].title == "Under-studied practice"


class TestF7DeleteLiveGapAndChangeLiveEvidenceS1StillReproducible:
    def test_s1_retrievable_and_frozen_after_live_deletion_and_change(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f7"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")

        # Delete the live research gap and change live analytical evidence.
        default_synthesis_gap_service().delete_research_gap(proj_id, seeded["gap_id"])
        repos["matrix"].update_converted_value(
            proj_id,
            seeded["relation_id"],
            ConvertedValue(transformed_value=42.0, transformed_unit="kwh", conversion_rule="changed"),
        )
        assert default_synthesis_gap_service().list_research_gaps(proj_id) == []

        stored = service.get_snapshot_by_version(proj_id, s1.version)
        assert stored.snapshot_id == s1.snapshot_id
        assert stored.content_hash == s1.content_hash
        assert len(stored.content.research_gaps) == 1
        assert stored.content.research_gaps[0].gap_id == UUID(seeded["gap_id"])
        assert stored.content.relations[0].converted_value is None


# ---------------------------------------------------------------------------
# F8: ordering-insensitive deterministic identity
# ---------------------------------------------------------------------------


class TestF8OrderingInsensitiveIdentity:
    def test_dataset_hash_stable_under_group_item_reordering(self):
        gi_a = ExtractedGroupItemState(
            group_item_id=uuid4(),
            group_key="lean_energy_relationships",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="lean_practice",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="5S",
                    source_locator="Table 1",
                )
            ],
        )
        gi_b = ExtractedGroupItemState(
            group_item_id=uuid4(),
            group_key="lean_energy_relationships",
            item_index=2,
            values=[
                ExtractedValueState(
                    field_key="energy_effect_indicator",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="reduction",
                    source_locator="Table 1",
                )
            ],
        )
        rev = ExtractionRevision(
            record_id=uuid4(),
            project_id="p",
            publication_id=uuid4(),
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[gi_a, gi_b],
        )
        h1 = compute_extraction_dataset_hash(build_extraction_dataset_items([rev]))
        rev2 = rev.model_copy(update={"group_items": [gi_b, gi_a]})
        h2 = compute_extraction_dataset_hash(build_extraction_dataset_items([rev2]))
        assert h1 == h2

    def test_content_hash_stable_under_list_reversal(self):
        rel_a = AnalyticalRelation(
            relation_id=uuid4(),
            project_id="p",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=uuid4(),
            item_index=1,
            source_practice="SMED Setup",
            source_effect="Compressed Air",
        )
        rel_b = rel_a.model_copy(
            update={
                "relation_id": uuid4(),
                "group_item_id": uuid4(),
                "source_practice": "Kanban",
                "source_effect": "Electrical Consumption",
            }
        )
        base = SynthesisSnapshotContent(project_id="p", relations=[rel_a, rel_b])
        reversed_content = base.model_copy(update={"relations": [rel_b, rel_a]})
        assert compute_content_hash(base) == compute_content_hash(reversed_content)


# ---------------------------------------------------------------------------
# F9: changing eligible evidence changes the dataset/content identity
# ---------------------------------------------------------------------------


class TestF9EvidenceChangeChangesIdentity:
    def test_dataset_and_content_identity_change_with_complete_revision(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f9"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        group_item_id = uuid4()
        rev1 = _append_revision(
            db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
        )
        _save_relation(db_path, proj_id, pub_id, rev1, group_item_id)
        s1 = service.create_snapshot(proj_id, "researcher-1")

        _append_revision(
            db_path, rec, proj_id, pub_id, 2, ExtractionCompletenessStatus.IN_PROGRESS, practice="Kanban"
        )
        _append_revision(
            db_path,
            rec,
            proj_id,
            pub_id,
            3,
            ExtractionCompletenessStatus.COMPLETE,
            group_item_id,
            practice="Kanban",
            effect="Electrical Consumption",
        )
        default_synthesis_matrix_service().synchronize_analytical_relations(proj_id)
        s2 = service.create_snapshot(proj_id, "researcher-1")

        assert s2.extraction_dataset_hash != s1.extraction_dataset_hash
        assert s2.content_hash != s1.content_hash


# ---------------------------------------------------------------------------
# F10: DRAFT-only revisions are excluded from eligible dataset identity
# ---------------------------------------------------------------------------


class TestF10DraftOnlyRevisionExcluded:
    def test_draft_only_project_snapshot_is_effectively_empty(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f10"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        _append_revision(db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.IN_PROGRESS)

        snap = service.create_snapshot(proj_id, "researcher-1")
        assert snap.content.relations == []
        empty_hash = compute_extraction_dataset_hash([])
        assert snap.extraction_dataset_hash == empty_hash

    def test_draft_after_complete_keeps_identity(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f10b"
        _seed_project(db_path, proj_id)
        _register_template(db_path)
        pub_id = _add_publication(db_path, proj_id)
        rec = SqliteExtractionRepository(db_path).create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        group_item_id = uuid4()
        rev1 = _append_revision(
            db_path, rec, proj_id, pub_id, 1, ExtractionCompletenessStatus.COMPLETE, group_item_id
        )
        s1 = service.create_snapshot(proj_id, "researcher-1")

        _append_revision(
            db_path, rec, proj_id, pub_id, 2, ExtractionCompletenessStatus.IN_PROGRESS, practice="Kanban"
        )
        s2 = service.create_snapshot(proj_id, "researcher-1")

        assert s2.extraction_dataset_hash == s1.extraction_dataset_hash
        assert rev1.revision_id is not None


# ---------------------------------------------------------------------------
# F11: cross-project isolation for retrieval, export, and creation
# ---------------------------------------------------------------------------


class TestF11CrossProjectIsolation:
    def test_project_b_cannot_retrieve_project_a_snapshot(self, service_env):
        db_path, repos, service = service_env
        proj_a = "proj-f11a"
        proj_b = "proj-f11b"
        _seed_project(db_path, proj_a)
        _seed_project(db_path, proj_b)
        _seed_baseline(db_path, proj_a)

        snap_a = service.create_snapshot(proj_a, "researcher-1")
        snap_b = service.create_snapshot(proj_b, "researcher-1")

        assert len(snap_a.content.relations) == 1
        assert len(snap_b.content.relations) == 0

        with pytest.raises(SnapshotNotFoundError):
            service.get_snapshot(proj_b, str(snap_a.snapshot_id))
        assert service.get_snapshot_by_version(proj_b, 1).snapshot_id == snap_b.snapshot_id

    def test_export_of_one_project_never_contains_other_project_data(self, service_env):
        db_path, repos, service = service_env
        proj_a = "proj-f11x"
        proj_b = "proj-f11y"
        _seed_project(db_path, proj_a)
        _seed_project(db_path, proj_b)
        _seed_baseline(db_path, proj_a)

        snap_a = service.create_snapshot(proj_a, "researcher-1")
        service.create_snapshot(proj_b, "researcher-1")

        exported_a = service.export_snapshot(proj_a, snap_a.version, "json")
        exported_b = service.export_snapshot(proj_b, 1, "json")
        assert len(exported_a["content"]["relations"]) == 1
        assert exported_b["content"]["relations"] == []
        for rel in exported_a["content"]["relations"]:
            assert rel["project_id"] == proj_a

    def test_api_creation_and_retrieval_are_project_scoped(self, client):
        test_client, db_path = client
        proj_a = "proj-f11-api-a"
        proj_b = "proj-f11-api-b"
        _seed_project(db_path, proj_a)
        _seed_project(db_path, proj_b)
        _seed_baseline(db_path, proj_a)

        resp_a = test_client.post(f"/api/v1/projects/{proj_a}/synthesis/snapshots", json={"actor": "researcher-1"})
        assert resp_a.status_code == 201
        resp_b = test_client.post(f"/api/v1/projects/{proj_b}/synthesis/snapshots", json={"actor": "researcher-1"})
        assert resp_b.status_code == 201

        detail_a = test_client.get(f"/api/v1/projects/{proj_a}/synthesis/snapshots/1")
        detail_b = test_client.get(f"/api/v1/projects/{proj_b}/synthesis/snapshots/1")
        assert detail_a.status_code == 200
        assert detail_b.status_code == 200
        assert len(detail_a.json()["content"]["relations"]) == 1
        assert detail_b.json()["content"]["relations"] == []


# ---------------------------------------------------------------------------
# F12: no repository/service/API mutation path; persisted content unchanged
# ---------------------------------------------------------------------------


class TestF12NoMutationPath:
    def test_no_update_or_delete_service_or_repo_methods(self, service_env):
        db_path, repos, service = service_env
        assert not hasattr(service, "update_snapshot")
        assert not hasattr(service, "delete_snapshot")
        assert not hasattr(repos["snapshot"], "update_snapshot")
        assert not hasattr(repos["snapshot"], "delete_snapshot")

    def test_router_exposes_no_mutating_methods(self):
        allowed = {"GET", "POST"}
        for route in synthesis_snapshot_router.routes:
            methods = set(getattr(route, "methods", set()) or set())
            assert methods.issubset(allowed), f"Mutating route found: {methods} -> {route.path}"

    def test_api_rejects_put_patch_delete(self, client):
        test_client, db_path = client
        proj_id = "proj-f12-api"
        _seed_project(db_path, proj_id)
        test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "researcher-1"})

        assert test_client.put(f"/api/v1/projects/{proj_id}/synthesis/snapshots/1", json={}).status_code == 405
        assert test_client.patch(f"/api/v1/projects/{proj_id}/synthesis/snapshots/1", json={}).status_code == 405
        assert test_client.delete(f"/api/v1/projects/{proj_id}/synthesis/snapshots/1").status_code == 405

    def test_persisted_content_unchanged_after_live_mutation(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f12-persist"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)
        snap = service.create_snapshot(proj_id, "researcher-1")

        conn = sqlite3.connect(db_path)
        row_before = conn.execute(
            "SELECT content_json FROM synthesis_snapshots WHERE snapshot_id = ?",
            (str(snap.snapshot_id),),
        ).fetchone()
        conn.close()

        repos["matrix"].update_converted_value(
            proj_id,
            seeded["relation_id"],
            ConvertedValue(transformed_value=7.0, transformed_unit="kwh", conversion_rule="tamper"),
        )
        default_synthesis_gap_service().delete_research_gap(proj_id, seeded["gap_id"])

        conn = sqlite3.connect(db_path)
        row_after = conn.execute(
            "SELECT content_json FROM synthesis_snapshots WHERE snapshot_id = ?",
            (str(snap.snapshot_id),),
        ).fetchone()
        conn.close()
        assert row_before[0] == row_after[0]

    def test_version_conflict_raises_integrity_error(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f12-conflict"
        _seed_project(db_path, proj_id)
        snap = service.create_snapshot(proj_id, "researcher-1")
        duplicate = snap.model_copy(update={"snapshot_id": uuid4()})
        with pytest.raises(sqlite3.IntegrityError):
            repos["snapshot"].save_snapshot(duplicate)


# ---------------------------------------------------------------------------
# F13: criterion-level QA without aggregate score / quality tier / confidence
# ---------------------------------------------------------------------------


class TestF13CriterionLevelQA:
    def test_criterion_responses_and_justifications_preserved(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f13"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)
        template = _seed_qa_template(db_path, proj_id)

        assessment_id = uuid4()
        repos["qa"].save_assessment(
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
                        justification="Described in the introduction.",
                    )
                ],
            )
        )

        snap = service.create_snapshot(proj_id, "researcher-1")
        assert len(snap.content.qa_profiles) == 1
        criterion = snap.content.qa_profiles[0].criteria_assessments[0]
        assert criterion.question_text == "Clear objectives?"
        assert criterion.response_value == "YES"
        assert criterion.justification == "Described in the introduction."

    def test_absence_of_aggregate_score_quality_tier_and_confidence(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f13-absence"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)
        template = _seed_qa_template(db_path, proj_id)

        assessment_id = uuid4()
        repos["qa"].save_assessment(
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
                        justification="Described.",
                    )
                ],
            )
        )

        snap = service.create_snapshot(proj_id, "researcher-1")
        profile_dump = snap.content.qa_profiles[0].model_dump()
        assert "score" not in profile_dump
        assert "quality_tier" not in profile_dump
        assert "confidence" not in profile_dump

        qa_fields = set(QAProfileSummary.model_fields)
        assert "score" not in qa_fields
        assert "quality_tier" not in qa_fields
        assert "confidence" not in qa_fields


# ---------------------------------------------------------------------------
# F14: arbitrary score/confidence/tier fields are rejected
# ---------------------------------------------------------------------------


class TestF14ArbitraryFieldsRejected:
    def test_domain_models_reject_snapshot_score_and_confidence(self):
        with pytest.raises(ValidationError):
            SynthesisSnapshot(
                snapshot_id=uuid4(),
                project_id="proj-f14",
                version=1,
                actor="r",
                extraction_dataset_hash="a" * 64,
                classification_version="b" * 64,
                content_hash="c" * 64,
                content=SynthesisSnapshotContent(project_id="proj-f14"),
                snapshot_score=0.9,
            )
        with pytest.raises(ValidationError):
            SynthesisSnapshotContent(
                project_id="proj-f14",
                confidence=0.9,
            )
        with pytest.raises(ValidationError):
            QAProfileSummary(
                assessment_id=uuid4(),
                template_id=uuid4(),
                reviewer_id="r",
                quality_score=0.9,
            )

    def test_api_rejects_arbitrary_snapshot_fields(self, client):
        test_client, db_path = client
        proj_id = "proj-f14-api"
        _seed_project(db_path, proj_id)
        resp = test_client.post(
            f"/api/v1/projects/{proj_id}/synthesis/snapshots",
            json={"actor": "researcher-1", "quality_score": 0.9},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# F15: explicit researcher action only; seeding never auto-creates
# ---------------------------------------------------------------------------


class TestF15ExplicitResearcherActionOnly:
    def test_seeding_and_changes_never_auto_create_snapshot(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-f15"
        _seed_project(db_path, proj_id)
        seeded = _seed_baseline(db_path, proj_id)

        classification = default_synthesis_classification_service()
        classification.create_lean_category(proj_id, "cat-lean-1", "Setup Reduction")
        default_synthesis_mechanism_service().create_category(proj_id, "mech-cat-1", "Mechanism Category")
        default_synthesis_context_service().create_context_category(proj_id, "ctx-cat-1", "Context Category")
        default_synthesis_gap_service().update_research_gap(proj_id, seeded["gap_id"], title="Edited")

        assert service.list_snapshots(proj_id) == []

        snap = service.create_snapshot(proj_id, "researcher-1")
        assert len(service.list_snapshots(proj_id)) == 1
        assert snap.actor == "researcher-1"


# ---------------------------------------------------------------------------
# F16: no AI/LLM dependency or automatic AI interpretation in Task 10.7 scope
# ---------------------------------------------------------------------------


class TestF16NoAILLMDependency:
    AI_LLM_DEPENDENCY_TOKENS = (
        "openai",
        "anthropic",
        "langchain",
        "langgraph",
        "transformers",
        "huggingface",
        "ollama",
        "torch",
        "tensorflow",
        "gpt-4",
        "gpt-3",
        "claude",
        "gemini",
        "llama",
        "cohere",
        "llm",
        "ai_agent",
        "autogen",
    )

    SCOPE_FILES = (
        "app/domain/synthesis.py",
        "app/repositories/synthesis_snapshot_repository.py",
        "app/services/synthesis_snapshot_service.py",
        "app/api/routers/synthesis_snapshots.py",
        "app/api/dto/synthesis.py",
        "app/api/main.py",
        "app/adapters/synthesis_extraction_adapter.py",
        "migrations/0026_synthesis_snapshots.sql",
        "frontend/src/components/synthesis/SnapshotsWorkspace.tsx",
        "frontend/src/types/synthesis.ts",
        "frontend/src/services/api/synthesisApi.ts",
        "frontend/src/pages/EvidenceSynthesisPage.tsx",
        "frontend/tests/SnapshotsWorkspace.test.tsx",
    )

    @staticmethod
    def _dependency_lines(text: str) -> list[str]:
        dependencies = []
        for raw in text.splitlines():
            line = raw.strip()
            lowered = line.lower()
            if lowered.startswith("import ") or lowered.startswith("from "):
                dependencies.append(lowered)
            elif '"' in lowered or "'" in lowered:
                for token in TestF16NoAILLMDependency.AI_LLM_DEPENDENCY_TOKENS:
                    if token in lowered:
                        dependencies.append(lowered)
                        break
        return dependencies

    def test_no_ai_llm_dependency_tokens_in_task_10_7_scope(self):
        repo_root = Path(__file__).parents[3]
        offending = []
        for rel in self.SCOPE_FILES:
            path = repo_root / rel
            assert path.exists(), f"Scope file missing: {rel}"
            dependencies = self._dependency_lines(path.read_text(encoding="utf-8"))
            for line in dependencies:
                for token in self.AI_LLM_DEPENDENCY_TOKENS:
                    if token in line:
                        offending.append(f"{rel}: {line.strip()} (token '{token}')")
        assert offending == [], "AI/LLM dependency tokens found in Task 10.7 scope:\n" + "\n".join(offending)

    def test_snapshot_service_imports_have_no_ai_llm_references(self):
        service_file = Path(__file__).parents[3] / "app/services/synthesis_snapshot_service.py"
        module_imports = [
            line.strip()
            for line in service_file.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        joined = " ".join(module_imports).lower()
        for token in ("llm", "openai", "anthropic", "langchain", "agent"):
            assert token not in joined, f"AI/LLM token '{token}' referenced in snapshot service imports"


# ---------------------------------------------------------------------------
# Export contract: JSON = complete immutable content; CSV = relations matrix
# ---------------------------------------------------------------------------


class TestJsonExportContract:
    def test_json_export_contains_complete_content_supporting_full_reconstruction(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-json-contract"
        _seed_project(db_path, proj_id)
        _seed_baseline(db_path, proj_id)
        snap = service.create_snapshot(proj_id, "researcher-1")

        exported = service.export_snapshot(proj_id, snap.version, "json")
        assert exported["content"] == snap.content.model_dump(mode="json")
        assert exported["extraction_dataset_hash"] == snap.extraction_dataset_hash
        assert len(exported["content"]["relations"]) == 1
        assert len(exported["content"]["mechanism_pathways"]) == 1
        assert len(exported["content"]["context_assignments"]) == 1
        assert len(exported["content"]["research_gaps"]) == 1

        # The JSON payload supports full reconstruction of the immutable content.
        reconstructed = SynthesisSnapshotContent.model_validate(exported["content"])
        assert compute_content_hash(reconstructed) == snap.content_hash


class TestCsvExportContract:
    def test_csv_is_flattened_relations_matrix_not_full_content(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-csv-contract"
        _seed_project(db_path, proj_id)
        _seed_baseline(db_path, proj_id)
        snap = service.create_snapshot(proj_id, "researcher-1")

        exported = service.export_snapshot(proj_id, snap.version, "csv")
        assert exported["format"] == "csv"
        reader = csv.DictReader(io.StringIO(exported["content_csv"]))
        rows = list(reader)
        assert len(rows) == len(snap.content.relations)
        assert rows[0]["source_practice"] == "SMED Setup"
        assert rows[0]["direction"] == "positive"

        # CSV is a flattened analytical-relation dataset export: it carries the
        # relations matrix, not the mechanism/context/gap/QA objects.
        assert "mechanism_pathways" not in exported["content_csv"]
        assert "context_assignments" not in exported["content_csv"]
        assert "research_gaps" not in exported["content_csv"]
        assert "qa_profiles" not in exported["content_csv"]

    def test_csv_only_serializes_relations_when_present(self, service_env):
        db_path, repos, service = service_env
        proj_id = "proj-csv-empty"
        _seed_project(db_path, proj_id)
        snap = service.create_snapshot(proj_id, "researcher-1")

        exported = service.export_snapshot(proj_id, snap.version, "csv")
        reader = csv.DictReader(io.StringIO(exported["content_csv"]))
        rows = list(reader)
        assert rows == []
        assert list(reader.fieldnames or []) == [
            "publication_id",
            "group_item_id",
            "source_practice",
            "analytical_lean_category_id",
            "source_effect",
            "analytical_energy_category_id",
            "direction",
            "magnitude",
            "evidence_character",
            "approval_state",
        ]
