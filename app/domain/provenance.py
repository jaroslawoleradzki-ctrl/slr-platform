from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProvenanceEntry(BaseModel):
    """Traceable origin of a record or field value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    query_id: UUID | None = None
    run_id: UUID | None = None
    rendered_query: str | None = None
    raw_file: str | None = None
    payload_hash: str | None = None
    transformation: str | None = None
    # --- Retrieval-path diagnostics (v0.6.9 WP2) ---
    # Exact physical subquery that returned this record. ``rendered_query``
    # keeps the combined plan string; ``physical_query`` identifies one of the
    # bounded candidate queries (e.g. one of the six Crossref queries).
    physical_query: str | None = None
    # Zero-based index of the physical query within the deterministic plan.
    physical_query_index: int | None = Field(default=None, ge=0)
    # Zero-based position of the record within its physical query page.
    # Together with ``physical_cursor`` it forms a deterministic position.
    result_rank: int | None = Field(default=None, ge=0)
    # Provider-supplied relevance score (Crossref ``score``), when present.
    provider_score: float | None = None
    # Physical cursor value used for the request that returned this record
    # (``"*"`` for the first page); identifies the page within the query.
    physical_cursor: str | None = None

    @field_validator(
        "source",
        "source_record_id",
        "rendered_query",
        "raw_file",
        "payload_hash",
        "transformation",
        "physical_query",
        "physical_cursor",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value
