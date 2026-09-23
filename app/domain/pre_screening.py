from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.author import Author
from app.domain.identifiers import Identifier
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication


class PreScreeningStatus(StrEnum):
    RETAINED = "retained"
    REMOVED = "removed"


class PreScreeningRemovalReason(StrEnum):
    CLEARLY_OUTSIDE_SCOPE = "clearly_outside_scope"
    RETRIEVAL_ARTEFACT = "retrieval_artefact"
    INCOMPLETE_RECORD = "incomplete_record"
    OTHER = "other"


class PreScreeningDecision(BaseModel):
    """Auditable record representing a pre-screening decision before formal Screening."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    record_id: UUID
    import_id: UUID | None = None
    status: PreScreeningStatus
    reason: PreScreeningRemovalReason | None = None
    notes: str | None = None
    reviewer_id: str = "default_reviewer"
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "reviewer_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @field_validator("notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("decided_at", "created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_removal_contract(self) -> "PreScreeningDecision":
        if self.status is PreScreeningStatus.REMOVED:
            if self.reason is None:
                raise ValueError("a removal reason is required when status is 'removed'")
            if self.reason is PreScreeningRemovalReason.OTHER and not self.notes:
                raise ValueError("a note is required when removal reason is 'other'")
        elif self.status is PreScreeningStatus.RETAINED:
            # When restoring or retained, reason/notes are not required
            pass
        return self


class PreScreeningArchivedRecord(BaseModel):
    """Immutable, auditable snapshot of a publication removed during Import Review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    archive_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    record_id: UUID
    import_id: UUID | None = None
    provider: str | None = None
    title: str = Field(min_length=1)
    publication_year: int | None = None
    authors: list[Author] = Field(default_factory=list)
    identifiers: list[Identifier] = Field(default_factory=list)
    document_type: str | None = None
    language: str | None = None
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    document: dict[str, Any] = Field(default_factory=dict)
    removal_reason: PreScreeningRemovalReason
    removal_notes: str | None = None
    removed_by: str = "default_reviewer"
    removed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "removed_by")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @field_validator("removal_notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("removed_at", "created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @classmethod
    def from_publication(
        cls,
        publication: Publication,
        project_id: str,
        *,
        removal_reason: PreScreeningRemovalReason,
        import_id: UUID | None = None,
        removal_notes: str | None = None,
        removed_by: str = "default_reviewer",
        removed_at: datetime | None = None,
        archive_id: UUID | None = None,
    ) -> "PreScreeningArchivedRecord":
        now = removed_at or datetime.now(timezone.utc)
        provider = publication.discovered_by if publication.provenance else None
        return cls(
            archive_id=archive_id or uuid4(),
            project_id=project_id,
            record_id=publication.record_id,
            import_id=import_id,
            provider=provider,
            title=publication.title,
            publication_year=publication.publication_year,
            authors=list(publication.authors),
            identifiers=list(publication.identifiers),
            document_type=publication.document_type.value if publication.document_type else None,
            language=publication.language,
            provenance=list(publication.provenance),
            document=publication.model_dump(mode="json"),
            removal_reason=removal_reason,
            removal_notes=removal_notes,
            removed_by=removed_by,
            removed_at=now,
            created_at=now,
        )

    def to_publication(self) -> Publication:
        """Reconstitute canonical Publication from stored snapshot."""
        return Publication.model_validate(self.document)
