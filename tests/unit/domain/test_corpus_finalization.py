from uuid import UUID

import pytest

from app.domain.corpus_finalization import (
    CorpusRecordDisposition,
    PreparedCorpusRecord,
    count_prepared_corpus,
)


def record(number: int, disposition: CorpusRecordDisposition, reason: str | None = None) -> PreparedCorpusRecord:
    return PreparedCorpusRecord(
        record_id=UUID(int=number),
        disposition=disposition,
        provenance=(f"provider:{number}",),
        removal_reason=reason,
    )


def test_pre_screening_removal_is_counted_outside_formal_screening() -> None:
    counts = count_prepared_corpus(
        (
            record(1, CorpusRecordDisposition.RETAINED_FOR_SCREENING),
            record(2, CorpusRecordDisposition.REMOVED_DURING_PRE_SCREENING, "out of scope"),
        ),
        source_records=2,
        duplicates_removed=0,
    )

    assert counts.pre_screening_removed == 1
    assert counts.retained_for_screening == 1


def test_duplicate_accounting_is_explicit() -> None:
    counts = count_prepared_corpus(
        (record(1, CorpusRecordDisposition.RETAINED_FOR_SCREENING),),
        source_records=3,
        duplicates_removed=2,
    )

    assert counts.source_records == 3
    assert counts.duplicates_removed + counts.pre_screening_removed + counts.retained_for_screening == 3


def test_removed_record_requires_provenance_reason() -> None:
    with pytest.raises(ValueError, match="removal_reason"):
        record(1, CorpusRecordDisposition.REMOVED_DURING_PRE_SCREENING)


def test_counts_reject_unbalanced_accounting() -> None:
    with pytest.raises(ValueError, match="source_records"):
        count_prepared_corpus(
            (record(1, CorpusRecordDisposition.RETAINED_FOR_SCREENING),),
            source_records=2,
            duplicates_removed=0,
        )
