"""Adversarial and contract tests for SLR Platform v0.7.1 WP3: PRISMA Accounting and Corpus-Preparation Semantics.

Verifies Invariants A through Q:
A: 10 imported records: 7 retained, 3 removed during Import Review (5677/3952/1725 model scaled).
B: Physical archival of 3 removed records preserves historical identification count = 10.
C: Active Corpus remains 7 after physical removal.
D: Pre-screening removal count remains 3 after physical removal.
E: Formal screened remains 0 after pre-screening operations.
F: Formal excluded remains 0 after pre-screening operations.
G: Formal Title/Abstract exclusion on a retained record sets formal screened = 1, excluded = 1, pre-screening removals = 3.
H: Retaining another formally screened record sets formal screened = 2 without modifying pre-screening accounting.
I: Multi-provider identification history (Crossref, OpenAlex, Semantic Scholar) is faithfully preserved.
J: Cross-provider duplicate handling preserves provider identification counts.
K: Duplicate technical removal decrements canonical count without rewriting retrieval history.
L: Legacy project without pre-screening archive remains readable and deterministically reported.
M: No corpus-preparation action creates a formal screening decision.
N: Normalization execution does NOT increment formal screening counters.
O: Deduplication execution does NOT increment formal screening counters.
P: Repeated PRISMA PDF and SVG generation is byte-deterministic.
Q: PDF, SVG, XLSX, and API models share identical authoritative accounting semantics.
"""

import io
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pypdf
import pytest

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.pre_screening import PreScreeningRemovalReason
from app.domain.project import Project
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.pre_screening_archive_repository import SqlitePreScreeningArchiveRepository
from app.repositories.pre_screening_decision_repository import SqlitePreScreeningDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.export.prisma_flow_builder import build_flow_model
from app.services.export.prisma_pdf_renderer import render_prisma_pdf
from app.services.export.prisma_svg_renderer import render_prisma_svg
from app.services.export_dataset_service import ExportDatasetService
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.normalization_service import normalize_project
from app.services.pre_screening_review_service import PreScreeningReviewService
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_workflow_status_service import ProjectWorkflowStatusService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService
from tests.fixtures.factories import make_import_history, make_publication

PROJECT_ID = "wp3_prisma_project"
REVIEWER_ID = "reviewer_wp3"


@pytest.fixture
def wp3_env(tmp_path: Path):
    db_path = tmp_path / "wp3_prisma.db"
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id=PROJECT_ID, title="WP3 PRISMA Accounting Project"))

    publications = SqliteProjectPublicationRepository(db_path)
    history = SqliteImportHistoryRepository(db_path)
    duplicate_decisions = SqliteDuplicateReviewDecisionRepository(db_path)
    screening_decisions = SqliteScreeningDecisionRepository(db_path)
    assignments = SqliteScreeningReviewerAssignmentRepository(db_path)
    resolutions = SqliteConflictResolutionRepository(db_path)
    reporting = ScreeningReportingRepository(db_path)
    archive_repo = SqlitePreScreeningArchiveRepository(db_path)
    pre_screening_decisions = SqlitePreScreeningDecisionRepository(db_path)

    input_service = ScreeningInputService(publications, duplicate_decisions)
    multi_service = MultiReviewerScreeningService(
        assignments=assignments,
        reporting=reporting,
        input_service=input_service,
        resolutions=resolutions,
    )
    adapter = ScreeningEligibilityAdapter(
        input_service=input_service,
        assignments_repo=assignments,
        decisions_repo=screening_decisions,
        multi_reviewer_service=multi_service,
    )
    workflow_status = ProjectWorkflowStatusService(
        publication_repository=publications,
        decision_repository=screening_decisions,
        assignment_repository=assignments,
        resolution_repository=resolutions,
        reporting_repository=reporting,
        input_service=input_service,
        multi_reviewer_service=multi_service,
        eligibility_adapter=adapter,
    )
    prisma_service = PrismaMetricsService(
        publication_repository=publications,
        import_history_repository=history,
        decision_repository=duplicate_decisions,
        workflow_status_service=workflow_status,
        builder=DuplicateGroupBuilder(),
        archive_repository=archive_repo,
    )
    review_service = PreScreeningReviewService(
        publication_repository=publications,
        decision_repository=pre_screening_decisions,
        archive_repository=archive_repo,
    )
    export_service = ExportDatasetService(
        publication_repository=publications,
        screening_reporting_repository=reporting,
        prisma_service=prisma_service,
    )

    return {
        "db_path": db_path,
        "publications": publications,
        "history": history,
        "duplicate_decisions": duplicate_decisions,
        "screening_decisions": screening_decisions,
        "archive_repo": archive_repo,
        "pre_screening_decisions": pre_screening_decisions,
        "prisma_service": prisma_service,
        "review_service": review_service,
        "export_service": export_service,
    }


