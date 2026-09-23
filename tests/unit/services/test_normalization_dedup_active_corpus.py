"""WP2 adversarial tests: Normalization + Deduplication consume the Active Corpus.

Synthetic fixtures mirror the production defect shape (retained vs
pre-screening removed populations, cross-provider DOI sharing) without
hardcoding production values or touching production data.

Requirement map:
  A. 10 pubs (7 retained / 3 removed) -> normalization processes exactly 7.
  B. Normalization rerun still processes exactly 7.
  C. Removed records produce no active canonical output (docs untouched).
  D. Deduplication receives exactly the normalized Active Corpus.
  E. Removed record sharing a DOI with a retained record -> no duplicate pair.
  F. Two retained cross-provider records sharing a DOI -> duplicate detected.
  G. Removed record sharing a normalized title -> no duplicate candidate.
  H. retained -> removed before rebuild disappears from derived state.
  I. No provider-specific logic (Crossref/OpenAlex/Semantic Scholar uniform).
  J. Legacy project without pre-screening decisions remains compatible.
  K. Finalized corpus protections remain intact.
  L. Normalization reported count equals actual active input count.
  M. Deduplication counts/groups contain no removed records.
  N. Repeated rebuild is deterministic/idempotent.
  O. No formal screening decision is created by rebuild/reconciliation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.pre_screening import PreScreeningRemovalReason
from app.domain.project import Project
from app.repositories.corpus_finalization_repository import (
    SqliteCorpusFinalizationRepository,
)
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.pre_screening_archive_repository import (
    SqlitePreScreeningArchiveRepository,
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
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.corpus_derived_state_service import CorpusDerivedStateService
from app.services.corpus_finalization_service import CorpusFinalizationService
from app.services.normalization_service import normalize_project
from app.services.pre_screening_review_service import (
    CorpusFinalizedError,
    PreScreeningReviewService,
)
from app.services.project_duplicate_service import ProjectDuplicateService
from tests.fixtures.factories import make_publication

SHARED_DOI = "10.1000/shared-study"
PROJECT_ID = "wp2-adversarial"


@pytest.fixture
def stores(tmp_path: Path):
    db_path = tmp_path / "wp2.db"
    SqliteProjectRepository(db_path).create(Project(project_id=PROJECT_ID, title="WP2"))
    pubs = SqliteProjectPublicationRepository(db_path)
    decisions = SqliteDuplicateReviewDecisionRepository(db_path)
    merges = SqliteDuplicateMergeRepository(db_path)
    executions = SqliteNormalizationExecutionRepository(db_path)
    ps_decisions = SqlitePreScreeningDecisionRepository(db_path)
    archive = SqlitePreScreeningArchiveRepository(db_path)
    screening = SqliteScreeningDecisionRepository(db_path)
    finalizations = SqliteCorpusFinalizationRepository(db_path)
    review = PreScreeningReviewService(
        publication_repository=pubs,
        decision_repository=ps_decisions,
        archive_repository=archive,
        screening_decision_repository=screening,
    )
    duplicates = ProjectDuplicateService(
        pubs,
        decisions,
        merge_repository=merges,
        transaction_manager=SqliteTransactionManager(db_path),
    )
    rebuild_service = CorpusDerivedStateService(
        publication_repository=pubs,
        normalization_execution_repository=executions,
        duplicate_service=duplicates,
        finalization_repository=finalizations,
    )
    finalization_service = CorpusFinalizationService(
        finalization_repository=finalizations,
        publication_repository=pubs,
        decision_repository=ps_decisions,
    )
    return {
        "db_path": db_path,
        "pubs": pubs,
        "decisions": decisions,
        "merges": merges,
        "executions": executions,
        "review": review,
        "duplicates": duplicates,
        "rebuild": rebuild_service,
        "finalizations": finalization_service,
    }


def _seed_ten_publications(stores) -> dict[str, UUID]:
    """Seed 7 retained + 3 removed publications across providers."""
    pubs = stores["pubs"]
    review = stores["review"]
    import_id = uuid4()
    retained = [
        make_publication(index=1, title="Crossref retained alpha", doi=SHARED_DOI, source="Crossref", source_id="CR-1"),
        make_publication(index=2, title="OpenAlex retained alpha", doi=SHARED_DOI, source="OpenAlex", source_id="W2"),
        make_publication(index=3, title="Identical Study Title", doi="10.1000/semantic-unique", source="Semantic Scholar", source_id="S2-3"),
        make_publication(index=4, title="Crossref retained beta", doi="10.1000/crossref-beta", source="Crossref", source_id="CR-4"),
        make_publication(index=5, title="OpenAlex retained beta", doi="10.1000/openalex-beta", source="OpenAlex", source_id="W5"),
        make_publication(index=6, title="RIS retained one", doi="10.1000/ris-one", source="RIS file (manual export)", source_id="IMP-6"),
        make_publication(index=7, title="RIS retained two", doi="10.1000/ris-two", source="RIS file (manual export)", source_id="IMP-7"),
    ]
    removed = [
        make_publication(index=8, title="Crossref removed sharing DOI", doi=SHARED_DOI, source="Crossref", source_id="CR-8"),
        make_publication(index=9, title="Identical Study Title", doi="10.1000/openalex-removed", source="OpenAlex", source_id="W9"),
        make_publication(index=10, title="Semantic Scholar removed", doi="10.1000/semantic-removed", source="Semantic Scholar", source_id="S2-10"),
    ]
    pubs.import_source_publications(PROJECT_ID, [*retained, *removed], import_id=import_id)
    for publication in removed:
        review.remove_record(
            PROJECT_ID,
            import_id,
            publication.record_id,
            reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        )
    return {
        "import_id": import_id,
        "retained": [p.record_id for p in retained],
        "removed": [p.record_id for p in removed],
    }


def _screening_decision_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM screening_decisions WHERE project_id = ?", (PROJECT_ID,)
        ).fetchone()
    return int(row[0])


def test_a_normalization_processes_exactly_active_corpus(stores) -> None:
    ids = _seed_ten_publications(stores)
    execution = normalize_project(stores["pubs"], PROJECT_ID)
    assert execution.processed_records == 7
    assert execution.clean_records == 7
    assert stores["pubs"].count_active_by_project(PROJECT_ID) == 7
    assert stores["pubs"].count_by_project(PROJECT_ID) == 10
    assert set(ids["retained"]) == {p.record_id for p in stores["pubs"].get_active_publications(PROJECT_ID)}


def test_b_normalization_rerun_processes_exactly_active_corpus(stores) -> None:
    _seed_ten_publications(stores)
    first = normalize_project(stores["pubs"], PROJECT_ID)
    second = normalize_project(stores["pubs"], PROJECT_ID)
    assert (first.processed_records, first.clean_records) == (7, 7)
    assert (second.processed_records, second.clean_records) == (7, 7)
    assert stores["pubs"].count_by_project(PROJECT_ID) == 10


def test_c_removed_records_produce_no_active_canonical_output(stores) -> None:
    ids = _seed_ten_publications(stores)
    before = {p.record_id: p for p in stores["pubs"].get_publications(PROJECT_ID)}
    normalize_project(stores["pubs"], PROJECT_ID)
    after = {p.record_id: p for p in stores["pubs"].get_publications(PROJECT_ID)}
    for record_id in ids["removed"]:
        assert before[record_id] == after[record_id]
    active_ids = {p.record_id for p in stores["pubs"].get_active_publications(PROJECT_ID)}
    assert not (set(ids["removed"]) & active_ids)


def test_d_deduplication_receives_normalized_active_corpus(stores) -> None:
    ids = _seed_ten_publications(stores)
    normalize_project(stores["pubs"], PROJECT_ID)
    response = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    member_ids = {record.id for group in response.groups for record in group.records}
    assert member_ids <= set(str(record_id) for record_id in ids["retained"])
    assert response.total_groups_count == 1
    pair = next(iter(response.groups))
    assert {record.id for record in pair.records} == {str(ids["retained"][0]), str(ids["retained"][1])}
    # Deduplication consumed post-normalization state: canonical titles present.
    repo_titles = {p.record_id: p.title_normalized for p in stores["pubs"].get_active_publications(PROJECT_ID)}
    assert all(repo_titles[UUID(record.id)] for record in pair.records)


def test_e_removed_doi_sharing_record_creates_no_duplicate_pair(stores) -> None:
    ids = _seed_ten_publications(stores)
    response = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    removed_doi_holder = str(ids["removed"][0])
    for group in response.groups:
        assert removed_doi_holder not in {record.id for record in group.records}


def test_f_cross_provider_retained_duplicates_still_detected(stores) -> None:
    ids = _seed_ten_publications(stores)
    response = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    assert response.total_groups_count == 1
    group = response.groups[0]
    assert {record.id for record in group.records} == {str(ids["retained"][0]), str(ids["retained"][1])}
    sources = {record.source for record in group.records}
    assert sources == {"Crossref", "OpenAlex"}


def test_g_removed_title_sharing_record_creates_no_candidate(stores) -> None:
    ids = _seed_ten_publications(stores)
    response = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    removed_title_holder = str(ids["removed"][1])
    for group in response.groups:
        assert removed_title_holder not in {record.id for record in group.records}
    assert response.total_groups_count == 1


def test_h_retained_to_removed_transition_rebuild_clears_derived_state(stores) -> None:
    pubs = stores["pubs"]
    review = stores["review"]
    import_id = uuid4()
    first = make_publication(index=21, title="Merge pair one", doi="10.1000/merge-pair", source="Crossref", source_id="CR-21")
    second = make_publication(index=22, title="Merge pair two", doi="10.1000/merge-pair", source="OpenAlex", source_id="W22")
    third = make_publication(index=23, title="Unrelated study", doi="10.1000/unrelated", source="Semantic Scholar", source_id="S2-23")
    pubs.import_source_publications(PROJECT_ID, [first, second, third], import_id=import_id)

    duplicates = stores["duplicates"]
    group_id = duplicates.get_candidate_duplicate_groups(PROJECT_ID).groups[0].group_id
    duplicates.record_decision(PROJECT_ID, group_id, "APPROVE")
    duplicates.merge_group(PROJECT_ID, group_id)
    assert stores["merges"].get_merge(PROJECT_ID, group_id) is not None

    review.remove_record(
        PROJECT_ID, import_id, second.record_id, reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT
    )
    report = stores["rebuild"].rebuild(PROJECT_ID)

    assert report.normalization_processed_records == 2
    assert group_id in report.removed_merge_group_ids
    assert group_id in report.removed_decision_group_ids
    assert stores["merges"].get_merge(PROJECT_ID, group_id) is None
    assert stores["decisions"].get_decision(PROJECT_ID, group_id) is None
    assert {p.record_id for p in pubs.get_active_publications(PROJECT_ID)} == {first.record_id, third.record_id}
    assert duplicates.get_candidate_duplicate_groups(PROJECT_ID).total_groups_count == 0


def test_i_providers_flow_through_single_active_corpus_contract(stores) -> None:
    ids = _seed_ten_publications(stores)
    active = stores["pubs"].get_active_publications(PROJECT_ID)
    providers = {entry.source for publication in active for entry in publication.provenance}
    assert {"Crossref", "OpenAlex", "Semantic Scholar"} <= providers
    execution = normalize_project(stores["pubs"], PROJECT_ID)
    assert execution.processed_records == len(active) == 7
    assert set(ids["retained"]) == {p.record_id for p in active}


def test_j_legacy_project_without_prescreening_decisions(stores) -> None:
    pubs = stores["pubs"]
    legacy = [
        make_publication(index=31, title="Legacy one", doi="10.1000/legacy-shared", source="Crossref", source_id="CR-31"),
        make_publication(index=32, title="Legacy two", doi="10.1000/legacy-shared", source="OpenAlex", source_id="W32"),
        make_publication(index=33, title="Legacy three", doi="10.1000/legacy-unique", source="Semantic Scholar", source_id="S2-33"),
    ]
    pubs.import_source_publications(PROJECT_ID, legacy)
    execution = normalize_project(pubs, PROJECT_ID)
    assert execution.processed_records == 3
    response = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    assert response.total_groups_count == 1
    report = stores["rebuild"].rebuild(PROJECT_ID)
    assert report.normalization_processed_records == 3
    assert report.removed_merges_count == 0
    assert report.removed_decisions_count == 0


def test_k_finalized_corpus_protections_remain_intact(stores) -> None:
    ids = _seed_ten_publications(stores)
    normalize_project(stores["pubs"], PROJECT_ID)
    finalization = stores["finalizations"].finalize_corpus(PROJECT_ID)
    members_before = {
        (member.record_id, member.admitted_to_screening)
        for member in stores["finalizations"].get_finalization_members(finalization.finalization_id)
    }
    with pytest.raises(CorpusFinalizedError):
        stores["rebuild"].rebuild(PROJECT_ID)
    # Normalization rerun must not silently mutate finalized membership.
    normalize_project(stores["pubs"], PROJECT_ID)
    members_after = {
        (member.record_id, member.admitted_to_screening)
        for member in stores["finalizations"].get_finalization_members(finalization.finalization_id)
    }
    assert members_before == members_after
    admitted = {record_id for record_id, admitted in members_after if admitted}
    assert admitted == set(ids["retained"])
    # Pre-screening modifications stay locked after finalization (WP1 invariant).
    with pytest.raises(CorpusFinalizedError):
        stores["review"].remove_record(
            PROJECT_ID,
            ids["import_id"],
            ids["retained"][0],
            reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        )


def test_l_normalization_reported_count_equals_active_input(stores) -> None:
    _seed_ten_publications(stores)
    report = stores["rebuild"].rebuild(PROJECT_ID)
    active_count = stores["pubs"].count_active_by_project(PROJECT_ID)
    assert report.normalization_processed_records == active_count == 7
    assert report.normalization_clean_records == active_count == 7
    stored = stores["executions"].get_for_project(PROJECT_ID)
    assert stored is not None
    assert stored.processed_records == active_count


def test_m_deduplication_counts_contain_no_removed_records(stores) -> None:
    ids = _seed_ten_publications(stores)
    report = stores["rebuild"].rebuild(PROJECT_ID)
    assert report.active_duplicate_groups_count == 1
    response = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    assert response.total_groups_count == 1
    removed = {str(record_id) for record_id in ids["removed"]}
    for group in response.groups:
        assert not (removed & {record.id for record in group.records})


def test_n_repeated_rebuild_is_deterministic_and_idempotent(stores) -> None:
    _seed_ten_publications(stores)
    first = stores["rebuild"].rebuild(PROJECT_ID)
    second = stores["rebuild"].rebuild(PROJECT_ID)
    assert (first.normalization_processed_records, first.active_duplicate_groups_count) == (7, 1)
    assert (second.normalization_processed_records, second.active_duplicate_groups_count) == (7, 1)
    assert second.removed_merges_count == 0
    assert second.removed_decisions_count == 0
    first_groups = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    second_groups = stores["duplicates"].get_candidate_duplicate_groups(PROJECT_ID)
    assert [g.group_id for g in first_groups.groups] == [g.group_id for g in second_groups.groups]


def test_o_rebuild_creates_no_formal_screening_decisions(stores) -> None:
    _seed_ten_publications(stores)
    assert _screening_decision_count(stores["db_path"]) == 0
    stores["rebuild"].rebuild(PROJECT_ID)
    stores["rebuild"].rebuild(PROJECT_ID)
    assert _screening_decision_count(stores["db_path"]) == 0
