from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.identifiers import IdentifierType
from app.domain.pre_screening import (
    PreScreeningDecision,
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.publication import Publication


class PreScreeningRemovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: PreScreeningRemovalReason
    notes: str | None = None
    reviewer_id: str = "default_reviewer"


class PreScreeningRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = "default_reviewer"


class ImportedRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: UUID
    project_id: str
    import_id: UUID | None
    title: str
    authors: list[str]
    publication_year: int | None
    venue_name: str | None
    doi: str | None
    abstract: str | None
    provider: str
    source_record_id: str
    pre_screening_status: PreScreeningStatus
    removal_reason: PreScreeningRemovalReason | None
    removal_notes: str | None
    decided_at: datetime | None
    reviewer_id: str | None

    @classmethod
    def from_domain(
        cls,
        publication: Publication,
        project_id: str,
        import_id: UUID | None,
        status: PreScreeningStatus,
        latest_decision: PreScreeningDecision | None = None,
    ) -> "ImportedRecordResponse":
        doi = None
        for identifier in publication.identifiers:
            if identifier.type == IdentifierType.DOI:
                doi = identifier.value
                break

        provider = publication.discovered_by
        source_record_id = publication.provenance[0].source_record_id if publication.provenance else str(publication.record_id)
        venue_name = publication.venue.name if publication.venue else None

        removal_reason = None
        removal_notes = None
        decided_at = None
        reviewer_id = None

        if status == PreScreeningStatus.REMOVED and latest_decision is not None and latest_decision.status == PreScreeningStatus.REMOVED:
            removal_reason = latest_decision.reason
            removal_notes = latest_decision.notes
            decided_at = latest_decision.decided_at
            reviewer_id = latest_decision.reviewer_id

        return cls(
            record_id=publication.record_id,
            project_id=project_id,
            import_id=import_id,
            title=publication.title,
            authors=[author.display_name for author in publication.authors],
            publication_year=publication.publication_year,
            venue_name=venue_name,
            doi=doi,
            abstract=publication.abstract,
            provider=provider,
            source_record_id=source_record_id,
            pre_screening_status=status,
            removal_reason=removal_reason,
            removal_notes=removal_notes,
            decided_at=decided_at,
            reviewer_id=reviewer_id,
        )


class ImportedRecordsPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    import_id: UUID
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    total_imported: int = Field(ge=0)
    retained_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    items: list[ImportedRecordResponse]
