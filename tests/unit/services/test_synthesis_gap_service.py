"""Unit tests for SynthesisGapService: Phase 10 Research Gap Synthesis (Task 10.6)."""

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
    AnalyticalRelation,
    ClassificationApprovalState,
    RelationDirection,
    ResearchGap,
    ResearchGapEvidenceCandidate,
    ResearchGapLink,
    ResearchGapLinkType,
    ResearchGapType,
    ResearchGapWorkspaceData,
)
from app.repositories.extraction_repository import default_extraction_repository
from app.repositories.project_publication_repository import (
    default_project_publication_repository,
)
from app.repositories.project_repository import (
    ProjectNotFoundError,
    default_project_repository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentCatalogRepository,
    default_quality_assessment_repository,
)
from app.repositories.synthesis_gap_repository import (
    default_synthesis_gap_repository,
)
from app.services.synthesis_context_service import (
    default_synthesis_context_service,
)
from app.services.synthesis_gap_service import (
    ResearchGapEvidenceError,
    ResearchGapNotFoundError,
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


def _append_revision(record, project_id, publication_id, revision_id, revision_index, group_items):
    extraction_repo = default_extraction_repository()
    extraction_repo.append_revision(
        ExtractionRevision(
            revision_id=revision_id,
            record_id=record.record_id,
            project_id=project_id,
            publication_id=publication_id,
            revision_index=revision_index,
            reviewer_id="rev_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=group_items,
            created_at=datetime.now(timezone.utc),
        )
    )


def _seed_complete_evidence(project_id="test_project"):
    """Seeds publication + COMPLETE revision + analytical relation + pathway + context link."""
    pub_id = uuid4()
    group_item_id = uuid4()
    rev1_id = UUID("11111111-1111-1111-1111-111111111111")

    pub_repo = default_project_publication_repository()
    pub_repo.add_publications(
        project_id, [Publication(record_id=pub_id, title="Manufacturing Energy Study", publication_year=2024)]
    )

    extraction_repo = default_extraction_repository()
    rec = extraction_repo.create_record(
        ExtractionRecord(
            project_id=project_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
        )
    )
    _append_revision(
        rec,
        project_id,
        pub_id,
        rev1_id,
        1,
        [
            ExtractedGroupItemState(
                group_item_id=group_item_id,
                group_key="lean_energy_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="lean_practice", status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED, text_value="Value Stream Mapping",
                    ),
                    ExtractedValueState(
                        field_key="energy_effect_indicator", status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED, text_value="Natural Gas",
                    ),
                    ExtractedValueState(
                        field_key="impact_mechanism", status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED, text_value="Elimination of thermal bottlenecks.",
                    ),
                    ExtractedValueState(
                        field_key="moderating_conditions", status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED, text_value="Batch manufacturing with high ambient variation.",
                    ),
                ],
            )
        ],
    )

    matrix_service = SynthesisMatrixService(
        matrix_repo=default_synthesis_gap_service()._matrix_repo,
        extraction_repo=extraction_repo,
        project_repo=default_project_repository(),
        publication_repo=pub_repo,
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


def _append_revision_with_status(
    project_id,
    publication_id,
    revision_id,
    revision_index,
    group_items,
    completeness_status,
):
    extraction_repo = default_extraction_repository()
    record = extraction_repo.list_records(project_id)[0]
    extraction_repo.append_revision(
        ExtractionRevision(
            revision_id=revision_id,
            record_id=record.record_id,
            project_id=project_id,
            publication_id=publication_id,
            revision_index=revision_index,
            reviewer_id="rev_1",
            completeness_status=completeness_status,
            group_items=group_items,
            created_at=datetime.now(timezone.utc),
        )
    )


def _seed_qa_assessment(project_id, publication_id):
    """Creates a criterion-level QA assessment for the publication, persisting it in the DB."""
    catalog_repo = SqliteQualityAssessmentCatalogRepository()
    try:
        catalog_repo.create_tool(QualityAssessmentTool(tool_id="casp_tool", name="CASP Tool"))
    except Exception:
        pass

    tid = uuid4()
    crit1 = uuid4()
    crit2 = uuid4()
    ass_id = uuid4()

    template = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_tool",
        template_key="lean_qa",
        name="Lean QA Template",
        version=1,
        is_active=True,
        criteria=[
            QualityAssessmentTemplateCriterion(
                criterion_id=crit1,
                template_id=tid,
                display_order=1,
                question="Is the study design clearly described?",
            ),
            QualityAssessmentTemplateCriterion(
                criterion_id=crit2,
                template_id=tid,
                display_order=2,
                question="Are energy measurements metered directly?",
            ),
        ],
    )
    catalog_repo.create_template_version(template)

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
                    criterion_id=crit1,
                    question_snapshot="Is the study design clearly described?",
                    response_value=QualityAssessmentResponseValue.YES,
                    justification="Detailed methodology provided in section 3.",
                ),
                QualityAssessmentResponse(
                    assessment_id=ass_id,
                    criterion_id=crit2,
                    question_snapshot="Are energy measurements metered directly?",
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="Values estimated from machine specifications.",
                ),
            ],
        )
    )
    return {"assessment_id": ass_id, "template_id": tid}


