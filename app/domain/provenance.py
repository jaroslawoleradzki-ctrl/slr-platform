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
    raw_file: str | None = None
    payload_hash: str | None = None
    transformation: str | None = None

    @field_validator(
        "source",
        "source_record_id",
        "raw_file",
        "payload_hash",
        "transformation",
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