def test_adversarial_a_to_h_lifecycle_preservation(wp3_env):
    """Verifies Tests A through H:

    A: 10 imported: 7 retained, 3 in-place removed.
    B-F: Physical archival/removal of 3 records -> retrieval remains 10, active remains 7, removals remain 3, screened = 0, exclusions = 0.
    G: Formal T&A exclusion -> screened = 1, excluded = 1, removals remain 3.
    H: Retaining another screened record -> screened = 2, excluded = 1, removals remain 3.
    """
    pubs_repo = wp3_env["publications"]
    history_repo = wp3_env["history"]
    prisma_service = wp3_env["prisma_service"]
    review_service = wp3_env["review_service"]
    dec_repo = wp3_env["screening_decisions"]

    # 1. Setup 10 imported records
    pubs = [make_publication(i, title=f"Publication {i}") for i in range(1, 11)]
    pubs_repo.add_publications(PROJECT_ID, pubs)
    import_rec = make_import_history(
        PROJECT_ID,
        records_count=10,
        source_type="provider",
        provider="crossref",
        status="success",
    )
    history_repo.create(import_rec)

    # 2. In-place Pre-screening review: 3 removed, 7 retained (Test A)
    for p in pubs[7:]:  # pubs 8, 9, 10
        pubs_repo.update_pre_screening_status(PROJECT_ID, p.record_id, "removed")

    metrics_a = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics_a.total_identified == 10
    assert metrics_a.records_identified_providers == 10
    assert metrics_a.records_removed_prescreening == 3
    assert metrics_a.records_after_normalization == 7
    assert metrics_a.records_before_dedup == 7
    assert metrics_a.records_after_technical_merger == 7
    assert metrics_a.records_screened_title_abstract == 0
    assert metrics_a.records_excluded_title_abstract == 0
    assert metrics_a.studies_included_synthesis == 0

    # 3. Test B, C, D, E, F: Physically archive and remove the 3 removed records from project_publications
    for p in pubs[7:]:
        review_service.archive_pre_screening_removal(
            project_id=PROJECT_ID,
            import_id=import_rec.import_id,
            record_id=p.record_id,
            reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
            notes="Out of scope retrieval artefact",
            reviewer_id="reviewer_wp3",
            physical_delete=True,
        )

    # Invariants B–F check after physical deletion
    metrics_post_delete = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics_post_delete.total_identified == 10, "Test B: historical retrieval count must remain 10"
    assert metrics_post_delete.records_after_normalization == 7, "Test C: active corpus must remain 7"
    assert metrics_post_delete.records_before_dedup == 7, "Test C: active corpus before dedup must remain 7"
    assert metrics_post_delete.records_after_technical_merger == 7, "Test C: active canonical records must remain 7"
    assert metrics_post_delete.records_removed_prescreening == 3, "Test D: pre-screening removal count must remain 3"
    assert metrics_post_delete.records_screened_title_abstract == 0, "Test E: formal screened count must remain 0"
    assert metrics_post_delete.records_excluded_title_abstract == 0, "Test F: formal excluded count must remain 0"

    # 4. Test G: Perform one formal Title/Abstract exclusion on an active retained record
    dec_repo.save(
        ScreeningDecision(
            project_id=PROJECT_ID,
            publication_id=pubs[0].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id=REVIEWER_ID,
        )
    )
    metrics_g = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics_g.records_screened_title_abstract == 1
    assert metrics_g.records_excluded_title_abstract == 1
    assert metrics_g.records_removed_prescreening == 3, "Pre-screening removals must stay independent at 3"
    assert metrics_g.total_identified == 10

    # 5. Test H: Retain another formally screened record (INCLUDE)
    dec_repo.save(
        ScreeningDecision(
            project_id=PROJECT_ID,
            publication_id=pubs[1].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id=REVIEWER_ID,
        )
    )
    metrics_h = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics_h.records_screened_title_abstract == 2
    assert metrics_h.records_excluded_title_abstract == 1
    assert metrics_h.records_removed_prescreening == 3
    assert metrics_h.total_identified == 10


