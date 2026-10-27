from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.import_review import get_import_review_service
from app.api.routers.search_strategy import (
    get_import_history_repository,
    get_import_review_repository,
    get_project_publication_repository,
    get_sources_summary_service,
)
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import ImportHistoryRecord, SqliteImportHistoryRepository
from app.repositories.import_review_repository import SqliteImportReviewRepository
from app.repositories.import_source_record_repository import ImportSourceRecord, SqliteImportSourceRecordRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.import_review_service import ImportReviewService
from app.services.sources_summary_service import SourcesSummaryService

PROJECT_ID = "api-review-project"


def _publication(number: int = 1) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Review publication {number}",
        publication_year=2024,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/review")],
        provenance=[ProvenanceEntry(source="ris", source_record_id="10.1000/review")],
    )


def _create_import(
    *,
    database: Path,
    history: SqliteImportHistoryRepository,
    sources: SqliteImportSourceRecordRepository,
    publications: SqliteProjectPublicationRepository,
    status: str = "warning",
    publications_to_add: list[Publication] | None = None,
) -> tuple[UUID, list[Publication]]:
    records = publications_to_add or [_publication()]
    import_id = uuid4()
    history.create(
        ImportHistoryRecord(
            import_id=import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="review.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=len(records),
            total_available=None,
            status=status,
            warnings=("Skipped 2 duplicate record(s).",) if status == "warning" else (),
            created_at=datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc),
        )
    )
    for index, publication in enumerate(records):
        sources.create_source_record(
            ImportSourceRecord(
                source_record_id=f"source-{index + 1}",
                project_id=PROJECT_ID,
                import_id=import_id,
                source_filename="review.ris",
                source_file_hash=None,
                source_record_index=index + 1,
                title=publication.title,
                publication_year=publication.publication_year,
                original_doi="10.1000/review",
                normalized_doi="10.1000/review",
                authors=("Reviewer",),
                document_type="journal_article",
                provenance=publication.provenance[0].model_dump(mode="json"),
                canonical_publication_id=str(publication.record_id),
                recovery_status="imported",
            )
        )
    publications.import_source_publications(
        PROJECT_ID, records, import_id=import_id, preserve_source_occurrences=True
    )
    return import_id, records


@pytest.fixture
def environment(tmp_path: Path):
    database = tmp_path / "api-review.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    publications = SqliteProjectPublicationRepository(database)
    reviews = SqliteImportReviewRepository(database)
    service = ImportReviewService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
        transaction_manager=SqliteTransactionManager(database),
    )
    app.dependency_overrides[get_import_review_service] = lambda: service
    app.dependency_overrides[get_project_publication_repository] = lambda: publications
    app.dependency_overrides[get_import_history_repository] = lambda: history
    app.dependency_overrides[get_import_review_repository] = lambda: reviews
    app.dependency_overrides[get_sources_summary_service] = lambda: SourcesSummaryService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
    )
    client = TestClient(app)
    yield client, service, history, sources, publications, database
    app.dependency_overrides.clear()


def test_review_detail_exposes_warnings_and_decisions(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, _ = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )

    response = client.get(f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/review")

    assert response.status_code == 200
    body = response.json()
    assert body["import_id"] == str(import_id)
    assert body["status"] == "warning"
    assert body["review_status"] == "pending"
    assert body["effective_status"] == "warning"
    assert body["can_accept"] is True
    assert body["can_reject"] is True
    assert body["warnings"] == ["Skipped 2 duplicate record(s)."]
    assert body["source_record_count"] == 1


def test_accept_endpoint_sets_effective_success(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, records = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )

    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/review",
        json={"decision": "accept", "reviewer_id": "alice", "rationale": "Reviewed."},
    )

    assert response.status_code == 200
    assert response.json()["effective_status"] == "success"
    assert response.json()["review_status"] == "accepted"
    assert publications.get_publications(PROJECT_ID) == records
    assert history.get(PROJECT_ID, import_id).status == "warning"


def test_reject_requires_confirmation(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, records = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )

    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/review",
        json={"decision": "reject", "reviewer_id": "alice"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "confirmation_required"
    assert publications.get_publications(PROJECT_ID) == records


def test_reject_endpoint_removes_active_import_only_after_confirmation(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, _ = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )

    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/review",
        json={
            "decision": "reject",
            "reviewer_id": "alice",
            "confirm_rejection": True,
            "rationale": "Wrong file.",
        },
    )

    assert response.status_code == 200
    assert response.json()["effective_status"] == "rejected"
    assert response.json()["review_status"] == "rejected"
    assert publications.get_publications(PROJECT_ID) == []
    assert history.get(PROJECT_ID, import_id) is not None
    assert len(sources.list_source_records_for_import(PROJECT_ID, import_id)) == 1


def test_shared_publication_returns_structured_conflict(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, records = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )
    other_import_id = uuid4()
    history.create(
        ImportHistoryRecord(
            import_id=other_import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="other.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=0,
            total_available=None,
            status="success",
            warnings=(),
            created_at=datetime(2026, 10, 27, 11, 0, tzinfo=timezone.utc),
        )
    )
    sources.create_source_record(
        ImportSourceRecord(
            source_record_id="other-source",
            project_id=PROJECT_ID,
            import_id=other_import_id,
            source_filename="other.ris",
            source_file_hash=None,
            source_record_index=1,
            title=records[0].title,
            publication_year=records[0].publication_year,
            original_doi="10.1000/review",
            normalized_doi="10.1000/review",
            authors=("Reviewer",),
            document_type="journal_article",
            provenance=records[0].provenance[0].model_dump(mode="json"),
            canonical_publication_id=str(records[0].record_id),
            recovery_status="linked",
        )
    )

    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/review",
        json={"decision": "reject", "reviewer_id": "alice", "confirm_rejection": True},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "import_rejection_blocked"
    assert {item["code"] for item in detail["blockers"]} == {"shared_publication"}
    assert publications.get_publications(PROJECT_ID) == records


def test_review_is_project_scoped(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, _ = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )

    response = client.get(f"/api/v1/projects/other-project/imports/{import_id}/review")

    assert response.status_code == 404


def test_rejected_import_is_hidden_from_active_history_and_sources_summary(environment) -> None:
    client, _, history, sources, publications, database = environment
    import_id, _ = _create_import(
        database=database, history=history, sources=sources, publications=publications
    )
    client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/review",
        json={"decision": "reject", "reviewer_id": "alice", "confirm_rejection": True},
    )

    active = client.get(f"/api/v1/projects/{PROJECT_ID}/imports")
    audit = client.get(
        f"/api/v1/projects/{PROJECT_ID}/imports", params={"include_rejected": True}
    )
    summary = client.get(f"/api/v1/projects/{PROJECT_ID}/sources-summary")

    assert active.status_code == 200 and active.json() == []
    assert audit.status_code == 200
    assert audit.json()[0]["review_status"] == "rejected"
    assert audit.json()[0]["effective_status"] == "rejected"
    assert summary.status_code == 200
    assert summary.json()["import_history"] == []
    assert summary.json()["working_collection"]["total_records"] == 0
