from pydantic import BaseModel, ConfigDict, Field


class SharedIdentifierResponse(BaseModel):
    """Structured shared canonical identifier across candidate group members."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier_type: str
    value: str


class DuplicateRecordPreviewResponse(BaseModel):
    """Clean API preview of one publication within a candidate duplicate group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    authors: str
    year: int | None = None
    source: str
    doi: str | None = None
    pmid: str | None = None
    openalex_id: str | None = None


class DuplicateGroupResponse(BaseModel):
    """API representation of one candidate duplicate group awaiting review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str
    reason: str
    records_count: int
    shared_identifiers: list[SharedIdentifierResponse] = Field(default_factory=list)
    records: list[DuplicateRecordPreviewResponse]


class DuplicateGroupListResponse(BaseModel):
    """List response containing candidate duplicate groups for a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    total_groups_count: int
    groups: list[DuplicateGroupResponse]
