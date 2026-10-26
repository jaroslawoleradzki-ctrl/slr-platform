from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkingCollectionSummary(BaseModel):
    total_records: int = Field(
        ...,
        description="Total publications count in Working Collection directly from ProjectPublicationRepository.count_by_project",
    )


class SourceSummaryItem(BaseModel):
    source: str = Field(
        ...,
        description="Provider name (openalex, crossref) or file format (RIS, BibTeX)",
    )
    source_kind: Literal["provider", "file"]
    successful_imports_count: int
    warning_imports_count: int
    failed_imports_count: int
    records_added_count: int = Field(
        ...,
        description="Sum of deltas (records_count) for successful and warning imports",
    )
    last_import_at: datetime | None = None
    last_import_status: Literal["success", "warning", "failed"] | None = None


class ImportHistoryItemDTO(BaseModel):
    import_id: UUID
    source_type: Literal["provider", "file"]
    filename: str | None = None
    format: str | None = None
    provider: str | None = None
    query: str | None = None
    records_count: int
    status: Literal["success", "warning", "failed"]
    warnings: tuple[str, ...]
    created_at: datetime
    source_record_count: int | None = None
    canonical_publication_count: int | None = None
    exact_doi_match_count: int | None = None
    repeated_source_count: int | None = None
    title_candidate_count: int | None = None
    similar_title_candidate_count: int | None = None
    skipped_canonical_count: int | None = None
    invalid_doi_count: int | None = None
    validation_error_count: int = 0
    skip_audit_available: bool = False
    audit_available: bool = False
    recovery_status: str | None = None


class SourcesSummaryResponse(BaseModel):
    project_id: str
    working_collection: WorkingCollectionSummary
    source_summaries: list[SourceSummaryItem]
    import_history: list[ImportHistoryItemDTO]
