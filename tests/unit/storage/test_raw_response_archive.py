from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.providers.search.base import JsonObject
from app.storage.raw_response_archive import (
    RawResponseArchiveEntry,
    RawResponseStatus,
)

_ARCHIVE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_RUN_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_CAPTURED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


def _entry(
    *,
    provider: str = "openalex",
    rendered_query: str = '"lean manufacturing"',
    captured_at: datetime = _CAPTURED_AT,
    status: RawResponseStatus = RawResponseStatus.SUCCESS,
    responses: list[JsonObject] | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> RawResponseArchiveEntry:
    return RawResponseArchiveEntry(
        archive_id=_ARCHIVE_ID,
        search_run_id=_RUN_ID,
        provider=provider,
        rendered_query=rendered_query,
        captured_at=captured_at,
        status=status,
        responses=[] if responses is None else responses,
        error_type=error_type,
        error_message=error_message,
    )


def test_success_accepts_ordered_raw_pages() -> None:
    responses: list[JsonObject] = [{"page": 1}, {"page": 2}]

    entry = _entry(responses=responses)

    assert entry.status is RawResponseStatus.SUCCESS
    assert entry.responses is responses
    assert entry.captured_at == _CAPTURED_AT
    assert entry.error_type is None
    assert entry.error_message is None


def test_success_accepts_empty_raw_responses() -> None:
    entry = _entry(responses=[])

    assert entry.responses == []


def test_failure_accepts_diagnostics() -> None:
    entry = _entry(
        status=RawResponseStatus.FAILED,
        error_type="RuntimeError",
        error_message="provider failed",
    )

    assert entry.status is RawResponseStatus.FAILED
    assert entry.responses == []
    assert entry.error_type == "RuntimeError"
    assert entry.error_message == "provider failed"


def test_rejects_blank_provider() -> None:
    with pytest.raises(ValueError, match="provider must not be blank"):
        _entry(provider="  ")


def test_rejects_blank_rendered_query() -> None:
    with pytest.raises(ValueError, match="rendered_query must not be blank"):
        _entry(rendered_query="")


def test_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="captured_at must be timezone-aware"):
        _entry(captured_at=datetime(2026, 7, 28, 12, 0))


def test_rejects_success_with_error_diagnostics() -> None:
    with pytest.raises(
        ValueError,
        match="successful archive entries must not contain errors",
    ):
        _entry(error_type="RuntimeError", error_message="failure")


@pytest.mark.parametrize(
    ("error_type", "error_message"),
    [(None, None), ("RuntimeError", None), (None, "failure")],
)
def test_rejects_failure_without_complete_diagnostics(
    error_type: str | None,
    error_message: str | None,
) -> None:
    with pytest.raises(
        ValueError,
        match="failed archive entries require error diagnostics",
    ):
        _entry(
            status=RawResponseStatus.FAILED,
            error_type=error_type,
            error_message=error_message,
        )
