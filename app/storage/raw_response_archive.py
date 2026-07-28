from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.providers.search.base import JsonObject


class RawResponseStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RawResponseArchiveEntry:
    """Raw provider responses and diagnostics for one search run."""

    archive_id: UUID
    search_run_id: UUID
    provider: str
    rendered_query: str
    captured_at: datetime
    status: RawResponseStatus
    responses: list[JsonObject]
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be blank")
        if not self.rendered_query.strip():
            raise ValueError("rendered_query must not be blank")
        if (
            self.captured_at.tzinfo is None
            or self.captured_at.utcoffset() is None
        ):
            raise ValueError("captured_at must be timezone-aware")
        has_error = self.error_type is not None or self.error_message is not None
        if self.status is RawResponseStatus.SUCCESS and has_error:
            raise ValueError("successful archive entries must not contain errors")
        if self.status is RawResponseStatus.FAILED and (
            self.error_type is None or self.error_message is None
        ):
            raise ValueError("failed archive entries require error diagnostics")


class RawResponseArchive(Protocol):
    async def save(self, entry: RawResponseArchiveEntry) -> None: ...
