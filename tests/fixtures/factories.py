from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.author import Author
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import ImportHistoryRecord
from app.services.normalization_service import NormalizationExecution

DEFAULT_TEST_TIME = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def make_provenance(
    source: str = "OpenAlex", source_record_id: str = "W1"
) -> ProvenanceEntry:
    """Create a deterministic provenance entry."""
    return ProvenanceEntry(source=source, source_record_id=source_record_id)


def make_author(name: str = "Smith, John", orcid: str | None = None) -> Author:
    """Create a deterministic author entry."""
    identifiers: list[Identifier] = []
    if orcid:
        identifiers.append(Identifier(type=IdentifierType.ORCID, value=orcid))
    return Author(display_name=name, identifiers=identifiers)


def make_publication(
    index: int = 1,
    title: str | None = None,
    doi: str | None = None,
    openalex_id: str | None = None,
    year: int = 2024,
    source: str = "OpenAlex",
    source_id: str | None = None,
    created_at: datetime | None = None,
    record_id: UUID | None = None,
) -> Publication:
    """Create a deterministic publication instance for test fixtures."""
    uuid_str = f"00000000-0000-0000-0000-{index:012d}"
    pub_id = record_id or UUID(uuid_str)
    pub_title = title or f"Test Publication Title {index}"
    src_id = source_id or f"W{index}"

    identifiers: list[Identifier] = []
    if doi:
        identifiers.append(Identifier(type=IdentifierType.DOI, value=doi))
    if openalex_id:
        identifiers.append(Identifier(type=IdentifierType.OPENALEX, value=openalex_id))

    return Publication(
        record_id=pub_id,
        title=pub_title,
        authors=[make_author(f"Author {index}")],
        publication_year=year,
        identifiers=identifiers,
        provenance=[make_provenance(source=source, source_record_id=src_id)],
        created_at=created_at or DEFAULT_TEST_TIME,
    )


def make_import_history(
    project_id: str = "test_project",
    records_count: int = 1,
    source_type: str = "provider",
    provider: str | None = "openalex",
    filename: str | None = None,
    format_type: str | None = None,
    status: str = "success",
    fingerprint: str | None = None,
    created_at: datetime | None = None,
    import_id: UUID | None = None,
) -> ImportHistoryRecord:
    """Create a deterministic import history record."""
    return ImportHistoryRecord(
        import_id=import_id or uuid4(),
        project_id=project_id,
        source_type=source_type,
        filename=filename,
        format=format_type,
        provider=provider,
        query="test query" if provider else None,
        records_count=records_count,
        total_available=records_count,
        status=status,
        warnings=(),
        created_at=created_at or DEFAULT_TEST_TIME,
        fingerprint=fingerprint,
    )


def make_normalization_execution(
    project_id: str = "test_project",
    processed_records: int = 10,
    clean_records: int = 10,
    warnings_count: int = 0,
    errors_count: int = 0,
    status: str = "completed",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    run_id: UUID | None = None,
) -> NormalizationExecution:
    """Create a deterministic normalization execution summary."""
    ts = started_at or DEFAULT_TEST_TIME
    return NormalizationExecution(
        project_id=project_id,
        run_id=run_id or uuid4(),
        status=status,
        processed_records=processed_records,
        clean_records=clean_records,
        warnings_count=warnings_count,
        errors_count=errors_count,
        started_at=ts,
        completed_at=completed_at or ts,
        audit_trail=("Normalized titles and DOIs",),
        rules_applied=("doi_canonical", "title_whitespace"),
    )


def make_duplicate_decision(
    project_id: str = "test_project",
    group_id: str = "group-1",
    decision: DuplicateDecision = DuplicateDecision.APPROVE,
    rationale: str | None = None,
) -> DuplicateGroupReviewDecision:
    """Create a deterministic duplicate group review decision."""
    return DuplicateGroupReviewDecision(
        decision=decision,
        rationale=rationale,
    )
