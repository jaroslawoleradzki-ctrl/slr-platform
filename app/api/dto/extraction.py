"""Data Transfer Objects for Data Extraction (Phase 9.3 & 9.4)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectExtractionConfigurationRequestDTO(BaseModel):
    """Request DTO to set or update project extraction configuration."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., description="Extraction template identifier (e.g. 'generic_extraction').")
    template_version: str = Field(..., description="Immutable template semver version (e.g. '1.0.0').")


class ProjectExtractionConfigurationResponseDTO(BaseModel):
    """Response DTO representing active project extraction configuration."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    template_id: str
    template_version: str
    configured_at: str
    updated_at: str


class ExtractionEligibilityResultDTO(BaseModel):
    """Response DTO for publication extraction eligibility status."""

    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    status: str
    is_eligible: bool
    reason_details: str | None = None


class ExtractionEligibilityListResponseDTO(BaseModel):
    """Response DTO for list of publication eligibility statuses in a project."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total_publications: int
    eligible_count: int
    items: list[ExtractionEligibilityResultDTO]


class ExtractedValueStateDTO(BaseModel):
    """DTO representing an extracted field value assessment and provenance."""

    model_config = ConfigDict(extra="forbid")

    value_id: UUID | None = None
    field_key: str
    status: str = Field(..., description="ValueStatus: unassessed, present, not_reported, not_applicable, unclear")
    origin: str | None = None

    text_value: str | None = None
    int_value: int | None = None
    float_value: float | None = None
    bool_value: bool | None = None
    unit_value: str | None = None
    json_value: list[str] | None = None

    source_page: str | None = None
    source_section: str | None = None
    source_locator: str | None = None
    source_quote: str | None = None
    reviewer_note: str | None = None


class ExtractedGroupItemStateDTO(BaseModel):
    """DTO representing a 1:N repeating group item instance."""

    model_config = ConfigDict(extra="forbid")

    group_item_id: UUID | None = None
    group_key: str
    item_index: int
    values: list[ExtractedValueStateDTO] = Field(default_factory=list)


class ExtractionRevisionSubmitRequestDTO(BaseModel):
    """Request DTO to submit a new append-only extraction revision."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(..., description="Identifier of the reviewer submitting this revision.")
    publication_values: list[ExtractedValueStateDTO] = Field(default_factory=list)
    group_items: list[ExtractedGroupItemStateDTO] = Field(default_factory=list)
    mark_complete: bool = Field(default=False, description="If True, requires all fields to be complete.")


class ExtractionRevisionResponseDTO(BaseModel):
    """Response DTO representing an append-only extraction revision."""

    model_config = ConfigDict(extra="forbid")

    revision_id: UUID
    record_id: UUID
    project_id: str
    publication_id: UUID
    revision_index: int
    reviewer_id: str
    completeness_status: str
    publication_values: list[ExtractedValueStateDTO]
    group_items: list[ExtractedGroupItemStateDTO]
    created_at: str


class ExtractionRecordResponseDTO(BaseModel):
    """Response DTO representing the current extraction state for a publication."""

    model_config = ConfigDict(extra="forbid")

    record_id: UUID
    project_id: str
    publication_id: UUID
    template_id: str
    template_version: str
    current_status: str
    created_at: str
    updated_at: str
    latest_revision: ExtractionRevisionResponseDTO | None = None


class ExtractionRevisionHistoryResponseDTO(BaseModel):
    """Response DTO for list of historical extraction revisions."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    publication_id: UUID
    total_revisions: int
    revisions: list[ExtractionRevisionResponseDTO]


class ExtractionProgressResponseDTO(BaseModel):
    """Response DTO for project data extraction progress metrics."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total_eligible_publications: int
    not_started_count: int
    in_progress_count: int
    complete_count: int
    needs_review_count: int
    completion_percentage: float


class ExtractionRecordSummaryDTO(BaseModel):
    """Summary DTO for publication extraction status in summary table."""

    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    extraction_status: str
    latest_revision_index: int | None = None
    latest_reviewer_id: str | None = None
    latest_updated_at: str | None = None


class ExtractionRecordListResponseDTO(BaseModel):
    """Response DTO for eligible publication extraction queue."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total_records: int
    items: list[ExtractionRecordSummaryDTO]


class ExtractionMatrixRowDTO(BaseModel):
    """DTO representing a single 1:N repeating group item row in the cross-study matrix."""

    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    publication_title: str
    group_key: str
    group_name: str
    group_item_id: UUID
    item_index: int
    values: list[ExtractedValueStateDTO]


class ExtractionMatrixResponseDTO(BaseModel):
    """Response DTO for cross-study repeating group matrix."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    template_id: str
    template_version: str
    total_relationships: int
    group_keys: list[str]
    items: list[ExtractionMatrixRowDTO]