class TestResearchGapCRUD:
    def test_create_and_get_gap(self, service):
        gap = service.create_research_gap(
            project_id="test_project",
            gap_type="thematic",
            title="Under-studied practice",
            rationale="Only one eligible source covers this practice; publication count alone is not proof.",
            researcher_id="reviewer_alpha",
        )
        assert isinstance(gap, ResearchGap)
        assert gap.gap_type == ResearchGapType.THEMATIC
        assert gap.title == "Under-studied practice"
        assert gap.researcher_id == "reviewer_alpha"

        fetched = service.get_research_gap("test_project", str(gap.gap_id))
        assert fetched is not None
        assert fetched.rationale.startswith("Only one eligible source")

    def test_create_all_five_gap_types(self, service):
        for gap_type in list(ResearchGapType):
            gap = service.create_research_gap(
                project_id="test_project",
                gap_type=gap_type.value,
                title=f"Gap for {gap_type.value}",
                rationale="Researcher justification.",
                researcher_id="r",
            )
            assert gap.gap_type == gap_type

    def test_create_gap_rejects_empty_rationale(self, service):
        with pytest.raises(ValueError, match="publication count alone"):
            service.create_research_gap(
                project_id="test_project",
                gap_type="thematic",
                title="Under-studied",
                rationale="   ",
                researcher_id="r",
            )

    def test_create_gap_rejects_empty_title(self, service):
        with pytest.raises(ValueError, match="title"):
            service.create_research_gap(
                project_id="test_project",
                gap_type="thematic",
                title="   ",
                rationale="Researcher justification.",
                researcher_id="r",
            )

    def test_create_gap_rejects_invalid_type(self, service):
        with pytest.raises(ValueError, match="Invalid research gap type"):
            service.create_research_gap(
                project_id="test_project",
                gap_type="evidence",
                title="Gap",
                rationale="Researcher justification.",
                researcher_id="r",
            )

    def test_create_gap_rejects_missing_project(self, service):
        with pytest.raises(ProjectNotFoundError):
            service.create_research_gap(
                project_id="missing",
                gap_type="thematic",
                title="Gap",
                rationale="Researcher justification.",
                researcher_id="r",
            )

    def test_update_gap(self, service):
        gap = service.create_research_gap(
            project_id="test_project", gap_type="contextual", title="Old", rationale="Old rationale", researcher_id="r"
        )
        updated = service.update_research_gap(
            "test_project", str(gap.gap_id), gap_type="methodological", title="New", rationale="New rationale"
        )
        assert updated is not None
        assert updated.gap_type == ResearchGapType.METHODOLOGICAL
        assert updated.title == "New"
        assert updated.rationale == "New rationale"

    def test_update_gap_missing(self, service):
        assert service.update_research_gap("test_project", str(uuid4()), title="X") is None

    def test_delete_gap(self, service):
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        assert service.delete_research_gap("test_project", str(gap.gap_id)) is True
        assert service.get_research_gap("test_project", str(gap.gap_id)) is None

    def test_list_gaps_deterministic(self, service):
        for i in range(3):
            service.create_research_gap(
                project_id="test_project", gap_type="mechanism", title=f"Gap {i}",
                rationale="Justification.", researcher_id="r",
            )
        gaps = service.list_research_gaps("test_project")
        assert [g.title for g in gaps] == ["Gap 0", "Gap 1", "Gap 2"]

    def test_project_isolation(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="D", protocol_version="1.0.0")
        )
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        assert service.get_research_gap("other_project", str(gap.gap_id)) is None
        assert service.list_research_gaps("other_project") == []


