from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.author import Author
from app.domain.identifiers import Identifier
from app.domain.provenance import ProvenanceEntry
from app.domain.venue import Venue


class DocumentType(StrEnum):
    """High-level publication type used by the canonical model."""

    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    REVIEW = "review"
    DISSERTATION = "dissertation"
    REPORT = "report"
    PREPRINT = "preprint"
    DATASET = "dataset"
    OTHER = "other"


class Publication(BaseModel):
    """Canonical, provider-independent representation of a publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: UUID = Field(default_factory=uuid4)
    schema_version: str = "1.0"
    title: str = Field(min_length=1)
    title_normalized: str | None = None
    abstract: str | None = None
    authors: list[Author] = Field(default_factory=list)
    publication_year: int | None = Field(default=None, ge=1000, le=9999)
    publication_date: date | None = None
    identifiers: list[Identifier] = Field(default_factory=list)
    venue: Venue | None = None
    publisher: str | None = None
    document_type: DocumentType | None = None
    language: str | None = Field(default=None, min_length=2)
    keywords: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    open_access: bool | None = None
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator(
        "schema_version",
        "title",
        "title_normalized",
        "abstract",
        "publisher",
        "language",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise ValueError("keywords must not contain blank values")
            key = stripped.casefold()
            if key not in seen:
                normalized.append(stripped)
                seen.add(key)
        return normalized

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped.startswith(("http://", "https://")):
                raise ValueError("urls must use http or https")
            if stripped not in seen:
                normalized.append(stripped)
                seen.add(stripped)
        return normalized

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_publication_date(self) -> "Publication":
        if (
            self.publication_date is not None
            and self.publication_year is not None
            and self.publication_date.year != self.publication_year
        ):
            raise ValueError("publication_date and publication_year must agree")
        return self
