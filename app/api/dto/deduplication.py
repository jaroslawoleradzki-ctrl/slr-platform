from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class DuplicateDecisionType(str, Enum):
    """Allowed input decision types from reviewer."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"


class DuplicateDecisionStatus(str, Enum):
    """Response decision status enum including initial PENDING state."""

    PENDING = "PENDING"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class SharedIdentifierResponse(BaseModel):
    """Structured shared canonical identifier across candidate group members."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier_type: str
    value: str


class ProvenanceEntryResponse(BaseModel):
    """API representation of a publication record provenance entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    source_record_id: str
    retrieved_at: str | None = None


class DuplicateRecordPreviewResponse(BaseModel):
    """Clean API preview of one publication within a candidate duplicate group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    authors: str
    year: int | None = None
    source: str
    venue: str | None = None
    doi: str | None = None
    pmid: str | None = None
    openalex_id: str | None = None
    provenance: list[ProvenanceEntryResponse] = Field(default_factory=list)


class DuplicateGroupResponse(BaseModel):
    """API representation of one candidate duplicate group awaiting review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str
    reason: str
    records_count: int
    status: DuplicateDecisionStatus = DuplicateDecisionStatus.PENDING
    rationale: str | None = None
    shared_identifiers: list[SharedIdentifierResponse] = Field(default_factory=list)
    records: list[DuplicateRecordPreviewResponse]


class DuplicateGroupListResponse(BaseModel):
    """List response containing candidate duplicate groups for a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    total_groups_count: int
    groups: list[DuplicateGroupResponse]


class DuplicateGroupDecisionRequest(BaseModel):
    """Request payload for recording a reviewer duplicate decision with optional rationale."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: DuplicateDecisionType
    rationale: str | None = Field(default=None, max_length=1000)


class DuplicateGroupDecisionResponse(BaseModel):
    """Response returning current decision state and optional rationale for a duplicate group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    group_id: str
    decision: DuplicateDecisionStatus
    rationale: str | None = None