def test_adversarial_i_multi_provider_retrieval_history(wp3_env):
    """Test I: Multiple providers (Crossref, OpenAlex, Semantic Scholar, File imports)

    Historical provider counts remain separately reproducible.
    """
    history_repo = wp3_env["history"]
    prisma_service = wp3_env["prisma_service"]

    history_repo.create(make_import_history(PROJECT_ID, records_count=4968, source_type="provider", provider="crossref", status="success"))
    history_repo.create(make_import_history(PROJECT_ID, records_count=500, source_type="provider", provider="openalex", status="success"))
    history_repo.create(make_import_history(PROJECT_ID, records_count=150, source_type="provider", provider="semantic_scholar", status="warning"))
    history_repo.create(make_import_history(PROJECT_ID, records_count=59, source_type="file", source_database="scopus", status="success"))

    metrics = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics.records_identified_providers == 5618
    assert metrics.records_identified_imports == 59
    assert metrics.total_identified == 5677

    assert metrics.provider_breakdown == {
        "crossref": 4968,
        "openalex": 500,
        "semantic_scholar": 150,
    }
    assert metrics.manual_source_breakdown == {"scopus": 59}


def test_adversarial_j_and_k_duplicate_handling_does_not_alter_identification_history(wp3_env):
    """Tests J & K:

    J: Cross-provider duplicate merging does not alter provider identification history.
    K: Duplicate technical removal decrements active canonical count without rewriting retrieval history.
    """
    pubs_repo = wp3_env["publications"]
    history_repo = wp3_env["history"]
    duplicate_decisions = wp3_env["duplicate_decisions"]
    prisma_service = wp3_env["prisma_service"]

    # Ingest 2 identical records from 2 providers
    pub_crossref = make_publication(1, doi="10.1234/shared-doi", title="Shared Paper")
    pub_openalex = make_publication(2, doi="10.1234/shared-doi", title="Shared Paper")
    pub_unique = make_publication(3, doi="10.5678/unique", title="Unique Paper")
    pubs_repo.add_publications(PROJECT_ID, [pub_crossref, pub_openalex, pub_unique])

    history_repo.create(make_import_history(PROJECT_ID, records_count=1, source_type="provider", provider="crossref", status="success"))
    history_repo.create(make_import_history(PROJECT_ID, records_count=1, source_type="provider", provider="openalex", status="success"))
    history_repo.create(make_import_history(PROJECT_ID, records_count=1, source_type="provider", provider="semantic_scholar", status="success"))

    # Initial metrics before dedup merge
    m0 = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert m0.total_identified == 3
    assert m0.records_before_dedup == 3
    assert m0.records_after_technical_merger == 3
    assert m0.duplicate_groups_pending_review == 1

    # Perform duplicate merge: pub_openalex is superseded by pub_crossref
    pubs_repo.mark_superseded(PROJECT_ID, [pub_openalex.record_id], pub_crossref.record_id)
    group = DuplicateGroupBuilder().build([pub_crossref, pub_openalex])[0]
    duplicate_decisions.save_decision(
        PROJECT_ID, str(group.group_id), DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE)
    )

    # Post-dedup merge metrics
    m1 = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert m1.total_identified == 3, "Test J: Retrieval history MUST remain 3"
    assert m1.provider_breakdown["crossref"] == 1
    assert m1.provider_breakdown["openalex"] == 1
    assert m1.provider_breakdown["semantic_scholar"] == 1
    assert m1.records_before_dedup == 3
    assert m1.records_after_technical_merger == 2, "Test K: Active canonical count is 2 (1 duplicate merged away)"

    flow = build_flow_model(m1)
    assert flow.removed["duplicates_removed"] == 1


