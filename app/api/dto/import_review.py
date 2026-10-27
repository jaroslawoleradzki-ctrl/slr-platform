from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportReviewBlockerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    count: int = Field(ge=0)
    publication_ids: list[str] = Field(default_factory=list)


class ImportWarningCategoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    label: str
    count: int = Field(ge=0)


class ImportReviewDecisionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID
    decision: Literal["accepted", "rejected"]
    reviewer_id: str
    rationale: str | None = None
    decided_at: datetime
    deleted_publication_count: int = Field(ge=0)
    retained_source_record_count: int = Field(ge=0)
    prisma_treatment: str


class ImportReviewDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    import_id: UUID
    source_type: Literal["provider", "file"]
    filename: str | None = None
    format: str | None = None
    provider: str | None = None
    query: str | None = None
    records_count: int = Field(ge=0)
    status: str
    effective_status: str
    review_status: str
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    source_record_count: int = Field(ge=0)
    canonical_publication_count: int = Field(ge=0)
    exact_doi_match_count: int = Field(ge=0)
    repeated_source_count: int = Field(ge=0)
    title_candidate_count: int = Field(ge=0)
    similar_title_candidate_count: int = Field(ge=0)
    skipped_canonical_count: int = Field(ge=0)
    invalid_doi_count: int = Field(ge=0)
    validation_error_count: int = Field(ge=0)
    audit_available: bool
    can_accept: bool
    can_reject: bool
    warning_categories: list[ImportWarningCategoryResponse] = Field(default_factory=list)
    blockers: list[ImportReviewBlockerResponse] = Field(default_factory=list)
    decision: ImportReviewDecisionSummary | None = None


class ImportReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["accept", "reject"]
    reviewer_id: str = Field(min_length=1)
    rationale: str | None = Field(default=None, max_length=1000)
    confirm_rejection: bool = False


class ImportReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    import_id: UUID
    decision: ImportReviewDecisionSummary
    effective_status: str
    review_status: str
