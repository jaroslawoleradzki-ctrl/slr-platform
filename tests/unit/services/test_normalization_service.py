"""Tests for the normalization service language canonicalization."""

from datetime import datetime, timezone
from uuid import UUID

from app.domain import (
    Author,
    Identifier,
    IdentifierType,
    ProvenanceEntry,
)
from app.domain.publication import Publication
from app.repositories.project_publication_repository import ProjectPublicationRepository
from app.services.normalization_service import normalize_project


class InMemoryProjectPublicationRepository(ProjectPublicationRepository):
    """In-memory repository for testing normalization service."""

    def __init__(self) -> None:
        self._storage: dict[str, list[Publication]] = {}

    def get_publications(self, project_id: str) -> list[Publication]:
        return self._storage.get(project_id, [])

    def replace_publications(self, project_id: str, publications: list[Publication]) -> None:
        self._storage[project_id] = publications


def _publication(
    *,
    record_id: UUID | None = None,
    language: str | None = "en",
    title: str = "Test Title",
    doi: str | None = None,
) -> Publication:
    identifiers = []
    if doi:
        identifiers.append(Identifier(type=IdentifierType.DOI, value=doi))
    return Publication(
        record_id=record_id or UUID("11111111-1111-1111-1111-111111111111"),
        schema_version="1.0",
        title=title,
        authors=[Author(display_name="Test Author")],
        publication_year=2024,
        identifiers=identifiers,
        language=language,
        provenance=[
            ProvenanceEntry(source="test", source_record_id="rec-1")
        ],
        created_at=datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc),
    )


def test_normalize_project_canonicalizes_language() -> None:
    """Normalization service canonicalizes language to ISO 639-1."""
    repo = InMemoryProjectPublicationRepository()
    project_id = "test-project"

    repo.replace_publications(project_id, [
        _publication(language="eng", title="Paper 1"),
        _publication(record_id=UUID("22222222-2222-2222-2222-222222222222"), language="EN", title="Paper 2"),
        _publication(record_id=UUID("33333333-3333-3333-3333-333333333333"), language="en", title="Paper 3"),
        _publication(record_id=UUID("44444444-4444-4444-4444-444444444444"), language=None, title="Paper 4"),
        _publication(record_id=UUID("55555555-5555-5555-5555-555555555555"), language="unknown", title="Paper 5"),
    ])

    execution = normalize_project(repo, project_id)

    # All non-None languages should be canonicalized to "en"
    publications = repo.get_publications(project_id)
    assert publications[0].language == "en"
    assert publications[1].language == "en"
    assert publications[2].language == "en"
    assert publications[3].language is None
    assert publications[4].language is None

    # Audit counts actual changes:
    # - "eng" -> "en" (1 change)
    # - "EN" -> "en" (1 change)
    # - "en" -> "en" (0 changes)
    # - None -> None (0 changes)
    # - "unknown" -> None (1 change)
    # Total: 3
    audit_text = " ".join(execution.audit_trail)
    assert "language canonicalized: 3" in audit_text
    assert "language canonicalized" in execution.rules_applied


def test_normalize_project_language_idempotent() -> None:
    """Re-running normalization is idempotent for language."""
    repo = InMemoryProjectPublicationRepository()
    project_id = "test-project"

    repo.replace_publications(project_id, [
        _publication(language="eng", title="Paper 1"),
    ])

    # First run
    normalize_project(repo, project_id)
    pubs1 = repo.get_publications(project_id)
    assert pubs1[0].language == "en"

    # Second run
    exec2 = normalize_project(repo, project_id)
    pubs2 = repo.get_publications(project_id)
    assert pubs2[0].language == "en"
    assert pubs1[0] == pubs2[0]

    # Second run should show 0 language changes
    audit_text = " ".join(exec2.audit_trail)
    assert "language canonicalized: 0" in audit_text


def test_normalize_project_preserves_record_ids_and_state() -> None:
    """Normalization preserves record IDs and other state."""
    repo = InMemoryProjectPublicationRepository()
    project_id = "test-project"

    orig_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    repo.replace_publications(project_id, [
        _publication(record_id=orig_id, language="eng", title="Paper 1"),
    ])

    normalize_project(repo, project_id)
    publications = repo.get_publications(project_id)

    assert publications[0].record_id == orig_id
    assert publications[0].schema_version == "1.0"
    assert publications[0].title == "Paper 1"
    assert publications[0].language == "en"
