from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class PublicationRecord(BaseModel):
    record_id: UUID = Field(default_factory=uuid4)
    title: str
    title_normalized: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    publication_date: date | None = None
    doi: str | None = None
    abstract: str | None = None
    journal: str | None = None
    publisher: str | None = None
    publication_type: str | None = None
    language: str | None = None
    url: str | None = None
    open_access: bool | None = None
    sources: list[str] = Field(default_factory=list)
    source_record_ids: dict[str, str] = Field(default_factory=dict)
    raw_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