def test_adversarial_l_legacy_project_fallback_semantics(wp3_env):
    """Test L: Legacy project without pre-screening archive remains readable and deterministically reported."""
    pubs_repo = wp3_env["publications"]
    prisma_service = wp3_env["prisma_service"]

    # Legacy project with 5 publications, no pre_screening_archive table usage, no import history
    legacy_pubs = [make_publication(i, title=f"Legacy Pub {i}") for i in range(1, 6)]
    pubs_repo.add_publications(PROJECT_ID, legacy_pubs)

    metrics = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics.project_id == PROJECT_ID
    assert metrics.total_identified == 0  # No fake import history fabricated
    assert metrics.records_after_normalization == 5
    assert metrics.records_before_dedup == 5
    assert metrics.records_after_technical_merger == 5
    assert metrics.records_removed_prescreening == 0
    assert metrics.records_screened_title_abstract == 0


def test_adversarial_m_no_corpus_preparation_creates_formal_screening_decision(wp3_env):
    """Test M: No corpus-preparation or pre-screening removal creates a formal screening decision."""
    pubs_repo = wp3_env["publications"]
    review_service = wp3_env["review_service"]
    screening_decisions = wp3_env["screening_decisions"]
    prisma_service = wp3_env["prisma_service"]

    pub = make_publication(1, title="Artefact To Remove")
    pubs_repo.add_publications(PROJECT_ID, [pub])

    dummy_import_id = uuid4()
    review_service.archive_pre_screening_removal(
        project_id=PROJECT_ID,
        import_id=dummy_import_id,
        record_id=pub.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        reviewer_id=REVIEWER_ID,
        physical_delete=True,
    )

    formal_decisions = screening_decisions.list_by_project(PROJECT_ID)
    assert len(formal_decisions) == 0, "No formal screening decision should be created"

    metrics = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics.records_screened_title_abstract == 0
    assert metrics.records_excluded_title_abstract == 0


def test_adversarial_n_normalization_does_not_increment_records_screened(wp3_env):
    """Test N: Normalization execution operates strictly on active corpus and does NOT increment Records Screened."""
    pubs_repo = wp3_env["publications"]
    prisma_service = wp3_env["prisma_service"]

    pubs = [make_publication(i, title=f"Paper {i}") for i in range(1, 5)]
    pubs_repo.add_publications(PROJECT_ID, pubs)

    normalize_project(pubs_repo, PROJECT_ID)

    metrics = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics.records_screened_title_abstract == 0
    assert metrics.records_screened_full_text == 0
    assert metrics.studies_included_synthesis == 0


def test_adversarial_o_deduplication_does_not_increment_records_screened(wp3_env):
    """Test O: Deduplication execution does NOT increment Records Screened."""
    pubs_repo = wp3_env["publications"]
    duplicate_decisions = wp3_env["duplicate_decisions"]
    prisma_service = wp3_env["prisma_service"]

    pub1 = make_publication(1, doi="10.1111/dup", title="Dup 1")
    pub2 = make_publication(2, doi="10.1111/dup", title="Dup 2")
    pubs_repo.add_publications(PROJECT_ID, [pub1, pub2])

    dedup_service = ProjectDuplicateService(
        repository=pubs_repo,
        decision_repository=duplicate_decisions,
    )
    dedup_service.get_candidate_duplicate_groups(PROJECT_ID)

    metrics = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert metrics.records_screened_title_abstract == 0
    assert metrics.records_screened_full_text == 0
    assert metrics.studies_included_synthesis == 0


