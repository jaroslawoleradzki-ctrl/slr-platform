"""Unit tests for PRISMA 2020 flow model, builder, and SVG renderer (v0.6.1 Slice 3)."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.domain.conflict_resolution import (
    ConflictResolution,
    ResolvedOutcome,
    compute_decision_set_key,
)
from app.domain.project import Project
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services.export.prisma_flow_builder import build_flow_model
from app.services.export.prisma_svg_renderer import render_prisma_svg
from app.services.export_dataset_service import ExportDatasetService
from app.services.prisma_metrics_service import PrismaMetrics
from tests.fixtures.factories import make_publication

PROJECT_ID = "prisma_flow_project"


def _sample_metrics(
    *,
    providers: int = 150,
    imports: int = 50,
    working: int = 200,
    after_dedup: int = 180,
    screened_ta: int = 180,
    screened_ft: int = 120,
    included: int = 45,
    pending_groups: int = 2,
    manual_breakdown: dict[str, int] | None = None,
) -> PrismaMetrics:
    return PrismaMetrics(
        project_id=PROJECT_ID,
        records_identified_providers=providers,
        records_identified_imports=imports,
        total_identified=providers + imports,
        records_after_normalization=working,
        records_before_dedup=working,
        records_after_technical_merger=after_dedup,
        duplicate_groups_pending_review=pending_groups,
        records_screened_title_abstract=screened_ta,
        records_screened_full_text=screened_ft,
        studies_included_synthesis=included,
        manual_source_breakdown=manual_breakdown or {"pubmed_export": 30, "scopus_export": 20},
    )


class TestPrismaFlowBuilder:
    def test_flow_model_derives_correct_stages_and_nodes(self) -> None:
        metrics = _sample_metrics()
        model = build_flow_model(metrics)

        assert model.project_id == PROJECT_ID
        assert len(model.nodes) == 9
        assert len(model.edges) == 8

        node_map = {n.node_id: n for n in model.nodes}
        assert node_map["identification.databases"].values["count"] == 150
        assert node_map["identification.other_methods"].values["count"] == 50
        assert node_map["identification.after_deduplication"].values["count"] == 180
        assert node_map["screening.title_abstract"].values["count"] == 180
        assert node_map["screening.full_text"].values["count"] == 120
        assert node_map["included.synthesis"].values["count"] == 45

    def test_flow_model_derives_correct_exclusions_and_side_boxes(self) -> None:
        metrics = _sample_metrics(
            working=200,
            after_dedup=180,
            screened_ta=180,
            screened_ft=120,
            included=45,
        )
        model = build_flow_model(metrics)

        assert model.removed["duplicates_removed"] == 20  # 200 - 180
        assert model.removed["excluded_title_abstract"] == 60  # 180 - 120
        assert model.removed["excluded_full_text"] == 75  # 120 - 45

        node_map = {n.node_id: n for n in model.nodes}
        assert node_map["identification.records_removed"].values["duplicates_removed"] == 20
        assert node_map["identification.records_removed"].annotations["pending_review"] == "2"
        assert node_map["screening.excluded_title_abstract"].values["count"] == 60
        assert node_map["screening.excluded_full_text"].values["count"] == 75

    def test_flow_model_handles_zeroes_and_empty_project(self) -> None:
        metrics = _sample_metrics(
            providers=0,
            imports=0,
            working=0,
            after_dedup=0,
            screened_ta=0,
            screened_ft=0,
            included=0,
            pending_groups=0,
            manual_breakdown={},
        )
        model = build_flow_model(metrics)

        assert model.removed["duplicates_removed"] == 0
        assert model.removed["excluded_title_abstract"] == 0
        assert model.removed["excluded_full_text"] == 0

        for node in model.nodes:
            for val in node.values.values():
                assert val == 0

    def test_flow_model_metadata_echoes_counts(self) -> None:
        metrics = _sample_metrics()
        now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
        project = Project(project_id=PROJECT_ID, title="Metabolic Health", protocol_version="v2.1")
        model = build_flow_model(metrics, project=project, generated_at=now)

        assert model.metadata.project_title == "Metabolic Health"
        assert model.metadata.protocol_version == "v2.1"
        assert model.metadata.generated_at == now.isoformat()
        assert model.metadata.counts_echo["studies_included_synthesis"] == 45
        assert model.metadata.counts_echo["total_identified"] == 200


class TestPrismaSvgRenderer:
    def test_render_svg_produces_valid_xml(self) -> None:
        metrics = _sample_metrics()
        model = build_flow_model(metrics)
        svg_text = render_prisma_svg(model)

        assert svg_text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        root = ET.fromstring(svg_text)
        assert root.tag.endswith("svg")
        assert root.attrib.get("viewBox") == "0 0 860 980"

    def test_render_svg_escapes_xml_special_characters(self) -> None:
        metrics = _sample_metrics(
            manual_breakdown={'malicious <script> & "quote"': 10}
        )
        project = Project(
            project_id=PROJECT_ID,
            title='Adversarial & <Unescaped> "Project" Title',
            protocol_version='v1.0 & <alpha>',
        )
        model = build_flow_model(metrics, project=project)
        svg_text = render_prisma_svg(model)

        # Must parse cleanly as XML
        root = ET.fromstring(svg_text)
        assert root is not None

        # Verify raw unescaped tags are not present in raw XML string
        assert "<script>" not in svg_text
        assert "<Unescaped>" not in svg_text
        assert "&amp;" in svg_text

    def test_render_svg_byte_identical_reproducibility(self) -> None:
        metrics = _sample_metrics()
        model1 = build_flow_model(metrics)
        model2 = build_flow_model(metrics)

        svg1 = render_prisma_svg(model1)
        svg2 = render_prisma_svg(model2)

        assert svg1 == svg2

    def test_render_svg_contains_expected_visible_nodes_and_stages(self) -> None:
        metrics = _sample_metrics()
        model = build_flow_model(metrics)
        svg_text = render_prisma_svg(model)

        assert "Identification" in svg_text
        assert "Screening" in svg_text
        assert "Included" in svg_text
        assert "Records identified from databases &amp; registers" in svg_text
        assert "Database records (n = 150)" in svg_text
        assert "Manual file imports (n = 50)" in svg_text
        assert "Technical duplicates merged (n = 20)" in svg_text
        assert "Active canonical records (n = 180)" in svg_text
        assert "Title &amp; Abstract screened (n = 180)" in svg_text
        assert "Title &amp; Abstract excluded (n = 60)" in svg_text
        assert "Full-Text reports assessed (n = 120)" in svg_text
        assert "Full-Text excluded (n = 75)" in svg_text
        assert "Studies included in synthesis (n = 45)" in svg_text


class TestD4PrismaInclusionDefinition:
    """Definition-locking tests for D4: studies_included_synthesis ≡ final Full-Text INCLUDE population."""

    def test_multi_reviewer_resolved_conflict_to_include_counted_in_synthesis(self, tmp_path: Path) -> None:
        db_path = tmp_path / "d4_multi.db"
        proj_repo = SqliteProjectRepository(db_path)
        proj_repo.create(Project(project_id=PROJECT_ID, title="D4 Multi"))

        pub_repo = SqliteProjectPublicationRepository(db_path)
        pub1 = make_publication(1, title="Paper 1")
        pub_repo.add_publications(PROJECT_ID, [pub1])

        # Active Title & Abstract and Full-Text rosters with 2 reviewers
        roster_repo = SqliteScreeningReviewerAssignmentRepository(db_path)
        roster_repo.replace_active(PROJECT_ID, ScreeningStage.TITLE_ABSTRACT, ["rev_1", "rev_2"])
        roster_repo.replace_active(PROJECT_ID, ScreeningStage.FULL_TEXT, ["rev_1", "rev_2"])

        # Seed Title & Abstract decisions as INCLUDE for both reviewers
        dec_repo = SqliteScreeningDecisionRepository(db_path)
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_1",
            )
        )
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_2",
            )
        )

        # Full-Text Reviewer decisions: rev_1 INCLUDE, rev_2 EXCLUDE (Conflict!)
        dec_1 = dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_1",
            )
        )
        dec_2 = dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.EXCLUDE,
                reviewer_id="rev_2",
            )
        )

        # Conflict resolution verdict: RESOLVED to INCLUDE
        res_id = uuid4()
        key = compute_decision_set_key(
            PROJECT_ID,
            pub1.record_id,
            ScreeningStage.FULL_TEXT,
            ("rev_1", "rev_2"),
            {"rev_1": dec_1, "rev_2": dec_2},
        )
        resolution = ConflictResolution(
            resolution_id=res_id,
            project_id=PROJECT_ID,
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            decision_set_key=key,
            resolved_outcome=ResolvedOutcome.INCLUDE,
            resolver_id="adjudicator",
            rationale="Resolved after discussion",
            resolved_at=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
            decision_ids=(dec_1.decision_id, dec_2.decision_id),
        )
        resolutions_repo = SqliteConflictResolutionRepository(db_path)
        resolutions_repo.save(
            resolution,
            [
                (dec_1.decision_id, "rev_1", ResolvedOutcome.INCLUDE),
                (dec_2.decision_id, "rev_2", ResolvedOutcome.EXCLUDE),
            ],
        )

        reporting_repo = ScreeningReportingRepository(db_path)
        service = ExportDatasetService(
            publication_repository=pub_repo,
            screening_reporting_repository=reporting_repo,
        )

        metrics = service.get_prisma_metrics(PROJECT_ID)
        assert metrics.studies_included_synthesis == 1

        flow_model = service.get_prisma_flow_model(PROJECT_ID)
        inc_node = next(n for n in flow_model.nodes if n.node_id == "included.synthesis")
        assert inc_node.values["count"] == 1

    def test_superseded_record_excluded_from_studies_included_synthesis(self, tmp_path: Path) -> None:
        db_path = tmp_path / "d4_superseded.db"
        proj_repo = SqliteProjectRepository(db_path)
        proj_repo.create(Project(project_id=PROJECT_ID, title="D4 Superseded"))

        pub_repo = SqliteProjectPublicationRepository(db_path)
        pub1 = make_publication(1, title="Canonical Paper")
        pub2 = make_publication(2, title="Duplicate Paper")
        pub_repo.add_publications(PROJECT_ID, [pub1, pub2])
        pub_repo.mark_superseded(PROJECT_ID, [pub2.record_id], pub1.record_id)

        # Decision on superseded record pub2 is INCLUDE; decision on canonical pub1 is EXCLUDE
        dec_repo = SqliteScreeningDecisionRepository(db_path)
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub2.record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_1",
            )
        )
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.EXCLUDE,
                reviewer_id="rev_1",
            )
        )

        reporting_repo = ScreeningReportingRepository(db_path)
        service = ExportDatasetService(
            publication_repository=pub_repo,
            screening_reporting_repository=reporting_repo,
        )

        metrics = service.get_prisma_metrics(PROJECT_ID, reviewer_id="rev_1")
        # Only active canonical pub1 enters evaluation -> outcome is EXCLUDE -> studies_included_synthesis is 0
        assert metrics.studies_included_synthesis == 0

    def test_single_reviewer_latest_decision_wins(self, tmp_path: Path) -> None:
        db_path = tmp_path / "d4_single.db"
        proj_repo = SqliteProjectRepository(db_path)
        proj_repo.create(Project(project_id=PROJECT_ID, title="D4 Single"))

        pub_repo = SqliteProjectPublicationRepository(db_path)
        pub1 = make_publication(1, title="Paper 1")
        pub_repo.add_publications(PROJECT_ID, [pub1])

        dec_repo = SqliteScreeningDecisionRepository(db_path)
        # First decision: EXCLUDE
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.EXCLUDE,
                reviewer_id="rev_1",
                decided_at=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            )
        )
        # Second (latest) decision: INCLUDE
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pub1.record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_1",
                decided_at=datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc),
            )
        )

        reporting_repo = ScreeningReportingRepository(db_path)
        service = ExportDatasetService(
            publication_repository=pub_repo,
            screening_reporting_repository=reporting_repo,
        )

        metrics = service.get_prisma_metrics(PROJECT_ID, reviewer_id="rev_1")
        assert metrics.studies_included_synthesis == 1
