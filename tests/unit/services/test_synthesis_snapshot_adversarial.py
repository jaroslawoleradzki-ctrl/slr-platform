"""Original adversarial regression suite for Synthesis Snapshots (Task 10.7).

Each test proves an invariant of the immutable snapshot engine: snapshots are
researcher-triggered and never auto-created, content is stored (not live), hashes
are ordering-insensitive and deterministic, versions are monotonic per project,
exports are lossless, QA is criterion-level without arbitrary scoring, and no
AI/LLM dependency exists anywhere in the Task 10.7 scope.
"""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
    RelationDirection,
    ResearchGapLinkType,
    SynthesisSnapshot,
    SynthesisSnapshotContent,
    build_extraction_dataset_items,
    compute_content_hash,
    compute_extraction_dataset_hash,
)
from app.repositories.extraction_repository import default_extraction_repository
from app.repositories.synthesis_matrix_repository import SqliteSynthesisMatrixRepository
from app.repositories.synthesis_snapshot_repository import SqliteSynthesisSnapshotRepository
from app.services.synthesis_context_service import default_synthesis_context_service
from app.services.synthesis_gap_service import default_synthesis_gap_service
from app.services.synthesis_mechanism_service import default_synthesis_mechanism_service
from app.services.synthesis_snapshot_service import (
    SnapshotExportError as SnapshotServiceExportError,
)
from app.services.synthesis_snapshot_service import SynthesisSnapshotService


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
    db_file = tmp_path / "test_snapshot_adversarial.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_file))
    _apply_migrations_up_to(db_file, "0026_synthesis_snapshots.sql")
    return db_file


@pytest.fixture
def project_repo():
    from app.repositories.project_repository import default_project_repository

    repo = default_project_repository()
    repo.create(
        Project(
            project_id="test_project",
            title="Snapshot Adversarial Project",
            description="Task 10.7 adversarial test project.",
        )
    )
    return repo


@pytest.fixture
def service(project_repo):
    return SynthesisSnapshotService()


@pytest.fixture
def snapshot_repo():
    return SqliteSynthesisSnapshotRepository()


def _add_publication(project_id, pub_id, title="Snapshot Adversarial Study"):
    from app.repositories.project_publication_repository import default_project_publication_repository

    default_project_publication_repository().add_publications(
        project_id, [Publication(record_id=pub_id, title=title, publication_year=2024)]
    )


def _register_template():
    from app.domain.extraction import ExtractionTemplate, ExtractionTemplateVersion
    from app.repositories.extraction_template_repository import default_extraction_template_repository

    template_repo = default_extraction_template_repository()
    try:
        template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    except Exception:
        pass
    try:
        template_repo.register_version(
            ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
        )
    except Exception:
        pass


