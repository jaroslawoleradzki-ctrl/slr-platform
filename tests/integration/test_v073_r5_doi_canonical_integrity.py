"""v0.7.3 R5.3 post-merge DOI canonical-resolution regressions.

Deterministic record IDs avoid depending on random UUID ordering.  Every test
uses a disposable SQLite database created by the repositories under ``tmp_path``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import UUID

import pytest

from app.api.dto.search_strategy import (
    ManualSourceDatabase,
    SearchResultRecordResponse,
)
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_import_service import (
    CanonicalResolutionError,
    ProjectImportService,
    _active_canonical_for_doi,
    _doi_candidates,
)

DOI = "10.1000/r5-m01"
PROJECT = "p1"
OTHER_PROJECT = "p2"


def _uuid(number: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{number:012d}")


def _publication(
    number: int,
    title: str,
    *,
    doi: str | None = None,
    source: str = "ris",
    source_record_id: str | None = None,
    transformation: str | None = None,
) -> Publication:
    return Publication(
        record_id=_uuid(number),
        title=title,
        authors=[Author(display_name=f"Author {number}")],
        publication_year=2020,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)] if doi else [],
        provenance=[
            ProvenanceEntry(
                source=source,
                source_record_id=source_record_id or f"src-{number}",
                transformation=transformation
                or ("ris_to_publication" if source == "ris" else None),
            )
        ],
    )


@pytest.fixture
def environment(tmp_path: Path):
    db = tmp_path / "r5_doi_integrity.db"
    publications = SqliteProjectPublicationRepository(db)
    history = SqliteImportHistoryRepository(db)
    normalization = SqliteNormalizationExecutionRepository(db)
    sources = SqliteImportSourceRecordRepository(db)
    decisions = SqliteDuplicateReviewDecisionRepository(db)
    merges = SqliteDuplicateMergeRepository(db)
    transactions = SqliteTransactionManager(db)

    connection = sqlite3.connect(db)
    connection.execute("INSERT INTO projects(project_id,title) VALUES (?,?)", (PROJECT, "P1"))
    connection.execute(
        "INSERT INTO projects(project_id,title) VALUES (?,?)", (OTHER_PROJECT, "P2")
    )
    connection.commit()
    connection.close()

    importer = ProjectImportService(
        publication_repository=publications,
        import_history_repository=history,
        normalization_repository=normalization,
        transaction_manager=transactions,
        source_record_repository=sources,
    )
    duplicate_service = ProjectDuplicateService(
        publications,
        decisions,
        merge_repository=merges,
        transaction_manager=transactions,
        source_record_repository=sources,
    )
    return importer, duplicate_service, publications, sources, history, db


def _seed_doi_and_title_only(publications: SqliteProjectPublicationRepository) -> None:
    """Seed a group whose DOI-bearing member has the higher UUID.

    The merge canonical is the lowest UUID, so the DOI-bearing publication is
    deterministically superseded, exactly like the audited reproduction.
    """
    publications.add_publications(
        PROJECT,
        [
            _publication(1, "M01 Shared Title"),
            _publication(2, "M01 Shared Title", doi=DOI),
        ],
    )


def _merge_group(duplicate_service: ProjectDuplicateService) -> str:
    response = duplicate_service.get_candidate_duplicate_groups(PROJECT)
    assert len(response.groups) == 1
    merge = duplicate_service.merge_group(PROJECT, response.groups[0].group_id)
    return merge.canonical_record_id


def _reimport(
    importer: ProjectImportService,
    publication: Publication,
    filename: str,
):
    return importer.import_bibliographic_publications(
        project_id=PROJECT,
        filename=filename,
        file_format="RIS",
        publications=[publication],
        source_database=ManualSourceDatabase.GOOGLE_SCHOLAR_POP,
        source_label="google_scholar_pop",
    )


def _source_for_doi(sources: SqliteImportSourceRecordRepository, filename: str):
    records = [
        record
        for record in sources.list_source_records(PROJECT)
        if record.source_filename == filename
    ]
    assert len(records) == 1
    return records[0]


def test_reimport_doi_links_active_canonical_not_superseded(environment) -> None:
    importer, duplicate_service, publications, sources, _, _ = environment
    _seed_doi_and_title_only(publications)
    canonical_id = _merge_group(duplicate_service)

    superseded = publications.get_superseded_by_map(PROJECT)
    assert str(superseded[_uuid(2)]) == canonical_id
    assert superseded[_uuid(1)] is None

    _reimport(
        importer,
        _publication(3, "M01 Reimported Record", doi=DOI),
        "reimport.ris",
    )

    assert len(publications.get_publications(PROJECT)) == 2
    source = _source_for_doi(sources, "reimport.ris")
    assert source.canonical_publication_id == canonical_id
    assert source.canonical_publication_id != str(_uuid(2))
    assert source.duplicate_match_type == "exact_doi"
    assert "superseded" in (source.duplicate_match_reason or "").casefold()


def test_multi_step_supersession_chain_resolves_final_active_record(environment) -> None:
    importer, duplicate_service, publications, sources, _, _ = environment
    _seed_doi_and_title_only(publications)
    _merge_group(duplicate_service)
    # Extend the chain: canonical(1) -> new canonical(4).
    publications.add_publications(PROJECT, [_publication(4, "Final Canonical Record")])
    publications.mark_superseded(PROJECT, [_uuid(1)], _uuid(4))

    _reimport(
        importer,
        _publication(5, "M01 Multi-step Reimport", doi=DOI),
        "multi-step.ris",
    )

    source = _source_for_doi(sources, "multi-step.ris")
    assert source.canonical_publication_id == str(_uuid(4))
    assert publications.get_superseded_by_map(PROJECT)[_uuid(4)] is None


def test_missing_supersession_target_raises_safe_error_and_rolls_back(environment) -> None:
    importer, _, publications, sources, history, _ = environment
    _seed_doi_and_title_only(publications)
    # Simulate a dangling target without going through the merge service.
    publications.mark_superseded(PROJECT, [_uuid(2)], _uuid(999))
    before_sources = sources.list_source_records(PROJECT)
    before_history = history.list_for_project(PROJECT)

    with pytest.raises(CanonicalResolutionError, match="no active canonical"):
        _reimport(
            importer,
            _publication(6, "M01 Missing Target", doi=DOI),
            "missing-target.ris",
        )

    assert sources.list_source_records(PROJECT) == before_sources
    assert history.list_for_project(PROJECT) == before_history
    assert len(publications.get_publications(PROJECT)) == 2


def test_supersession_cycle_raises_safe_error_and_rolls_back(environment) -> None:
    importer, _, publications, sources, history, _ = environment
    _seed_doi_and_title_only(publications)
    publications.mark_superseded(PROJECT, [_uuid(2)], _uuid(1))
    publications.mark_superseded(PROJECT, [_uuid(1)], _uuid(2))
    before_sources = sources.list_source_records(PROJECT)
    before_history = history.list_for_project(PROJECT)

    with pytest.raises(CanonicalResolutionError, match="cycle"):
        _reimport(
            importer,
            _publication(7, "M01 Cycle", doi=DOI),
            "cycle.ris",
        )

    assert sources.list_source_records(PROJECT) == before_sources
    assert history.list_for_project(PROJECT) == before_history


def test_doi_resolution_is_project_scoped(environment) -> None:
    importer, duplicate_service, publications, sources, _, _ = environment
    _seed_doi_and_title_only(publications)
    canonical_id = _merge_group(duplicate_service)
    publications.add_publications(
        OTHER_PROJECT, [_publication(101, "Other Project Record", doi=DOI)]
    )

    _reimport(
        importer,
        _publication(8, "M01 Isolated Reimport", doi=DOI),
        "isolated.ris",
    )

    source = _source_for_doi(sources, "isolated.ris")
    assert source.canonical_publication_id == canonical_id
    assert source.canonical_publication_id != str(_uuid(101))


def test_conflicting_doi_candidates_resolve_to_first_valid_active_canonical(
    environment,
) -> None:
    _, _, publications, _, _, _ = environment
    publications.add_publications(
        PROJECT,
        [
            _publication(10, "Conflict One", doi=DOI),
            _publication(11, "Conflict Two", doi=DOI),
            _publication(12, "Conflict Canonical"),
        ],
    )
    # First candidate is superseded; the second remains active but the existing
    # deterministic candidate order (collection position) selects the resolved
    # canonical of the first candidate.
    publications.mark_superseded(PROJECT, [_uuid(10)], _uuid(12))

    candidates = _doi_candidates(publications.get_publications(PROJECT))
    resolved = _active_canonical_for_doi(
        PROJECT,
        DOI,
        candidates[DOI],
        publications.get_superseded_by_map(PROJECT),
    )
    assert resolved == _uuid(12)


def test_provider_reimport_links_active_canonical(environment) -> None:
    importer, duplicate_service, publications, sources, _, _ = environment
    publications.add_publications(
        PROJECT,
        [
            _publication(
                20,
                "Provider Shared Title",
                source="openalex",
                source_record_id="W20",
                transformation="ris_to_publication",
            ),
            _publication(
                21,
                "Provider Shared Title",
                doi=DOI,
                source="openalex",
                source_record_id="W21",
                transformation="ris_to_publication",
            ),
        ],
    )
    response = duplicate_service.get_candidate_duplicate_groups(PROJECT)
    assert len(response.groups) == 1
    merge = duplicate_service.merge_group(PROJECT, response.groups[0].group_id)

    importer.import_provider_results_group(
        PROJECT,
        "openalex",
        [
            SearchResultRecordResponse(
                id=str(_uuid(22)),
                title="Provider Reimport",
                authors=["Author 22"],
                year=2021,
                provider="openalex",
                source_id="W21",
                doi=DOI,
            )
        ],
        query="m01",
        group_total_available=1,
    )

    source = next(
        record
        for record in sources.list_source_records(PROJECT)
        if record.import_format == "provider:openalex"
    )
    assert source.canonical_publication_id == merge.canonical_record_id
    assert source.canonical_publication_id != str(_uuid(21))
