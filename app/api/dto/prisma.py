from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PrismaMetricsResponse(BaseModel):
    """Authoritative PRISMA funnel metrics derived from persisted project state.

    All counts are computed server-side from the project's persisted ingestion,
    deduplication, and screening state. No frontend approximation is used.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    records_identified_providers: int = Field(ge=0)
    records_identified_imports: int = Field(ge=0)
    total_identified: int = Field(ge=0)
    records_after_normalization: int = Field(ge=0)
    records_before_dedup: int = Field(ge=0)
    records_after_technical_merger: int = Field(ge=0)
    duplicate_groups_pending_review: int = Field(ge=0)
    records_screened_title_abstract: int = Field(ge=0)
    records_screened_full_text: int = Field(ge=0)
    studies_included_synthesis: int = Field(ge=0)
