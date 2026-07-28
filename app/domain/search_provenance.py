from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.publication import Publication
from app.domain.search import SearchRun, SearchRunStatus


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PublicationSearchProvenance:
    """Originating completed provider run for one canonical publication."""

    publication: Publication
    search_run: SearchRun
    provider: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be blank")
        if self.provider != self.search_run.provider:
            raise ValueError("provider must match search_run provider")
        if self.search_run.status is not SearchRunStatus.COMPLETED:
            raise ValueError("publication provenance requires a completed search run")

    @property
    def search_run_id(self) -> UUID:
        return self.search_run.run_id


@dataclass(frozen=True, slots=True)
class SearchExecutionProvenance:
    """Minimal summary indexing one complete Search Engine execution."""

    started_at: datetime
    finished_at: datetime
    provider_run_ids: tuple[UUID, ...]
    total_provider_results: int
    merged_result_count: int

    def __post_init__(self) -> None:
        _require_aware(self.started_at, field_name="started_at")
        _require_aware(self.finished_at, field_name="finished_at")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at")
        if self.total_provider_results < 0:
            raise ValueError("total_provider_results must not be negative")
        if self.merged_result_count < 0:
            raise ValueError("merged_result_count must not be negative")

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()