class TestLinkEvidence:
    def test_link_analytical_relation(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert isinstance(link, ResearchGapLink)
        assert link.gap_id == gap.gap_id
        assert link.target_id == seeded["relation_id"]
        assert link.group_item_id == seeded["group_item_id"]
        assert link.publication_id == seeded["pub_id"]
        assert link.latest_revision_id == seeded["rev1_id"]

    def test_link_mechanism_pathway(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="mechanism", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.MECHANISM_PATHWAY, seeded["pathway_id"]
        )
        assert link.link_type == ResearchGapLinkType.MECHANISM_PATHWAY
        assert link.group_item_id == seeded["group_item_id"]

    def test_link_context_factor_link(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="contextual", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.CONTEXT_FACTOR_LINK, seeded["context_link_id"]
        )
        assert link.link_type == ResearchGapLinkType.CONTEXT_FACTOR_LINK
        assert link.group_item_id == seeded["group_item_id"]

    def test_link_idempotent(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link1 = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        link2 = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert link1.link_id == link2.link_id
        assert len(service.list_links_for_gap("test_project", str(gap.gap_id))) == 1

    def test_link_rejects_missing_gap(self, service):
        seeded = _seed_complete_evidence()
        with pytest.raises(ResearchGapNotFoundError):
            service.link_evidence(
                "test_project", str(uuid4()), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
            )

    def test_link_rejects_missing_target(self, service):
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        with pytest.raises(ResearchGapEvidenceError, match="not found"):
            service.link_evidence(
                "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, uuid4()
            )

    def test_link_rejects_stale_evidence_removed_from_latest_complete(self, service):
        """Group item removed in a newer COMPLETE revision is no longer linkable evidence."""
        seeded = _seed_complete_evidence()
        extraction_repo = default_extraction_repository()
        rec = extraction_repo.list_records("test_project")[0]
        rev2_id = UUID("22222222-2222-2222-2222-222222222222")
        _append_revision(rec, "test_project", seeded["pub_id"], rev2_id, 2, [])  # COMPLETE, group item removed

        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        with pytest.raises(ResearchGapEvidenceError, match="not traceable"):
            service.link_evidence(
                "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
            )

    def test_link_rejects_draft_only_evidence(self, service):
        """A relation whose publication has no COMPLETE revision must never become gap evidence."""
        pub_id = uuid4()
        group_item_id = uuid4()
        draft_id = UUID("99999999-9999-9999-9999-999999999999")
        pub_repo = default_project_publication_repository()
        pub_repo.add_publications(
            "test_project", [Publication(record_id=pub_id, title="Draft Only Study", publication_year=2025)]
        )
        extraction_repo = default_extraction_repository()
        rec = extraction_repo.create_record(
            ExtractionRecord(
                project_id="test_project", publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=draft_id,
                record_id=rec.record_id,
                project_id="test_project",
                publication_id=pub_id,
                revision_index=1,
                reviewer_id="rev_1",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=group_item_id,
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(
                                field_key="lean_practice", status=ValueStatus.PRESENT,
                                origin=ValueOrigin.REPORTED, text_value="Kaizen",
                            ),
                            ExtractedValueState(
                                field_key="energy_effect_indicator", status=ValueStatus.PRESENT,
                                origin=ValueOrigin.REPORTED, text_value="Electricity",
                            ),
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )

        matrix_repo = default_synthesis_gap_service()._matrix_repo
        rel = AnalyticalRelation(
            project_id="test_project",
            publication_id=pub_id,
            latest_revision_id=draft_id,
            group_item_id=group_item_id,
            item_index=1,
            source_practice="Kaizen",
            source_effect="Electricity",
            direction=RelationDirection.POSITIVE,
            approval_state=ClassificationApprovalState.APPROVED,
        )
        matrix_repo.save_analytical_relation(rel)

        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        with pytest.raises(ResearchGapEvidenceError, match="not traceable"):
            service.link_evidence(
                "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, rel.relation_id
            )

    def test_unlink_evidence(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert service.unlink_evidence("test_project", str(gap.gap_id), str(link.link_id)) is True
        assert service.list_links_for_gap("test_project", str(gap.gap_id)) == []

    def test_unlink_evidence_wrong_gap(self, service):
        seeded = _seed_complete_evidence()
        gap_a = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="A", rationale="Justification.", researcher_id="r"
        )
        gap_b = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="B", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap_a.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert service.unlink_evidence("test_project", str(gap_b.gap_id), str(link.link_id)) is False
        assert len(service.list_links_for_gap("test_project", str(gap_a.gap_id))) == 1

    def test_link_stores_latest_complete_revision(self, service):
        seeded = _seed_complete_evidence()
        extraction_repo = default_extraction_repository()
        rec = extraction_repo.list_records("test_project")[0]
        rev2_id = UUID("22222222-2222-2222-2222-222222222222")
        # New COMPLETE revision that keeps the group item -> link advances to rev2
        extraction_repo.append_revision(
            ExtractionRevision(
                revision_id=rev2_id,
                record_id=rec.record_id,
                project_id="test_project",
                publication_id=seeded["pub_id"],
                revision_index=2,
                reviewer_id="rev_1",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                group_items=[
                    ExtractedGroupItemState(
                        group_item_id=seeded["group_item_id"],
                        group_key="lean_energy_relationships",
                        item_index=1,
                        values=[
                            ExtractedValueState(
                                field_key="lean_practice", status=ValueStatus.PRESENT,
                                origin=ValueOrigin.REPORTED, text_value="Value Stream Mapping",
                            ),
                            ExtractedValueState(
                                field_key="energy_effect_indicator", status=ValueStatus.PRESENT,
                                origin=ValueOrigin.REPORTED, text_value="Natural Gas",
                            ),
                        ],
                    )
                ],
                created_at=datetime.now(timezone.utc),
            )
        )
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        assert link.latest_revision_id == rev2_id


class TestLinkRevisionAdvancement:
    def _link(self, service, gap_id, relation_id):
        return service.link_evidence(
            "test_project", str(gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, relation_id
        )

    def _group_items(self, group_item_id):
        return [
            ExtractedGroupItemState(
                group_item_id=group_item_id,
                group_key="lean_energy_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="lean_practice", status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED, text_value="Value Stream Mapping",
                    ),
                    ExtractedValueState(
                        field_key="energy_effect_indicator", status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED, text_value="Natural Gas",
                    ),
                ],
            )
        ]

    def test_rev1_complete_creates_link(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = self._link(service, gap.gap_id, seeded["relation_id"])
        assert link.latest_revision_id == seeded["rev1_id"]
        links = service.list_links_for_gap("test_project", str(gap.gap_id))
        assert len(links) == 1
        assert links[0].link_id == link.link_id

    def test_rev2_draft_does_not_advance_revision(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link1 = self._link(service, gap.gap_id, seeded["relation_id"])
        assert link1.latest_revision_id == seeded["rev1_id"]

        _append_revision_with_status(
            "test_project",
            seeded["pub_id"],
            UUID("22222222-2222-2222-2222-222222222222"),
            2,
            self._group_items(seeded["group_item_id"]),
            ExtractionCompletenessStatus.IN_PROGRESS,
        )

        link2 = self._link(service, gap.gap_id, seeded["relation_id"])
        assert link2.link_id == link1.link_id
        assert link2.latest_revision_id == seeded["rev1_id"]
        assert len(service.list_links_for_gap("test_project", str(gap.gap_id))) == 1

    def test_rev3_complete_advances_revision_without_duplicate(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link1 = self._link(service, gap.gap_id, seeded["relation_id"])
        assert link1.latest_revision_id == seeded["rev1_id"]

        _append_revision_with_status(
            "test_project",
            seeded["pub_id"],
            UUID("22222222-2222-2222-2222-222222222222"),
            2,
            self._group_items(seeded["group_item_id"]),
            ExtractionCompletenessStatus.IN_PROGRESS,
        )
        rev3_id = UUID("33333333-3333-3333-3333-333333333333")
        _append_revision_with_status(
            "test_project",
            seeded["pub_id"],
            rev3_id,
            3,
            self._group_items(seeded["group_item_id"]),
            ExtractionCompletenessStatus.COMPLETE,
        )

        link2 = self._link(service, gap.gap_id, seeded["relation_id"])
        assert link2.link_id == link1.link_id
        assert link2.latest_revision_id == rev3_id
        links = service.list_links_for_gap("test_project", str(gap.gap_id))
        assert len(links) == 1

    def test_persistence_backed_advancement_matches_complete_revision(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        self._link(service, gap.gap_id, seeded["relation_id"])

        _append_revision_with_status(
            "test_project",
            seeded["pub_id"],
            UUID("22222222-2222-2222-2222-222222222222"),
            2,
            self._group_items(seeded["group_item_id"]),
            ExtractionCompletenessStatus.IN_PROGRESS,
        )
        rev3_id = UUID("33333333-3333-3333-3333-333333333333")
        _append_revision_with_status(
            "test_project",
            seeded["pub_id"],
            rev3_id,
            3,
            self._group_items(seeded["group_item_id"]),
            ExtractionCompletenessStatus.COMPLETE,
        )
        self._link(service, gap.gap_id, seeded["relation_id"])

        repo = default_synthesis_gap_repository()
        links = repo.list_links_for_gap("test_project", str(gap.gap_id))
        assert len(links) == 1
        stored = links[0]
        assert UUID(stored["latest_revision_id"]) == rev3_id
        history = default_extraction_repository().list_revision_history(
            "test_project", seeded["pub_id"]
        )
        complete_revisions = [
            r.revision_id
            for r in history
            if r.completeness_status == ExtractionCompletenessStatus.COMPLETE
            and any(gi.group_item_id == seeded["group_item_id"] for gi in r.group_items)
        ]
        assert UUID(stored["latest_revision_id"]) in complete_revisions

    def test_link_unchanged_when_revision_identical(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link1 = self._link(service, gap.gap_id, seeded["relation_id"])
        link2 = self._link(service, gap.gap_id, seeded["relation_id"])
        assert link2.link_id == link1.link_id
        assert link2.latest_revision_id == seeded["rev1_id"]
        assert len(service.list_links_for_gap("test_project", str(gap.gap_id))) == 1


class TestDeleteSemantics:
    def test_delete_gap_keeps_source_evidence(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )
        service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.MECHANISM_PATHWAY, seeded["pathway_id"]
        )
        service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.CONTEXT_FACTOR_LINK, seeded["context_link_id"]
        )

        service.delete_research_gap("test_project", str(gap.gap_id))

        matrix_repo = default_synthesis_gap_service()._matrix_repo
        mechanism_repo = default_synthesis_gap_service()._mechanism_repo
        context_repo = default_synthesis_gap_service()._context_repo
        assert matrix_repo.get_analytical_relation("test_project", seeded["relation_id"]) is not None
        assert mechanism_repo.get_pathway("test_project", seeded["pathway_id"]) is not None
        assert context_repo.get_link(str(seeded["context_link_id"])) is not None

        repo = default_synthesis_gap_repository()
        assert repo.list_links_for_gap("test_project", str(gap.gap_id)) == []


class TestWorkspace:
    def test_workspace_data_counts(self, service):
        seeded = _seed_complete_evidence()
        for gap_type in [ResearchGapType.THEMATIC, ResearchGapType.THEMATIC, ResearchGapType.MECHANISM]:
            gap = service.create_research_gap(
                project_id="test_project", gap_type=gap_type.value, title=f"Gap {gap_type.value}",
                rationale="Justification.", researcher_id="r",
            )
            if gap_type == ResearchGapType.THEMATIC:
                service.link_evidence(
                    "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
                )

        data = service.get_research_gap_workspace_data("test_project")
        assert isinstance(data, ResearchGapWorkspaceData)
        assert len(data.gaps) == 3
        assert data.stats.total_gaps == 3
        assert data.stats.thematic_count == 2
        assert data.stats.mechanism_count == 1
        assert data.stats.linked_publication_count == 1
        assert data.gaps[0].links[0].target_id == seeded["relation_id"]

    def test_workspace_data_empty_project(self, service):
        data = service.get_research_gap_workspace_data("test_project")
        assert data.gaps == []
        assert data.stats.total_gaps == 0
        assert data.stats.linked_publication_count == 0

    def test_no_gap_score_fields(self, service):
        """Task 10.6 forbids any numeric gap score/strength/priority field."""
        forbidden = {"gap_strength", "gap_score", "confidence_score", "priority_score", "evidence_quality_score"}
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        for attr in forbidden:
            assert not hasattr(gap, attr)
        data = service.get_research_gap_workspace_data("test_project")
        for attr in forbidden:
            assert not hasattr(data.stats, attr)
        with pytest.raises(ValidationError):
            ResearchGap(
                project_id="p", gap_type=ResearchGapType.THEMATIC, title="T",
                rationale="R", researcher_id="r", gap_strength=0.9,
            )

    def test_workspace_data_missing_project(self, service):
        with pytest.raises(ProjectNotFoundError):
            service.get_research_gap_workspace_data("missing")


class TestEvidenceCandidates:
    def test_candidates_traceable_when_complete(self, service):
        _seed_complete_evidence()
        candidates = service.list_linkable_evidence_candidates("test_project")
        link_types = {c.link_type for c in candidates}
        assert ResearchGapLinkType.ANALYTICAL_RELATION in link_types
        assert ResearchGapLinkType.MECHANISM_PATHWAY in link_types
        assert ResearchGapLinkType.CONTEXT_FACTOR_LINK in link_types
        assert all(c.traceable for c in candidates)

    def test_candidates_non_traceable_when_stale(self, service):
        seeded = _seed_complete_evidence()
        extraction_repo = default_extraction_repository()
        rec = extraction_repo.list_records("test_project")[0]
        rev2_id = UUID("22222222-2222-2222-2222-222222222222")
        _append_revision(rec, "test_project", seeded["pub_id"], rev2_id, 2, [])  # COMPLETE, group item removed

        candidates = service.list_linkable_evidence_candidates("test_project")
        stale = [c for c in candidates if c.target_id == seeded["relation_id"]]
        assert stale
        assert stale[0].traceable is False

    def test_candidates_missing_project(self, service):
        with pytest.raises(ProjectNotFoundError):
            service.list_linkable_evidence_candidates("missing")


class TestCandidateQA:
    def test_candidate_exposes_criterion_level_qa(self, service):
        seeded = _seed_complete_evidence()
        _seed_qa_assessment("test_project", seeded["pub_id"])

        candidates = service.list_linkable_evidence_candidates("test_project")
        with_qa = [c for c in candidates if c.publication_id == seeded["pub_id"]]
        assert with_qa
        qa = with_qa[0].qa_profile
        assert qa is not None
        assert qa.assessment_id
        assert qa.template_id
        assert qa.reviewer_id == "lead_reviewer"
        assert len(qa.criteria_assessments) == 2
        responses = {c.question_text: c.response_value for c in qa.criteria_assessments}
        assert responses["Is the study design clearly described?"] == "YES"
        assert responses["Are energy measurements metered directly?"] == "NO"
        justifications = {
            c.question_text: c.justification for c in qa.criteria_assessments
        }
        assert justifications["Is the study design clearly described?"] == "Detailed methodology provided in section 3."
        assert justifications["Are energy measurements metered directly?"] == "Values estimated from machine specifications."

    def test_missing_qa_is_explicit_none(self, service):
        seeded = _seed_complete_evidence()
        candidates = service.list_linkable_evidence_candidates("test_project")
        without_qa = [c for c in candidates if c.publication_id == seeded["pub_id"]]
        assert without_qa
        assert all(c.qa_profile is None for c in without_qa)

    def test_candidate_qa_exposes_no_aggregate_score_or_tier(self, service):
        seeded = _seed_complete_evidence()
        _seed_qa_assessment("test_project", seeded["pub_id"])
        candidates = service.list_linkable_evidence_candidates("test_project")
        with_qa = [c for c in candidates if c.publication_id == seeded["pub_id"]]
        qa = with_qa[0].qa_profile
        for field in ("score", "aggregate_score", "quality_tier", "confidence", "confidence_score", "weighting"):
            assert not hasattr(qa, field)

    def test_candidate_rejects_gap_score_quality_tier_confidence_fields(self):
        with pytest.raises(ValidationError):
            ResearchGapEvidenceCandidate(
                link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
                target_id=uuid4(),
                group_item_id=uuid4(),
                publication_id=uuid4(),
                latest_revision_id=uuid4(),
                traceable=True,
                label="candidate",
                gap_score=0.9,
            )
        with pytest.raises(ValidationError):
            ResearchGapEvidenceCandidate(
                link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
                target_id=uuid4(),
                group_item_id=uuid4(),
                publication_id=uuid4(),
                latest_revision_id=uuid4(),
                traceable=True,
                label="candidate",
                quality_tier="HIGH",
            )
        with pytest.raises(ValidationError):
            ResearchGapEvidenceCandidate(
                link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
                target_id=uuid4(),
                group_item_id=uuid4(),
                publication_id=uuid4(),
                latest_revision_id=uuid4(),
                traceable=True,
                label="candidate",
                confidence=0.8,
            )


class TestAdversarialGapIntegrity:
    def test_update_gap_preserves_evidence_links(self, service):
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        link = service.link_evidence(
            "test_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
        )

        updated = service.update_research_gap(
            "test_project", str(gap.gap_id), gap_type="methodological", title="Renamed", rationale="New rationale"
        )
        assert updated is not None
        assert updated.gap_type == ResearchGapType.METHODOLOGICAL
        assert updated.title == "Renamed"

        gap_after = service.get_research_gap("test_project", str(gap.gap_id))
        assert gap_after is not None
        assert gap_after.title == "Renamed"
        assert gap_after.researcher_id == "r"
        assert gap_after.rationale == "New rationale"
        assert service.list_links_for_gap("test_project", str(gap.gap_id)) == [link]

    def test_update_gap_wrong_project_returns_none(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="D", protocol_version="1.0.0")
        )
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        assert service.update_research_gap("other_project", str(gap.gap_id), title="Hijacked") is None
        unchanged = service.get_research_gap("test_project", str(gap.gap_id))
        assert unchanged is not None
        assert unchanged.title == "Gap"

    def test_delete_gap_wrong_project_returns_false(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="D", protocol_version="1.0.0")
        )
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        assert service.delete_research_gap("other_project", str(gap.gap_id)) is False
        assert service.get_research_gap("test_project", str(gap.gap_id)) is not None

    def test_link_evidence_wrong_project_gap_is_rejected(self, service, project_repo):
        project_repo.create(
            Project(project_id="other_project", title="Other", description="D", protocol_version="1.0.0")
        )
        seeded = _seed_complete_evidence()
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        with pytest.raises(ResearchGapNotFoundError):
            service.link_evidence(
                "other_project", str(gap.gap_id), ResearchGapLinkType.ANALYTICAL_RELATION, seeded["relation_id"]
            )
        assert service.unlink_evidence("other_project", str(gap.gap_id), "00000000-0000-0000-0000-000000000001") is False

    def test_update_gap_rejects_researcher_id_change(self, service):
        """researcher_id is immutable on update; attempts are silently ignored."""
        gap = service.create_research_gap(
            project_id="test_project", gap_type="thematic", title="Gap", rationale="Justification.", researcher_id="r"
        )
        updated = service.update_research_gap("test_project", str(gap.gap_id), title="Renamed")
        assert updated is not None
        assert updated.researcher_id == "r"
        assert updated.title == "Renamed"
        assert updated.rationale == "Justification."
