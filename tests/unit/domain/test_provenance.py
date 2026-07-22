from datetime import datetime

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