def _seed_complete_evidence(project_id="test_project"):
    """Seeds one publication + COMPLETE revision + materialized synthesis artifacts."""
    _register_template()
    pub_id = uuid4()
    group_item_id = uuid4()
    _add_publication(project_id, pub_id)
    ext_repo = default_extraction_repository()
    rec = ext_repo.create_record(
        ExtractionRecord(
            project_id=project_id,
            publication_id=pub_id,
            template_id="lean_energy",
            template_version="1.0.0",
        )
    )
    rev = ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=project_id,
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
    matrix_repo = SqliteSynthesisMatrixRepository()
    relation_id = uuid4()
    matrix_repo.save_analytical_relation(
        AnalyticalRelation(
            relation_id=relation_id,
            project_id=project_id,
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
    default_synthesis_mechanism_service().synchronize_mechanism_pathways(project_id)
    default_synthesis_context_service().synchronize_context_from_extraction(project_id)
    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "relation_id": relation_id,
        "revision_id": rev.revision_id,
    }


def _make_gap(project_id="test_project", title="Under-studied practice"):
    return default_synthesis_gap_service().create_research_gap(
        project_id=project_id,
        gap_type="thematic",
        title=title,
        rationale="Only one source covers this practice.",
        researcher_id="researcher-1",
    )


# ---------------------------------------------------------------------------
# F1-F2: Actor validation
# ---------------------------------------------------------------------------


class TestF1ActorValidation:
    def test_whitespace_only_actor_is_rejected(self, service, project_repo):
        with pytest.raises(ValueError):
            service.create_snapshot("test_project", "   ")

    def test_empty_actor_is_rejected(self, service, project_repo):
        with pytest.raises(ValueError):
            service.create_snapshot("test_project", "")


class TestF2ActorTrimming:
    def test_actor_is_trimmed_of_surrounding_whitespace(self, service, project_repo):
        snap = service.create_snapshot("test_project", "  reviewer_1  ")
        assert snap.actor == "reviewer_1"

    def test_internal_spaces_are_preserved(self, service, project_repo):
        snap = service.create_snapshot("test_project", "lead reviewer")
        assert snap.actor == "lead reviewer"


# ---------------------------------------------------------------------------
# F3-F4: Ordering-insensitive hashing
# ---------------------------------------------------------------------------


class TestF3ContentHashOrderingInsensitive:
    def test_content_hash_stable_under_relation_list_reversal(self):
        rel = AnalyticalRelation(
            relation_id=uuid4(),
            project_id="p",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=uuid4(),
            item_index=1,
            source_practice="SMED Setup",
            source_effect="Compressed Air",
        )
        rel2 = rel.model_copy(
            update={
                "relation_id": uuid4(),
                "group_item_id": uuid4(),
                "source_practice": "Value Stream Mapping",
                "source_effect": "Electrical Consumption",
            }
        )
        base = SynthesisSnapshotContent(
            project_id="p",
            relations=[rel, rel2],
            mechanism_pathways=[],
            context_assignments=[],
            research_gaps=[],
            research_gap_links=[],
            term_mappings=[],
            lean_categories=[],
            energy_categories=[],
            mechanism_categories=[],
            context_categories=[],
            qa_profiles=[],
        )
        reversed_content = base.model_copy(update={"relations": [rel2, rel]})
        assert compute_content_hash(base) == compute_content_hash(reversed_content)


class TestF4DatasetHashOrderingInsensitive:
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
        items = build_extraction_dataset_items([rev])
        h1 = compute_extraction_dataset_hash(items)
        # Reordering the group items yields the same canonical dataset hash.
        rev2 = rev.model_copy(update={"group_items": [gi_b, gi_a]})
        items2 = build_extraction_dataset_items([rev2])
        h2 = compute_extraction_dataset_hash(items2)
        assert h1 == h2


# ---------------------------------------------------------------------------
# F5-F6: No auto-creation; explicit researcher trigger only
# ---------------------------------------------------------------------------


class TestF5NoAutoSnapshot:
    def test_seeding_evidence_creates_no_snapshots(self, service, project_repo):
        _seed_complete_evidence("test_project")
        assert service.list_snapshots("test_project") == []

    def test_creating_gap_creates_no_snapshots(self, service, project_repo):
        _make_gap("test_project")
        assert service.list_snapshots("test_project") == []


class TestF6ExplicitTriggerOnly:
    def test_snapshot_only_appears_after_explicit_post(self, service, project_repo):
        _seed_complete_evidence("test_project")
        _make_gap("test_project")
        assert service.list_snapshots("test_project") == []
        snap = service.create_snapshot("test_project", "researcher-1")
        assert len(service.list_snapshots("test_project")) == 1
        assert snap.content.project_id == "test_project"


# ---------------------------------------------------------------------------
# F7-F8: Stored (frozen) content at the DB level
# ---------------------------------------------------------------------------


class TestF7DBCollisionFreeImmutability:
    def test_content_json_bytes_unchanged_after_synthesis_mutation(
        self, service, project_repo, snapshot_repo, isolate_test_database
    ):
        _seed_complete_evidence("test_project")
        snap = service.create_snapshot("test_project", "researcher-1")

        conn = sqlite3.connect(isolate_test_database)
        row_before = conn.execute(
            "SELECT content_json FROM synthesis_snapshots WHERE snapshot_id = ?",
            (str(snap.snapshot_id),),
        ).fetchone()
        conn.close()

        # Mutate the underlying synthesis state after the snapshot was created.
        matrix_repo = SqliteSynthesisMatrixRepository()
        rel = matrix_repo.list_analytical_relations("test_project")[0]
        from app.domain.synthesis import ConvertedValue

        matrix_repo.update_converted_value(
            "test_project",
            rel.relation_id,
            ConvertedValue(transformed_value=42.0, transformed_unit="kwh", conversion_rule="changed"),
        )
        gap = _make_gap("test_project")
        default_synthesis_gap_service().link_evidence(
            project_id="test_project",
            gap_id=str(gap.gap_id),
            link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
            target_id=rel.relation_id,
        )

        conn = sqlite3.connect(isolate_test_database)
        row_after = conn.execute(
            "SELECT content_json FROM synthesis_snapshots WHERE snapshot_id = ?",
            (str(snap.snapshot_id),),
        ).fetchone()
        conn.close()

        assert row_before[0] == row_after[0]

    def test_version_conflict_raises_integrity_error(self, service, project_repo, snapshot_repo):
        snap = service.create_snapshot("test_project", "researcher-1")
        duplicate = snap.model_copy(update={"snapshot_id": uuid4()})
        with pytest.raises(sqlite3.IntegrityError):
            snapshot_repo.save_snapshot(duplicate)


class TestF8CrossProjectExportIsolation:
    def test_export_of_one_project_never_contains_other_project_data(self, service, project_repo):
        from app.repositories.project_repository import default_project_repository

        default_project_repository().create(Project(project_id="project_b", title="Project B", description=""))
        _seed_complete_evidence("test_project")
        _seed_complete_evidence("project_b")

        snap_a = service.create_snapshot("test_project", "researcher-1")
        exported = service.export_snapshot("test_project", snap_a.version, "json")

        content = exported["content"]
        assert len(content["relations"]) == 1
        for rel in content["relations"]:
            assert rel["project_id"] == "test_project"


# ---------------------------------------------------------------------------
# F9-F10: Lossless exports
# ---------------------------------------------------------------------------


class TestF9JsonExportLossless:
    def test_export_content_deep_equals_stored_content(self, service, project_repo):
        _seed_complete_evidence("test_project")
        snap = service.create_snapshot("test_project", "researcher-1")
        exported = service.export_snapshot("test_project", snap.version, "json")

        assert exported["content"] == snap.content.model_dump(mode="json")
        assert exported["version"] == snap.version
        assert exported["actor"] == snap.actor


class TestF10CsvExportFidelity:
    def test_csv_rows_match_relations_and_header_present(self, service, project_repo):
        _seed_complete_evidence("test_project")
        snap = service.create_snapshot("test_project", "researcher-1")
        exported = service.export_snapshot("test_project", snap.version, "csv")

        import csv as csv_module
        import io

        reader = csv_module.DictReader(io.StringIO(exported["content_csv"]))
        rows = list(reader)
        assert len(rows) == len(snap.content.relations)
        assert "source_practice" in rows[0]
        assert "direction" in rows[0]
        assert rows[0]["source_practice"] == "SMED Setup"


# ---------------------------------------------------------------------------
# F11-F12: Export format handling
# ---------------------------------------------------------------------------


class TestF11ExportFormatCaseInsensitive:
    def test_uppercase_json_export_succeeds(self, service, project_repo):
        snap = service.create_snapshot("test_project", "researcher-1")
        exported = service.export_snapshot("test_project", snap.version, "JSON")
        assert exported["format"] == "json"

    def test_mixed_case_csv_export_succeeds(self, service, project_repo):
        snap = service.create_snapshot("test_project", "researcher-1")
        exported = service.export_snapshot("test_project", snap.version, "Csv")
        assert exported["format"] == "csv"


class TestF12UnsupportedExportFormat:
    def test_unknown_format_raises_snapshot_export_error(self, service, project_repo):
        snap = service.create_snapshot("test_project", "researcher-1")
        with pytest.raises(SnapshotServiceExportError):
            service.export_snapshot("test_project", snap.version, "xml")


# ---------------------------------------------------------------------------
# F13-F14: Empty project determinism
# ---------------------------------------------------------------------------


class TestF13EmptyProjectSnapshot:
    def test_empty_project_snapshot_is_valid_and_empty(self, service, project_repo):
        snap = service.create_snapshot("test_project", "researcher-1")
        assert len(snap.extraction_dataset_hash) == 64
        assert len(snap.classification_version) == 64
        assert len(snap.content_hash) == 64
        assert snap.content.relations == []
        assert snap.content.research_gaps == []
        assert snap.content.research_gap_links == []
        assert snap.content.qa_profiles == []


class TestF14DeterministicEmptyProject:
    def test_repeated_empty_project_snapshots_have_identical_hashes(self, service, project_repo):
        s1 = service.create_snapshot("test_project", "researcher-1")
        s2 = service.create_snapshot("test_project", "researcher-1")
        assert s1.extraction_dataset_hash == s2.extraction_dataset_hash
        assert s1.classification_version == s2.classification_version
        assert s1.content_hash == s2.content_hash
        assert s1.version != s2.version


# ---------------------------------------------------------------------------
# F15: No score/confidence/quality tier fields in 10.7 scope
# ---------------------------------------------------------------------------


class TestF15NoScoreConfidenceQualityTier:
    def test_snapshot_rejects_score_confidence_and_tier_fields(self):
        with pytest.raises(ValidationError):
            SynthesisSnapshot(
                snapshot_id=uuid4(),
                project_id="test_project",
                version=1,
                actor="r",
                extraction_dataset_hash="a" * 64,
                classification_version="b" * 64,
                content_hash="c" * 64,
                content=SynthesisSnapshotContent(project_id="test_project"),
                snapshot_score=0.9,
            )
        with pytest.raises(ValidationError):
            SynthesisSnapshotContent(
                project_id="test_project",
                confidence=0.9,
            )


# ---------------------------------------------------------------------------
# F16: No AI/LLM dependencies anywhere in the Task 10.7 scope
# ---------------------------------------------------------------------------


class TestF16NoAILLMDependencies:
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
        """Returns lines that import or reference a package dependency (not docstrings)."""
        dependencies = []
        for raw in text.splitlines():
            line = raw.strip()
            lowered = line.lower()
            if lowered.startswith("import ") or lowered.startswith("from "):
                dependencies.append(lowered)
            elif '"' in lowered or "'" in lowered:
                for token in TestF16NoAILLMDependencies.AI_LLM_DEPENDENCY_TOKENS:
                    if token in lowered:
                        dependencies.append(lowered)
                        break
        return dependencies

    def test_no_ai_llm_dependencies_anywhere_in_task_10_7_scope(self):
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

    def test_no_llm_agent_or_autogenerated_code_in_snapshot_service(self):
        service_file = Path(__file__).parents[3] / "app/services/synthesis_snapshot_service.py"
        module_imports = [
            line.strip()
            for line in service_file.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        joined = " ".join(module_imports).lower()
        for token in ("llm", "openai", "anthropic", "langchain", "agent"):
            assert token not in joined, f"AI/LLM token '{token}' referenced in snapshot service imports"
