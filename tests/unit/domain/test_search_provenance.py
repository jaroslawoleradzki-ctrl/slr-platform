from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.publication import Publication
from app.domain.search import SearchRun, SearchRunStatus
from app.domain.search_provenance import (
    PublicationSearchProvenance,
    SearchExecutionProvenance,
)

_STARTED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
_FINISHED_AT = _STARTED_AT + timedelta(seconds=2.5)
_RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
_QUERY_ID = UUID("22222222-2222-2222-2222-222222222222")


def _search_run(*, provider: str = "openalex") -> SearchRun:
    return SearchRun(
        run_id=_RUN_ID,
        query_id=_QUERY_ID,
        query_version=1,
        provider=provider,
        rendered_query="lean",
        status=SearchRunStatus.COMPLETED,
        records_retrieved=1,
        started_at=_STARTED_AT,
        finished_at=_FINISHED_AT,
    )


def test_publication_provenance_preserves_identity_and_run() -> None:
    publication = Publication(title="Result")
    search_run = _search_run()

    provenance = PublicationSearchProvenance(
        publication=publication,
        search_run=search_run,
        provider="openalex",
    )

    assert provenance.publication is publication
    assert provenance.search_run is search_run
    assert provenance.search_run_id == search_run.run_id


def test_publication_provenance_rejects_blank_provider() -> None:
    with pytest.raises(ValueError, match="provider must not be blank"):
        PublicationSearchProvenance(
            publication=Publication(title="Result"),
            search_run=_search_run(),
            provider="  ",
        )


def test_publication_provenance_rejects_provider_mismatch() -> None:
    with pytest.raises(ValueError, match="provider must match"):
        PublicationSearchProvenance(
            publication=Publication(title="Result"),
            search_run=_search_run(provider="openalex"),
            provider="crossref",
        )


def test_publication_provenance_requires_completed_run() -> None:
    running = SearchRun(
        run_id=_RUN_ID,
        query_id=_QUERY_ID,
        query_version=1,
        provider="openalex",
        rendered_query="lean",
        status=SearchRunStatus.RUNNING,
        started_at=_STARTED_AT,
    )

    with pytest.raises(ValueError, match="requires a completed search run"):
        PublicationSearchProvenance(
            publication=Publication(title="Result"),
            search_run=running,
            provider="openalex",
        )


def test_execution_provenance_calculates_duration_and_counts() -> None:
    provenance = SearchExecutionProvenance(
        started_at=_STARTED_AT,
        finished_at=_FINISHED_AT,
        provider_run_ids=(_RUN_ID,),
        total_provider_results=3,
        merged_result_count=2,
    )

    assert provenance.duration_seconds == 2.5
    assert provenance.provider_run_ids == (_RUN_ID,)
    assert provenance.total_provider_results == 3
    assert provenance.merged_result_count == 2


@pytest.mark.parametrize("field", ["started_at", "finished_at"])
def test_execution_provenance_rejects_naive_timestamp(field: str) -> None:
    values = {
        "started_at": _STARTED_AT,
        "finished_at": _FINISHED_AT,
    }
    values[field] = datetime(2026, 7, 28, 12, 0)

    with pytest.raises(ValueError, match=f"{field} must be timezone-aware"):
        SearchExecutionProvenance(
            started_at=values["started_at"],
            finished_at=values["finished_at"],
            provider_run_ids=(),
            total_provider_results=0,
            merged_result_count=0,
        )


def test_execution_provenance_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="finished_at must not be earlier"):
        SearchExecutionProvenance(
            started_at=_FINISHED_AT,
            finished_at=_STARTED_AT,
            provider_run_ids=(),
            total_provider_results=0,
            merged_result_count=0,
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("total_provider_results", "total_provider_results must not be negative"),
        ("merged_result_count", "merged_result_count must not be negative"),
    ],
)
def test_execution_provenance_rejects_negative_counts(
    field: str,
    message: str,
) -> None:
    values = {
        "total_provider_results": 0,
        "merged_result_count": 0,
    }
    values[field] = -1

    with pytest.raises(ValueError, match=message):
        SearchExecutionProvenance(
            started_at=_STARTED_AT,
            finished_at=_FINISHED_AT,
            provider_run_ids=(),
            total_provider_results=values["total_provider_results"],
            merged_result_count=values["merged_result_count"],
        )


def test_execution_provenance_allows_zero_duration_and_no_providers() -> None:
    provenance = SearchExecutionProvenance(
        started_at=_STARTED_AT,
        finished_at=_STARTED_AT,
        provider_run_ids=(),
        total_provider_results=0,
        merged_result_count=0,
    )

    assert provenance.duration_seconds == 0
    assert provenance.provider_run_ids == ()
