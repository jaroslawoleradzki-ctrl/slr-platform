"""Original adversarial regression suite for Phase 10 Research Gap Synthesis (Task 10.6).

Each test proves an invariant of the researcher-controlled research gap model:
the system NEVER auto-detects, auto-creates, auto-ranks, or auto-scores gaps, and
every evidence link is traceable to a real COMPLETE extraction revision inside the
same project. No AI/LLM dependency is used anywhere in the Task 10.6 scope.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

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
from app.domain.quality_assessment import (
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.domain.synthesis import (
    AnalyticalMechanismCategory,
    ResearchGap,
    ResearchGapEvidenceCandidate,
    ResearchGapLinkType,
)
from app.repositories.extraction_repository import default_extraction_repository
from app.repositories.project_publication_repository import (
    default_project_publication_repository,
)
from app.repositories.project_repository import (
    default_project_repository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentCatalogRepository,
    default_quality_assessment_repository,
)
from app.repositories.synthesis_gap_repository import (
    default_synthesis_gap_repository,
)
from app.repositories.synthesis_mechanism_repository import (
    default_synthesis_mechanism_repository,
)
from app.services.synthesis_context_service import (
    default_synthesis_context_service,
)
from app.services.synthesis_gap_service import (
    ResearchGapEvidenceError,
    default_synthesis_gap_service,
)
from app.services.synthesis_matrix_service import SynthesisMatrixService
from app.services.synthesis_mechanism_service import (
    default_synthesis_mechanism_service,
)


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
    _apply_migrations_up_to(db_file, "0025_research_gap_synthesis.sql")

    from app.domain.extraction import ExtractionTemplate, ExtractionTemplateVersion
    from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository

    template_repo = SqliteExtractionTemplateRepository(db_file)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )


@pytest.fixture
def project_repo():
    repo = default_project_repository()
    repo.create(
        Project(
            project_id="test_project",
            title="Test Project",
            description="Test project for research gap synthesis",
            protocol_version="1.0.0",
        )
    )
    return repo


@pytest.fixture
def service(project_repo):
    return default_synthesis_gap_service()


def _append_revision(
    project_id, publication_id, revision_id, revision_index, group_items, completeness=ExtractionCompletenessStatus.COMPLETE
):
    extraction_repo = default_extraction_repository()
    records = extraction_repo.list_records(project_id)
    record = next(r for r in records if r.publication_id == publication_id)
    extraction_repo.append_revision(
        ExtractionRevision(
            revision_id=revision_id,
            record_id=record.record_id,
            project_id=project_id,
            publication_id=publication_id,
            revision_index=revision_index,
            reviewer_id="rev_1",
            completeness_status=completeness,
            group_items=group_items,
            created_at=datetime.now(timezone.utc),
        )
    )


def _values(lean_practice="Value Stream Mapping", energy_effect="reduction", *, impact_mechanism="Thermal bottleneck removal.", moderating_conditions="Batch manufacturing."):
    values = [
        ExtractedValueState(
            field_key="lean_practice", status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED, text_value=lean_practice,
        ),
        ExtractedValueState(
            field_key="energy_effect_indicator", status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED, text_value=energy_effect,
        ),
        ExtractedValueState(
            field_key="direction", status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED, text_value="improvement",
        ),
    ]
    if impact_mechanism is not None:
        values.append(
            ExtractedValueState(
                field_key="impact_mechanism", status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED, text_value=impact_mechanism,
            )
        )
    if moderating_conditions is not None:
        values.append(
            ExtractedValueState(
                field_key="moderating_conditions", status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED, text_value=moderating_conditions,
            )
        )
    return values


def _add_publication(project_id, pub_id, title="Manufacturing Energy Study"):
    default_project_publication_repository().add_publications(
        project_id, [Publication(record_id=pub_id, title=title, publication_year=2024)]
    )


def _standard_group_items(group_item_id):
    return [
        ExtractedGroupItemState(
            group_item_id=group_item_id,
            group_key="lean_energy_relationships",
            item_index=1,
            values=_values(),
        )
    ]


def _seed_single_publication(project_id="test_project", *, impact_mechanism="Thermal bottleneck removal.", moderating_conditions="Batch manufacturing."):
    """Seeds one publication + COMPLETE revision + materialized evidence artifacts."""
    pub_id = uuid4()
    group_item_id = uuid4()
    rev1_id = uuid4()

    _add_publication(project_id, pub_id)
    extraction_repo = default_extraction_repository()
    extraction_repo.create_record(
        ExtractionRecord(
            project_id=project_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
        )
    )
    _append_revision(
        project_id,
        pub_id,
        rev1_id,
        1,
        [
            ExtractedGroupItemState(
                group_item_id=group_item_id,
                group_key="lean_energy_relationships",
                item_index=1,
                values=_values(impact_mechanism=impact_mechanism, moderating_conditions=moderating_conditions),
            )
        ],
    )

    matrix_service = SynthesisMatrixService(
        matrix_repo=default_synthesis_gap_service()._matrix_repo,
        extraction_repo=extraction_repo,
        project_repo=default_project_repository(),
        publication_repo=default_project_publication_repository(),
    )
    relations = matrix_service.synchronize_analytical_relations(project_id)
    relation_id = relations[0].relation_id if relations else None

    default_synthesis_mechanism_service().synchronize_mechanism_pathways(project_id)
    default_synthesis_context_service().synchronize_context_from_extraction(project_id)

    pathway = default_synthesis_gap_service()._mechanism_repo.list_pathways(project_id)[0]
    context_link = default_synthesis_gap_service()._context_repo.list_links(project_id)[0]

    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev1_id": rev1_id,
        "relation_id": relation_id,
        "pathway_id": pathway.pathway_id,
        "context_link_id": UUID(context_link["link_id"]),
    }


def _seed_qa_no(project_id, publication_id):
    catalog_repo = SqliteQualityAssessmentCatalogRepository()
    try:
        catalog_repo.create_tool(QualityAssessmentTool(tool_id="casp_tool", name="CASP Tool"))
    except Exception:
        pass
    tid = uuid4()
    crit = uuid4()
    ass_id = uuid4()
    catalog_repo.create_template_version(
        QualityAssessmentTemplate(
            template_id=tid,
            tool_id="casp_tool",
            template_key="lean_qa",
            name="Lean QA Template",
            version=1,
            is_active=True,
            criteria=[
                QualityAssessmentTemplateCriterion(
                    criterion_id=crit, template_id=tid, display_order=1,
                    question="Is the study design clearly described?",
                )
            ],
        )
    )
    qa_repo = default_quality_assessment_repository()
    qa_repo.save_assessment(
        QualityAssessment(
            assessment_id=ass_id,
            project_id=project_id,
            publication_id=publication_id,
            template_id=tid,
            reviewer_id="lead_reviewer",
            responses=[
                QualityAssessmentResponse(
                    assessment_id=ass_id,
                    criterion_id=crit,
                    question_snapshot="Is the study design clearly described?",
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="Methodology section is missing.",
                )
            ],
        )
    )


def _make_gap(service, project_id="test_project"):
    return service.create_research_gap(
        project_id=project_id, gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
    )


class TestOriginalE1NoAutoThematicGap:
    def test_single_publication_never_auto_creates_thematic_gap(self, service):
        seeded = _seed_single_publication()
        assert seeded["relation_id"] is not None
        gaps = service.list_research_gaps("test_project")
        assert gaps == []
        stats = service.get_research_gap_workspace_data("test_project").stats
        assert stats.total_gaps == 0


class TestOriginalE2NoAutoMechanismGap:
    def test_effect_without_mechanism_never_auto_creates_mechanism_gap(self, service):
        _seed_single_publication(impact_mechanism=None)
        pathway = service._mechanism_repo.list_pathways("test_project")[0]
        assert pathway.source_mechanism_text in (None, "")
        assert service.list_research_gaps("test_project") == []


class TestOriginalE3NoAutoContextualGap:
    def test_missing_context_never_auto_creates_contextual_gap(self, service):
        _seed_single_publication(moderating_conditions=None)
        context_links = service._context_repo.list_links("test_project")
        assert context_links
        assert service.list_research_gaps("test_project") == []


class TestOriginalE4NoAutoInconsistentGap:
    def test_conflicting_directions_never_auto_create_inconsistent_evidence_gap(self, service):
        project_id = "test_project"
        pub_a = uuid4()
        pub_b = uuid4()
        _add_publication(project_id, pub_a, title="Study A")
        _add_publication(project_id, pub_b, title="Study B")

        extraction_repo = default_extraction_repository()
        extraction_repo.create_record(
            ExtractionRecord(project_id=project_id, publication_id=pub_a, template_id="lean_energy", template_version="1.0.0")
        )
        extraction_repo.create_record(
            ExtractionRecord(project_id=project_id, publication_id=pub_b, template_id="lean_energy", template_version="1.0.0")
        )

        values_a = _values()
        values_a[2] = ExtractedValueState(
            field_key="direction", status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED, text_value="improvement",
        )
        values_b = _values()
        values_b[2] = ExtractedValueState(
            field_key="direction", status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED, text_value="degradation",
        )

        _append_revision(
            project_id, pub_a, UUID("11111111-1111-1111-1111-111111111111"), 1,
            [ExtractedGroupItemState(group_item_id=uuid4(), group_key="lean_energy_relationships", item_index=1, values=values_a)],
        )
        _append_revision(
            project_id, pub_b, UUID("22222222-2222-2222-2222-222222222222"), 1,
            [ExtractedGroupItemState(group_item_id=uuid4(), group_key="lean_energy_relationships", item_index=1, values=values_b)],
        )

        matrix_service = SynthesisMatrixService(
            matrix_repo=default_synthesis_gap_service()._matrix_repo,
            extraction_repo=extraction_repo,
            project_repo=default_project_repository(),
            publication_repo=default_project_publication_repository(),
        )
        relations = matrix_service.synchronize_analytical_relations(project_id)
        directions = {r.direction for r in relations}
        assert len(relations) == 2
        assert len(directions) >= 2
        assert service.list_research_gaps(project_id) == []


class TestOriginalE5NoAutoMethodologicalGap:
    def test_qa_no_responses_never_auto_create_methodological_gap(self, service):
        seeded = _seed_single_publication()
        _seed_qa_no("test_project", seeded["pub_id"])
        assert service.list_research_gaps("test_project") == []


class TestOriginalE6CrossProjectAnalyticalLinkRejected:
    def test_analytical_relation_from_another_project_is_rejected(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="", protocol_version="1.0.0")
        )
        _seed_single_publication()
        _seed_single_publication("other_project")

        gap = _make_gap(service)
        foreign_relation = service._matrix_repo.list_analytical_relations("other_project")[0]
        with pytest.raises(ResearchGapEvidenceError):
            service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, foreign_relation.relation_id)
        assert service.list_links_for_gap("test_project", str(gap.gap_id)) == []


class TestOriginalE7CrossProjectMechanismContextLinkRejected:
    def test_mechanism_pathway_from_another_project_is_rejected(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="", protocol_version="1.0.0")
        )
        _seed_single_publication()
        _seed_single_publication("other_project")

        gap = _make_gap(service)
        foreign_pathway = service._mechanism_repo.list_pathways("other_project")[0]
        with pytest.raises(ResearchGapEvidenceError):
            service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.MECHANISM_PATHWAY, foreign_pathway.pathway_id)
        assert service.list_links_for_gap("test_project", str(gap.gap_id)) == []

    def test_context_factor_link_from_another_project_is_rejected(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="", protocol_version="1.0.0")
        )
        _seed_single_publication()
        _seed_single_publication("other_project")

        gap = _make_gap(service)
        foreign_ctx = service._context_repo.list_links("other_project")[0]
        with pytest.raises(ResearchGapEvidenceError):
            service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.CONTEXT_FACTOR_LINK, UUID(foreign_ctx["link_id"]))
        assert service.list_links_for_gap("test_project", str(gap.gap_id)) == []


class TestOriginalE8DraftKeepsCompleteEvidence:
    def test_draft_revision_keeps_gap_linked_to_complete_evidence(self, service):
        seeded = _seed_single_publication()
        gap = _make_gap(service)
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert link.latest_revision_id == seeded["rev1_id"]

        group_items = [
            ExtractedGroupItemState(
                group_item_id=seeded["group_item_id"],
                group_key="lean_energy_relationships",
                item_index=1,
                values=_values(),
            )
        ]
        _append_revision(
            "test_project", seeded["pub_id"], UUID("22222222-2222-2222-2222-222222222222"), 2,
            group_items, completeness=ExtractionCompletenessStatus.IN_PROGRESS,
        )

        relink = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert relink.link_id == link.link_id
        assert relink.latest_revision_id == seeded["rev1_id"]
        candidates = service.list_linkable_evidence_candidates("test_project")
        candidate = next(c for c in candidates if c.target_id == seeded["relation_id"])
        assert candidate.traceable is True


class TestOriginalE9LaterCompleteKeepsCoherentTraceability:
    def test_later_complete_revision_advances_link_with_coherent_traceability(self, service):
        seeded = _seed_single_publication()
        gap = _make_gap(service)
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert link.latest_revision_id == seeded["rev1_id"]

        rev2 = UUID("22222222-2222-2222-2222-222222222222")
        rev3 = UUID("33333333-3333-3333-3333-333333333333")
        _append_revision("test_project", seeded["pub_id"], rev2, 2, _standard_group_items(seeded["group_item_id"]), completeness=ExtractionCompletenessStatus.IN_PROGRESS)
        _append_revision("test_project", seeded["pub_id"], rev3, 3, _standard_group_items(seeded["group_item_id"]))

        relink = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert relink.link_id == link.link_id
        assert relink.latest_revision_id == rev3
        assert relink.group_item_id == seeded["group_item_id"]

        history = default_extraction_repository().list_revision_history("test_project", seeded["pub_id"])
        complete_with_item = [
            r.revision_id
            for r in history
            if r.completeness_status == ExtractionCompletenessStatus.COMPLETE
            and any(gi.group_item_id == seeded["group_item_id"] for gi in r.group_items)
        ]
        assert relink.latest_revision_id in complete_with_item

        candidates = service.list_linkable_evidence_candidates("test_project")
        candidate = next(c for c in candidates if c.target_id == seeded["relation_id"])
        assert candidate.traceable is True


class TestOriginalE10DisappearedEvidenceNoFabrication:
    def test_disappeared_source_evidence_is_not_fabricated(self, service):
        seeded = _seed_single_publication()
        gap = _make_gap(service)
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert link.latest_revision_id == seeded["rev1_id"]

        default_extraction_repository().delete_for_project("test_project")

        with pytest.raises(ResearchGapEvidenceError):
            service.link_evidence(
                "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
            )

        repo = default_synthesis_gap_repository()
        stored = repo.list_links_for_gap("test_project", str(gap.gap_id))
        assert len(stored) == 1
        assert UUID(stored[0]["latest_revision_id"]) == seeded["rev1_id"]

        candidates = service.list_linkable_evidence_candidates("test_project")
        candidate = next(c for c in candidates if c.target_id == seeded["relation_id"])
        assert candidate.traceable is False


class TestOriginalE11EditingRationaleKeepsEvidenceUnchanged:
    def test_editing_gap_rationale_leaves_source_evidence_unchanged(self, service):
        seeded = _seed_single_publication()
        gap = _make_gap(service)
        service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"])
        service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.MECHANISM_PATHWAY, seeded["pathway_id"])

        before = service.list_links_for_gap("test_project", str(gap.gap_id))
        before_relation = service._matrix_repo.get_analytical_relation("test_project", seeded["relation_id"])

        service.update_research_gap("test_project", str(gap.gap_id), title="Renamed", rationale="Edited justification.")

        after = service.list_links_for_gap("test_project", str(gap.gap_id))
        assert [(lk.link_id, lk.latest_revision_id, lk.group_item_id) for lk in after] == [
            (lk.link_id, lk.latest_revision_id, lk.group_item_id) for lk in before
        ]
        after_relation = service._matrix_repo.get_analytical_relation("test_project", seeded["relation_id"])
        assert after_relation.group_item_id == before_relation.group_item_id
        assert after_relation.publication_id == before_relation.publication_id
        assert after_relation.latest_revision_id == before_relation.latest_revision_id


class TestOriginalE12DeletingGapKeepsEvidenceIntact:
    def test_deleting_gap_leaves_underlying_evidence_intact(self, service):
        seeded = _seed_single_publication()
        gap = _make_gap(service)
        service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"])
        service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.MECHANISM_PATHWAY, seeded["pathway_id"])
        service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.CONTEXT_FACTOR_LINK, seeded["context_link_id"])

        service.delete_research_gap("test_project", str(gap.gap_id))

        assert service._matrix_repo.get_analytical_relation("test_project", seeded["relation_id"]) is not None
        assert service._mechanism_repo.get_pathway("test_project", seeded["pathway_id"]) is not None
        assert service._context_repo.get_link(str(seeded["context_link_id"])) is not None
        assert default_extraction_repository().list_records("test_project")
        assert service.list_research_gaps("test_project") == []


class TestOriginalE13CategoryDeletionNoCorruption:
    def test_category_deletion_does_not_corrupt_gap_or_evidence(self, service):
        seeded = _seed_single_publication()
        mechanism_repo = default_synthesis_mechanism_repository()
        cat_id = uuid4()
        mechanism_repo.create_category(
            AnalyticalMechanismCategory(category_id=str(cat_id), name="Lean Waste Reduction", project_id="test_project")
        )
        default_synthesis_mechanism_service().assign_mechanism_category("test_project", seeded["pathway_id"], str(cat_id))

        gap = _make_gap(service)
        link = service.link_evidence("test_project", str(gap.gap_id), ResearchGapLinkType.MECHANISM_PATHWAY, seeded["pathway_id"])
        assert link.latest_revision_id == seeded["rev1_id"]

        assert mechanism_repo.delete_category("test_project", str(cat_id)) is True
        default_synthesis_mechanism_service().synchronize_mechanism_pathways("test_project")

        pathway = service._mechanism_repo.get_pathway("test_project", seeded["pathway_id"])
        assert pathway is not None
        assert pathway.analytical_mechanism_category_id is None

        stored = service.list_links_for_gap("test_project", str(gap.gap_id))
        assert len(stored) == 1
        assert stored[0].target_id == seeded["pathway_id"]
        assert stored[0].latest_revision_id == seeded["rev1_id"]
        assert default_extraction_repository().list_records("test_project")


class TestOriginalE14PublicationCountNeverAutoCreates:
    def test_zero_one_and_two_publications_never_auto_create_gaps(self, service):
        assert service.list_research_gaps("test_project") == []

        seeded_a = _seed_single_publication()
        assert seeded_a["relation_id"] is not None
        assert service.list_research_gaps("test_project") == []

        pub_b = uuid4()
        _add_publication("test_project", pub_b, title="Study B")
        extraction_repo = default_extraction_repository()
        extraction_repo.create_record(
            ExtractionRecord(project_id="test_project", publication_id=pub_b, template_id="lean_energy", template_version="1.0.0")
        )
        _append_revision(
            "test_project", pub_b, UUID("22222222-2222-2222-2222-222222222222"), 1,
            [
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=_values(lean_practice="5S", energy_effect="reduction"),
                )
            ],
        )
        matrix_service = SynthesisMatrixService(
            matrix_repo=default_synthesis_gap_service()._matrix_repo,
            extraction_repo=extraction_repo,
            project_repo=default_project_repository(),
            publication_repo=default_project_publication_repository(),
        )
        matrix_service.synchronize_analytical_relations("test_project")
        assert service.list_research_gaps("test_project") == []


class TestOriginalE15ScoreConfidenceTierUnsupported:
    def test_gap_rejects_gap_score_confidence_and_quality_tier_fields(self):
        with pytest.raises(ValidationError):
            ResearchGap(
                gap_id=uuid4(), project_id="test_project", gap_type="thematic", title="Gap",
                rationale="Rationale.", researcher_id="r", gap_score=0.9,
            )
        with pytest.raises(ValidationError):
            ResearchGap(
                gap_id=uuid4(), project_id="test_project", gap_type="thematic", title="Gap",
                rationale="Rationale.", researcher_id="r", quality_tier="HIGH",
            )
        with pytest.raises(ValidationError):
            ResearchGap(
                gap_id=uuid4(), project_id="test_project", gap_type="thematic", title="Gap",
                rationale="Rationale.", researcher_id="r", confidence=0.9,
            )

    def test_candidate_rejects_gap_score_confidence_and_quality_tier_fields(self):
        with pytest.raises(ValidationError):
            ResearchGapEvidenceCandidate(
                link_type=ResearchGapLinkType.ANALYTICAL_RELATION, target_id=uuid4(),
                group_item_id=uuid4(), publication_id=uuid4(), latest_revision_id=uuid4(),
                traceable=True, label="candidate", gap_score=0.9,
            )
        with pytest.raises(ValidationError):
            ResearchGapEvidenceCandidate(
                link_type=ResearchGapLinkType.ANALYTICAL_RELATION, target_id=uuid4(),
                group_item_id=uuid4(), publication_id=uuid4(), latest_revision_id=uuid4(),
                traceable=True, label="candidate", quality_tier="HIGH",
            )
        with pytest.raises(ValidationError):
            ResearchGapEvidenceCandidate(
                link_type=ResearchGapLinkType.ANALYTICAL_RELATION, target_id=uuid4(),
                group_item_id=uuid4(), publication_id=uuid4(), latest_revision_id=uuid4(),
                traceable=True, label="candidate", confidence=0.9,
            )


class TestOriginalE16NoAILLMDependencies:
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
        "app/repositories/synthesis_gap_repository.py",
        "app/services/synthesis_gap_service.py",
        "app/api/routers/synthesis_gaps.py",
        "app/api/dto/synthesis.py",
        "app/adapters/synthesis_extraction_adapter.py",
        "app/services/synthesis_matrix_service.py",
        "app/services/synthesis_mechanism_service.py",
        "app/services/synthesis_context_service.py",
        "app/repositories/synthesis_matrix_repository.py",
        "app/repositories/synthesis_mechanism_repository.py",
        "app/repositories/synthesis_context_repository.py",
        "migrations/0025_research_gap_synthesis.sql",
        "frontend/src/components/synthesis/ResearchGapsWorkspace.tsx",
        "frontend/src/types/synthesis.ts",
        "frontend/src/services/api/synthesisApi.ts",
        "frontend/src/pages/EvidenceSynthesisPage.tsx",
        "frontend/tests/ResearchGapsWorkspace.test.tsx",
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
                for token in TestOriginalE16NoAILLMDependencies.AI_LLM_DEPENDENCY_TOKENS:
                    if token in lowered:
                        dependencies.append(lowered)
                        break
        return dependencies

    def test_no_ai_llm_dependencies_anywhere_in_phase_10_6_scope(self):
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
        assert offending == [], "AI/LLM dependency tokens found in Task 10.6 scope:\n" + "\n".join(offending)

    def test_no_llm_agent_or_autogenerated_gap_code_in_scope(self, service):
        """Deeper check: no module-level name referring to an LLM/agent within the gap service module."""
        service_file = Path(__file__).parents[3] / "app/services/synthesis_gap_service.py"
        module_imports = [
            line.strip()
            for line in service_file.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        joined = " ".join(module_imports).lower()
        for token in ("llm", "openai", "anthropic", "langchain", "agent"):
            assert token not in joined