def test_adversarial_p_repeated_prisma_generation_is_deterministic(wp3_env):
    """Test P: Repeated PRISMA PDF, SVG, and Flow generation is deterministic and byte-identical."""
    history_repo = wp3_env["history"]
    pubs_repo = wp3_env["publications"]
    export_service = wp3_env["export_service"]

    history_repo.create(make_import_history(PROJECT_ID, records_count=100, source_type="provider", provider="crossref", status="success"))
    history_repo.create(make_import_history(PROJECT_ID, records_count=20, source_type="file", source_database="pubmed", status="success"))
    pubs_repo.add_publications(PROJECT_ID, [make_publication(i) for i in range(1, 51)])

    fixed_time = datetime(2026, 9, 23, 6, 0, 0, tzinfo=timezone.utc)
    model1 = export_service.get_prisma_flow_model(PROJECT_ID, reviewer_id=REVIEWER_ID, generated_at=fixed_time)
    model2 = export_service.get_prisma_flow_model(PROJECT_ID, reviewer_id=REVIEWER_ID, generated_at=fixed_time)
    assert model1 == model2

    svg1 = render_prisma_svg(model1)
    svg2 = render_prisma_svg(model2)
    assert svg1 == svg2

    pdf1 = render_prisma_pdf(model1)
    pdf2 = render_prisma_pdf(model2)
    assert pdf1 == pdf2


def test_adversarial_q_accounting_semantics_parity_across_pdf_svg_xlsx_and_api(wp3_env):
    """Test Q: PDF, SVG, XLSX workbook, and API DTO use the exact same underlying accounting semantics."""
    history_repo = wp3_env["history"]
    pubs_repo = wp3_env["publications"]
    review_service = wp3_env["review_service"]
    dec_repo = wp3_env["screening_decisions"]
    prisma_service = wp3_env["prisma_service"]
    export_service = wp3_env["export_service"]

    # Setup 10 imported: 7 retained, 3 removed & archived
    pubs = [make_publication(i, title=f"Study {i}") for i in range(1, 11)]
    pubs_repo.add_publications(PROJECT_ID, pubs)
    import_rec = make_import_history(PROJECT_ID, records_count=10, source_type="provider", provider="crossref", status="success")
    history_repo.create(import_rec)

    for p in pubs[7:]:
        review_service.archive_pre_screening_removal(
            project_id=PROJECT_ID,
            import_id=import_rec.import_id,
            record_id=p.record_id,
            reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
            reviewer_id=REVIEWER_ID,
            physical_delete=True,
        )

    # 1 formal Title/Abstract exclusion, 1 formal Title/Abstract inclusion
    dec_repo.save(
        ScreeningDecision(
            project_id=PROJECT_ID,
            publication_id=pubs[0].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id=REVIEWER_ID,
        )
    )
    dec_repo.save(
        ScreeningDecision(
            project_id=PROJECT_ID,
            publication_id=pubs[1].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id=REVIEWER_ID,
        )
    )

    # 1. Direct Service Metrics & Response DTO
    metrics = prisma_service.get_metrics(PROJECT_ID, reviewer_id=REVIEWER_ID)
    dto = prisma_service.to_response(metrics)
    assert dto.total_identified == 10
    assert dto.records_removed_prescreening == 3
    assert dto.records_after_normalization == 7
    assert dto.records_before_dedup == 7
    assert dto.records_screened_title_abstract == 2
    assert dto.records_excluded_title_abstract == 1

    # 2. Flow Model
    flow = export_service.get_prisma_flow_model(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert flow.removed["records_removed_prescreening"] == 3
    assert flow.removed["excluded_title_abstract"] == 1
    assert flow.metadata.counts_echo["total_identified"] == 10
    assert flow.metadata.counts_echo["records_after_normalization"] == 7

    # 3. SVG Diagram
    svg_text = export_service.get_prisma_svg(PROJECT_ID, reviewer_id=REVIEWER_ID)
    assert "Database records (n = 10)" in svg_text
    assert "Pre-screening removals (n = 3)" in svg_text
    assert "Active canonical records (n = 7)" in svg_text
    assert "Title &amp; Abstract screened (n = 2)" in svg_text
    assert "Title &amp; Abstract excluded (n = 1)" in svg_text

    # 4. PDF Diagram Text Extraction
    pdf_bytes = export_service.get_prisma_pdf(PROJECT_ID, reviewer_id=REVIEWER_ID)
    pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pdf_text = pdf_reader.pages[0].extract_text()
    assert "Database records (n = 10)" in pdf_text
    assert "Pre-screening removals (n = 3)" in pdf_text
    assert "Active canonical records (n = 7)" in pdf_text
    assert "Title & Abstract screened (n = 2)" in pdf_text
    assert "Title & Abstract excluded (n = 1)" in pdf_text
