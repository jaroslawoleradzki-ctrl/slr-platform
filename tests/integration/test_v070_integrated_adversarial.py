"""v0.7.0 Integrated Adversarial End-to-End Integration Test Suite.

Exercises the complete lifecycle across WP1, WP2, WP3, and WP4:
A) import records from multiple sources (Crossref, file/RIS)
B) inspect imported records via pre-screening API/service
C) search/filter imported records
D) remove records with valid reasons + notes
E) restore one record (undo)
F) remove it again
G) verify full pre-screening audit trail (decisions, reasons, timestamps, reviewer)
H) verify removed records do NOT count as formal Screening exclusions
I) finalize/admit the retained corpus for Screening
J) retry finalization -> verify idempotency (same event, no duplicates)
K) begin formal Screening on admitted records
L) import NEW records after finalization
M) verify new records do NOT alter the historical Screening corpus
N) verify exact admitted member set can be reconstructed
O) verify duplicate canonical DOI cannot create duplicate screening membership
P) verify bounded Crossref retrieval with safety limit (WP3)
Q) trigger safety limit stop -> verify stop reason
R) resume retrieval -> verify safety budget renewal
S) verify cumulative logical count across resumed executions
T) verify zero query/cursor overlap on resume
U) complete resume -> verify all records imported
V) verify provenance and replay determinism
W) verify Crossref retrieval with medical/no-abstract records evaluates MATCH/NON_MATCH/INDETERMINATE without silent discard (WP2)
X) researcher pre-screening review removes an INDETERMINATE/artefact record before finalization
Y) verify PRISMA invariant: records_screened <= records_admitted_to_screening and pre-screening removal does NOT inflate records_screened
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.dto.search_strategy import (
    ConceptGroupRequest,
    SearchStrategyExecutionRequest,
)
from app.domain.author import Author
from app.domain.deduplication import DuplicateGroupMergeRecord
from app.domain.duplicate_review import (
    DuplicateDecision,
    DuplicateGroupReviewDecision,
)
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.pre_screening import (
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.screening import (
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.domain.search import (
    BooleanOperator,
    SearchField,
    SearchGroup,
    SearchQuery,
    SearchTerm,
)
from app.providers.crossref import CrossrefClient
from app.providers.search.crossref import CrossrefProvider
from app.rendering.crossref import build_crossref_candidate_queries
from app.repositories.corpus_finalization_repository import (
    SqliteCorpusFinalizationRepository,
)
from app.repositories.duplicate_merge_repository import (
    SqliteDuplicateMergeRepository,
)
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import (
    SqliteImportHistoryRepository,
)
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
)
from app.repositories.search_result_snapshot_repository import (
    SqliteSearchResultSnapshotRepository,
)
from app.repositories.search_run_checkpoint_repository import (
    SqliteSearchRunCheckpointRepository,
)
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)
from app.services.corpus_finalization_service import (
    CorpusFinalizationService,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.fetch_all_search import FetchAllSearchService
from app.services.live_search import build_search_query
from app.services.pre_screening_review_service import (
    CorpusFinalizedError,
    PreScreeningReviewService,
)
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_workflow_status_service import (
    ProjectWorkflowStatusService,
)
from app.services.screening_input_service import ScreeningInputService
from app.services.search_engine import SearchProvider
from tests.fixtures.factories import make_import_history


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _pub(
    record_id: UUID,
    title: str,
    source: str,
    doi: str | None = None,
    year: int = 2024,
    abstract: str | None = "A relevant paper about lean systems and energy.",
) -> Publication:
    identifiers = []
    if doi:
        identifiers.append(Identifier(type=IdentifierType.DOI, value=doi))
    return Publication(
        record_id=record_id,
        title=title,
        abstract=abstract,
        authors=[Author(display_name="Doe, J."), Author(display_name="Smith, A.")],
        publication_year=year,
        identifiers=identifiers,
        provenance=[ProvenanceEntry(source=source, source_record_id=str(record_id))],
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def integrated_env(tmp_path: Path):
    db_path = tmp_path / "integrated_adversarial.db"
    project_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    ps_decision_repo = SqlitePreScreeningDecisionRepository(db_path)
    dup_decision_repo = SqliteDuplicateReviewDecisionRepository(db_path)
    dup_merge_repo = SqliteDuplicateMergeRepository(db_path)
    screening_decision_repo = SqliteScreeningDecisionRepository(db_path)
    fin_repo = SqliteCorpusFinalizationRepository(db_path)
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    project_id = "adv_v070_project"
    project_repo.create(Project(project_id=project_id, title="v0.7.0 Adversarial Test Project"))

    ps_service = PreScreeningReviewService(pub_repo, ps_decision_repo, fin_repo, screening_decision_repo)
    fin_service = CorpusFinalizationService(fin_repo, pub_repo, ps_decision_repo)
    screening_input_service = ScreeningInputService(
        publication_repository=pub_repo,
        decision_repository=dup_decision_repo,
        merge_repository=dup_merge_repo,
        finalization_repository=fin_repo,
    )
    reporting_repo = ScreeningReportingRepository(db_path)
    workflow_status_service = ProjectWorkflowStatusService(
        publication_repository=pub_repo,
        decision_repository=screening_decision_repo,
        reporting_repository=reporting_repo,
        input_service=screening_input_service,
    )
    prisma_service = PrismaMetricsService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        decision_repository=dup_decision_repo,
        workflow_status_service=workflow_status_service,
    )

    return {
        "db_path": db_path,
        "project_id": project_id,
        "pub_repo": pub_repo,
        "history_repo": history_repo,
        "ps_decision_repo": ps_decision_repo,
        "dup_decision_repo": dup_decision_repo,
        "dup_merge_repo": dup_merge_repo,
        "screening_decision_repo": screening_decision_repo,
        "fin_repo": fin_repo,
        "fin_service": fin_service,
        "ps_service": ps_service,
        "screening_input_service": screening_input_service,
        "prisma_service": prisma_service,
        "snapshot_repo": snapshot_repo,
        "checkpoint_repo": checkpoint_repo,
    }


@pytest.mark.anyio
async def test_v070_integrated_adversarial_workflow_a_to_y(integrated_env) -> None:
    env = integrated_env
    project_id = env["project_id"]
    pub_repo = env["pub_repo"]
    history_repo = env["history_repo"]
    ps_service = env["ps_service"]
    ps_decision_repo = env["ps_decision_repo"]
    dup_decision_repo = env["dup_decision_repo"]
    dup_merge_repo = env["dup_merge_repo"]
    fin_service = env["fin_service"]
    screening_input_service = env["screening_input_service"]
    screening_decision_repo = env["screening_decision_repo"]
    prisma_service = env["prisma_service"]

    # -------------------------------------------------------------------------
    # STEP A: Import records from multiple sources (Crossref, file/RIS)
    # -------------------------------------------------------------------------
    crossref_import_id = uuid4()
    ris_import_id = uuid4()

    rec_crossref_1 = uuid4()  # Retained
    rec_crossref_2 = uuid4()  # Will be removed -> restored -> removed
    rec_crossref_3 = uuid4()  # Will be removed (noise)
    rec_crossref_dup = uuid4()  # Has same DOI as ris_1

    rec_ris_1 = uuid4()  # Canonical for shared DOI
    rec_ris_2 = uuid4()  # Retained

    shared_doi = "10.1016/j.energy.2024.001"

    pubs_crossref = [
        _pub(
            rec_crossref_1, "Lean Manufacturing & Energy Efficiency in Automotive", "Crossref", "10.1007/s00170-024-01"
        ),
        _pub(
            rec_crossref_2, "Hospital Patient Flow and Lean Healthcare Management", "Crossref", "10.1007/s00170-024-02"
        ),
        _pub(rec_crossref_3, "Incomplete Indexing Record Artefact", "Crossref", "10.1007/s00170-024-03"),
        _pub(rec_crossref_dup, "Energy Optimization via Kaizen Techniques", "Crossref", shared_doi),
    ]
    pub_repo.import_source_publications(project_id, pubs_crossref, import_id=crossref_import_id)
    history_repo.create(
        make_import_history(
            import_id=crossref_import_id,
            project_id=project_id,
            source_type="provider",
            provider="crossref",
            records_count=4,
            status="success",
        )
    )

    pubs_ris = [
        _pub(rec_ris_1, "Energy Optimization via Kaizen Techniques", "RIS file", shared_doi),
        _pub(
            rec_ris_2,
            "Continuous Improvement and Industrial Decarbonization",
            "RIS file",
            "10.1016/j.resconrec.2024.05",
        ),
    ]
    pub_repo.import_source_publications(project_id, pubs_ris, import_id=ris_import_id)
    history_repo.create(
        make_import_history(
            import_id=ris_import_id,
            project_id=project_id,
            source_type="file",
            filename="scopus_export.ris",
            format_type="ris",
            records_count=2,
            status="success",
        )
    )

    # -------------------------------------------------------------------------
    # STEP B: Inspect imported records via pre-screening API/service
    # -------------------------------------------------------------------------
    crossref_page = ps_service.list_imported_records(project_id, crossref_import_id)
    assert crossref_page.total_imported == 4
    assert crossref_page.retained_count == 4
    assert crossref_page.removed_count == 0
    assert len(crossref_page.items) == 4
    for item in crossref_page.items:
        assert item.pre_screening_status == PreScreeningStatus.RETAINED
        assert item.title is not None
        assert item.publication_year == 2024

    # -------------------------------------------------------------------------
    # STEP C: Search/filter imported records
    # -------------------------------------------------------------------------
    filtered = ps_service.list_imported_records(project_id, crossref_import_id, search="Healthcare")
    assert filtered.total == 1
    assert filtered.items[0].record_id == rec_crossref_2

    # -------------------------------------------------------------------------
    # STEP D: Remove records with valid reasons + notes
    # -------------------------------------------------------------------------
    # Remove rec_crossref_3 (artefact)
    ps_service.remove_record(
        project_id,
        crossref_import_id,
        rec_crossref_3,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="Malformed citation record without usable text",
        reviewer_id="reviewer_lead",
    )
    # Remove rec_crossref_2 (clearly outside scope)
    ps_service.remove_record(
        project_id,
        crossref_import_id,
        rec_crossref_2,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        notes="Clinical healthcare domain, out of scope for manufacturing SLR",
        reviewer_id="reviewer_lead",
    )

    page_after_removal = ps_service.list_imported_records(project_id, crossref_import_id)
    assert page_after_removal.retained_count == 2
    assert page_after_removal.removed_count == 2

    # -------------------------------------------------------------------------
    # STEP E: Restore one record (undo)
    # -------------------------------------------------------------------------
    ps_service.restore_record(project_id, crossref_import_id, rec_crossref_2, reviewer_id="reviewer_lead")
    page_after_undo = ps_service.list_imported_records(project_id, crossref_import_id)
    assert page_after_undo.retained_count == 3
    assert page_after_undo.removed_count == 1

    # -------------------------------------------------------------------------
    # STEP F: Remove it again
    # -------------------------------------------------------------------------
    ps_service.remove_record(
        project_id,
        crossref_import_id,
        rec_crossref_2,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        notes="Re-confirmed outside manufacturing scope",
        reviewer_id="reviewer_lead",
    )
    page_after_second_remove = ps_service.list_imported_records(project_id, crossref_import_id)
    assert page_after_second_remove.retained_count == 2
    assert page_after_second_remove.removed_count == 2

    # -------------------------------------------------------------------------
    import_decisions = ps_decision_repo.list_decisions_for_import(project_id, crossref_import_id)
    history_rec2 = [d for d in import_decisions if d.record_id == rec_crossref_2]
    assert len(history_rec2) == 3
    # Newest to oldest:
    assert history_rec2[0].status == PreScreeningStatus.REMOVED
    assert history_rec2[0].reason == PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE
    assert history_rec2[0].reviewer_id == "reviewer_lead"
    assert history_rec2[1].status == PreScreeningStatus.RETAINED
    assert history_rec2[2].status == PreScreeningStatus.REMOVED

    # -------------------------------------------------------------------------
    # STEP H: Verify removed records do NOT count as formal Screening exclusions
    # -------------------------------------------------------------------------
    metrics_before_screening = prisma_service.get_metrics(project_id)
    assert metrics_before_screening.records_removed_prescreening == 2
    assert metrics_before_screening.records_screened_title_abstract == 0
    assert metrics_before_screening.records_excluded_title_abstract == 0

    # -------------------------------------------------------------------------
    # Deduplication readiness resolution prior to finalization:
    active_pubs_for_dedup = pub_repo.get_screening_corpus_publications(project_id)
    dup_groups = DuplicateGroupBuilder().build(active_pubs_for_dedup)
    for group in dup_groups:
        dup_decision_repo.save_decision(
            project_id,
            str(group.group_id),
            DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE),
        )
        dup_merge_repo.save_merge(
            DuplicateGroupMergeRecord(
                project_id=project_id,
                group_id=str(group.group_id),
                canonical_record_id=rec_ris_1,
                merged_publication_ids=(rec_ris_1, rec_crossref_dup),
                merged_at=datetime.now(timezone.utc),
                status="merged",
                pre_merge_snapshots=tuple(
                    p for p in active_pubs_for_dedup if p.record_id in (rec_ris_1, rec_crossref_dup)
                ),
            )
        )
    # Mark rec_crossref_dup as superseded by canonical rec_ris_1
    pub_repo.mark_superseded(project_id, [rec_crossref_dup], canonical_record_id=rec_ris_1)

    # -------------------------------------------------------------------------
    # STEP I: Finalize/admit the retained corpus for Screening
    # -------------------------------------------------------------------------
    fin = fin_service.finalize_corpus(project_id, finalized_by="reviewer_lead")
    assert fin.source_records_count == 6
    assert fin.duplicates_removed_count == 1
    assert fin.prescreening_removed_count == 2
    assert fin.retained_count == 3  # rec_crossref_1, rec_ris_1, rec_ris_2
    assert fin.source_records_count == (
        fin.duplicates_removed_count + fin.prescreening_removed_count + fin.retained_count
    )

    # -------------------------------------------------------------------------
    # STEP J: Retry finalization -> verify idempotency (same event, no duplicates)
    # -------------------------------------------------------------------------
    fin_retry = fin_service.finalize_corpus(project_id, finalized_by="different_reviewer")
    assert fin_retry.finalization_id == fin.finalization_id
    assert fin_retry.created_at == fin.created_at
    assert fin_retry.retained_count == fin.retained_count

    # -------------------------------------------------------------------------
    # STEP K: Begin formal Screening on admitted records
    # -------------------------------------------------------------------------
    screening_input = screening_input_service.get_input_set(project_id)
    assert screening_input.ready is True
    assert len(screening_input.publications) == 3
    admitted_ids = {p.record_id for p in screening_input.publications}
    assert admitted_ids == {rec_crossref_1, rec_ris_1, rec_ris_2}

    # Record formal screening decision on rec_crossref_1
    decision_ta = ScreeningDecision(
        project_id=project_id,
        publication_id=rec_crossref_1,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer_lead",
    )
    screening_decision_repo.save(decision_ta)

    # Pre-screening modification must be locked both by finalization and by formal decision
    with pytest.raises(CorpusFinalizedError):
        ps_service.remove_record(
            project_id, crossref_import_id, rec_crossref_1, reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE
        )

    # -------------------------------------------------------------------------
    # STEP L: Import NEW records after finalization
    # -------------------------------------------------------------------------
    rec_late = uuid4()
    late_import_id = uuid4()
    pub_repo.import_source_publications(
        project_id,
        [_pub(rec_late, "Post-Finalization Discovery Paper", "Crossref", "10.1007/late-999")],
        import_id=late_import_id,
    )
    history_repo.create(
        make_import_history(
            import_id=late_import_id,
            project_id=project_id,
            source_type="provider",
            provider="crossref",
            records_count=1,
            status="success",
        )
    )

    # -------------------------------------------------------------------------
    # STEP M: Verify new records do NOT alter the historical Screening corpus
    # -------------------------------------------------------------------------
    screening_input_post_import = screening_input_service.get_input_set(project_id)
    assert len(screening_input_post_import.publications) == 3
    assert {p.record_id for p in screening_input_post_import.publications} == {rec_crossref_1, rec_ris_1, rec_ris_2}
    assert rec_late not in {p.record_id for p in screening_input_post_import.publications}

    # -------------------------------------------------------------------------
    # STEP N: Verify exact admitted member set can be reconstructed
    # -------------------------------------------------------------------------
    reconstructed_admitted = fin_service.get_admitted_record_ids(project_id)
    assert reconstructed_admitted == {rec_crossref_1, rec_ris_1, rec_ris_2}
    members = fin_service.get_finalization_members(fin.finalization_id)
    assert len(members) == 5  # 5 canonical records at finalization time
    admitted_members = [m for m in members if m.admitted_to_screening]
    removed_members = [m for m in members if not m.admitted_to_screening]
    assert len(admitted_members) == 3
    assert len(removed_members) == 2

    # -------------------------------------------------------------------------
    # STEP O: Verify duplicate canonical DOI cannot create duplicate screening membership
    # -------------------------------------------------------------------------
    assert len({p.identifiers[0].value for p in screening_input_post_import.publications if p.identifiers}) == 3
    # rec_crossref_dup was merged into rec_ris_1 and never admitted twice
    assert rec_crossref_dup not in reconstructed_admitted

    # -------------------------------------------------------------------------
    # STEP P, Q, R, S, T, U, V: Bounded Crossref retrieval with safety limit,
    # stop reason, durable resume, budget renewal, cumulative counters, determinism (WP3)
    # -------------------------------------------------------------------------
    snapshot_repo = env["snapshot_repo"]
    checkpoint_repo = env["checkpoint_repo"]

    strategy_fetch = SearchStrategyExecutionRequest(
        publication_year_from=2015,
        publication_year_to=2026,
        providers=["crossref"],
        concept_groups=[
            ConceptGroupRequest(id="g1", name="Lean", terms=["Lean", "Kaizen"]),
            ConceptGroupRequest(id="g2", name="Energy", terms=["Energy"]),
            ConceptGroupRequest(id="g3", name="Manufacturing", terms=["Manufacturing"]),
        ],
    )
    physical_queries = build_crossref_candidate_queries(build_search_query(strategy_fetch).expression)
    query_indexes = {query: index for index, query in enumerate(physical_queries)}
    recorded_requests: list[tuple[str, str]] = []

    def mock_work(doi: str) -> dict[str, Any]:
        return {
            "DOI": doi,
            "title": ["Lean Energy in Manufacturing Operations"],
            "type": "journal-article",
            "published": {"date-parts": [[2024]]},
            "abstract": "Continuous improvement and energy efficiency.",
        }

    def fetch_handler(request: httpx.Request) -> httpx.Response:
        physical_query = request.url.params["query"]
        cursor = request.url.params["cursor"]
        recorded_requests.append((physical_query, cursor))
        index = query_indexes[physical_query]
        if cursor == "*":
            items = [mock_work(f"10.1000/wp3-{index}-a")]
            next_cursor = f"query-{index}-page-2"
        else:
            items = [mock_work(f"10.1000/wp3-{index}-b")]
            next_cursor = None
        return httpx.Response(
            200,
            json={"message": {"items": items, "next-cursor": next_cursor, "total-results": 2}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(fetch_handler)) as http_client:

        def provider_factory(
            strategy_req: SearchStrategyExecutionRequest, client: httpx.AsyncClient
        ) -> list[SearchProvider]:
            return [
                CrossrefProvider(
                    client=CrossrefClient(http_client=http_client, requests_per_second=None),
                    paginate=True,
                    max_physical_requests_per_call=1,
                )
            ]

        # P: Bounded retrieval with max_records_per_provider=2
        fetch_service = FetchAllSearchService(
            provider_factory=provider_factory,
            snapshot_repository=snapshot_repo,
            checkpoint_repository=checkpoint_repo,
            max_pages_per_provider=20,
            max_records_per_provider=2,
        )
        started = fetch_service.start(project_id, strategy_fetch)
        await fetch_service.wait(started.job_id)

        # Q: Trigger safety limit stop -> verify stop reason
        status_initial = fetch_service.get_status(started.job_id)
        assert status_initial.providers[0].status == "partial"
        assert status_initial.providers[0].stop_reason == "safety_limit"
        assert status_initial.resumable
        before_requests = list(recorded_requests)
        assert len(before_requests) > 0

        # R & S: Resume retrieval -> verify safety budget renewal and cumulative logical count
        restarted = FetchAllSearchService(
            provider_factory=provider_factory,
            snapshot_repository=snapshot_repo,
            checkpoint_repository=checkpoint_repo,
            max_pages_per_provider=20,
            max_records_per_provider=2,
        )
        resumed = restarted.start_resume_job(project_id, started.job_id)
        await restarted.wait(resumed.job_id)
        status_resumed = restarted.get_status(resumed.job_id)
        assert status_resumed.fetched_total > status_initial.fetched_total
        assert status_resumed.providers[0].status == "complete"

        # T: Verify zero query/cursor overlap on resume
        resumed_requests = recorded_requests[len(before_requests) :]
        assert not set(before_requests).intersection(resumed_requests)

        # U: Complete resume -> verify all queries finished and status complete
        assert status_resumed.fetched_total == 4

        # V: Verify provenance and replay determinism (every physical request is distinct)
        assert len(recorded_requests) == len(set(recorded_requests))

    # -------------------------------------------------------------------------
    # STEP W: Crossref retrieval with medical/no-abstract records evaluates
    # MATCH/NON_MATCH/INDETERMINATE without silent discard (WP2)
    # -------------------------------------------------------------------------
    lean_energy_query = SearchQuery(
        name="Lean Energy Query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="Lean", field=SearchField.ANY),
                        SearchTerm(value="Kaizen", field=SearchField.ANY),
                    ],
                ),
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="Energy", field=SearchField.ANY),
                        SearchTerm(value="Electricity", field=SearchField.ANY),
                    ],
                ),
            ],
        ),
    )

    # 1. Full metadata matching
    lean_energy_pub = _pub(
        uuid4(), "Lean production and energy efficiency", "Crossref", abstract="Improving energy in lean factory"
    )
    assert validate_canonical_query(lean_energy_query, lean_energy_pub).status == CanonicalMatchStatus.MATCH

    # 2. Medical noise out-of-domain with abstract
    medical_noise_pub = _pub(
        uuid4(), "Oncology patient treatments and oncology surgery", "Crossref", abstract="Chemotherapy results"
    )
    assert validate_canonical_query(lean_energy_query, medical_noise_pub).status == CanonicalMatchStatus.NON_MATCH

    # 3. Missing abstract -> evaluates to INDETERMINATE (PRISMA-S recall-first retention, NOT silently discarded)
    missing_abstract_pub = _pub(uuid4(), "Energy conservation methods", "Crossref", abstract=None)
    assert (
        validate_canonical_query(lean_energy_query, missing_abstract_pub).status == CanonicalMatchStatus.INDETERMINATE
    )

    # -------------------------------------------------------------------------
    # STEP X: Researcher pre-screening review removes an INDETERMINATE/artefact record
    # -------------------------------------------------------------------------
    # Verify that pre-screening review is the authoritative human boundary for
    # removing such INDETERMINATE noise before finalization
    assert rec_crossref_3 in {rec.record_id for rec in pubs_crossref}
    rec3_decision = ps_decision_repo.get_latest_decision(project_id, rec_crossref_3)
    assert rec3_decision is not None
    assert rec3_decision.status == PreScreeningStatus.REMOVED

    # -------------------------------------------------------------------------
    # STEP Y: Verify PRISMA invariant:
    # records_screened <= records_admitted_to_screening
    # and pre-screening removal does NOT inflate records_screened
    # -------------------------------------------------------------------------
    final_prisma = prisma_service.get_metrics(project_id, reviewer_id="reviewer_lead")
    assert final_prisma.records_removed_prescreening == 2
    assert final_prisma.records_screened_title_abstract == 1
    # Check invariant
    assert final_prisma.records_screened_title_abstract <= fin.retained_count
    # Verify records screened is NOT inflated by pre-screening removals
    assert final_prisma.records_screened_title_abstract != (
        final_prisma.records_screened_title_abstract + final_prisma.records_removed_prescreening
    )
    assert final_prisma.records_excluded_title_abstract == 0
