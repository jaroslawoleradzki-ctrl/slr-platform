from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.provenance import ProvenanceEntry


def test_provenance_uses_timezone_aware_timestamp() -> None:
    provenance = ProvenanceEntry(source="openalex", source_record_id="W123")

    assert provenance.retrieved_at.tzinfo is not None


def test_provenance_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ProvenanceEntry(
            source="openalex",
            source_record_id="W123",
            retrieved_at=datetime(2026, 7, 22, 8, 0, 0),
        )


def test_provenance_round_trips_with_search_context() -> None:
    provenance = ProvenanceEntry(
        source="openalex",
        source_record_id="https://openalex.org/W123",
        retrieved_at=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        query_id=UUID("00000000-0000-0000-0000-000000000001"),
        run_id=UUID("00000000-0000-0000-0000-000000000002"),
        rendered_query="lean energy",
    )

    restored = ProvenanceEntry.model_validate_json(
        provenance.model_dump_json()
    )

    assert restored == provenance
