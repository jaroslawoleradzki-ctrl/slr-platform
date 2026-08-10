from datetime import date, datetime, timezone
from uuid import UUID

from app.api.dto.search_strategy import SearchResultRecordResponse
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.venue import Venue, VenueType
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshot,
    SqliteSearchResultSnapshotRepository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_import_service import ProjectImportService


def test_authoritative_snapshot_import_preserves_screening_metadata(tmp_path) -> None:
    database = tmp_path / "metadata.db"
    run_id = UUID("00000000-0000-0000-0000-000000000010")
    provenance = ProvenanceEntry(
        source="openalex",
        source_record_id="W123",
        run_id=run_id,
        query_id=UUID("00000000-0000-0000-0000-000000000011"),
        rendered_query='"energy efficiency"',
        retrieved_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )
    publication = Publication(
        title="Canonical title",
        abstract="Complete abstract",
        publication_year=2024,
        publication_date=date(2024, 2, 3),
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1/example")],
        venue=Venue(name="Journal", type=VenueType.JOURNAL),
        publisher="Publisher",
        document_type=DocumentType.JOURNAL_ARTICLE,
        language="en",
        keywords=["energy"],
        urls=["https://example.org/work"],
        open_access=True,
        provenance=[provenance],
    )
    snapshot_repo = SqliteSearchResultSnapshotRepository(database)
    snapshot = snapshot_repo.save(
        SearchResultSnapshot.create(
            project_id="lean_energy",
            search_run_id=run_id,
            provider="openalex",
            source_id="W123",
            publication=publication,
        )
    )
    publication_repo = SqliteProjectPublicationRepository(database)
    service = ProjectImportService(
        publication_repo,
        SqliteImportHistoryRepository(database),
        SqliteNormalizationExecutionRepository(database),
        SqliteTransactionManager(database),
        snapshot_repo,
    )
    client_record = SearchResultRecordResponse(
        id=str(snapshot.snapshot_id),
        title="tampered",
        authors=[],
        year=1999,
        provider="openalex",
        source_id="W123",
        doi=None,
    )

    service.import_provider_results_group("lean_energy", "openalex", [client_record], None, 1)

    stored = publication_repo.get_publications("lean_energy")[0]
    assert stored == publication
    assert stored.abstract == "Complete abstract"
    assert stored.venue == publication.venue and stored.publisher == "Publisher"
    assert stored.document_type is DocumentType.JOURNAL_ARTICLE and stored.language == "en"
    assert stored.keywords == ["energy"] and stored.urls == ["https://example.org/work"]
    assert stored.open_access is True and stored.identifiers == publication.identifiers
    assert stored.provenance == [provenance]
    assert stored.provenance[0].source_record_id == "W123"
    assert stored.provenance[0].rendered_query == '"energy efficiency"'
