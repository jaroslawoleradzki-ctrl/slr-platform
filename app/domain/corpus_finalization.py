"""Contracts and accounting primitives for the corpus-to-screening boundary.

This module deliberately contains no persistence model.  WP1 owns the
pre-screening disposition state; WP4 consumes the small contract defined
here once that state is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class CorpusRecordDisposition(StrEnum):
    """The only dispositions relevant when a prepared corpus is finalized."""

    RETAINED_FOR_SCREENING = "retained_for_screening"
    REMOVED_DURING_PRE_SCREENING = "removed_during_pre_screening"


@dataclass(frozen=True, slots=True)
class PreparedCorpusRecord:
    """Minimum WP1-to-WP4 record contract.

    ``removal_reason`` is required only for pre-screening removals.  The
    canonical record ID and provenance references are retained so a later
    finalization event can reconstruct its exact input set.
    """

    record_id: UUID
    disposition: CorpusRecordDisposition
    provenance: tuple[str, ...] = ()
    removal_reason: str | None = None

    def __post_init__(self) -> None:
        if self.disposition is CorpusRecordDisposition.REMOVED_DURING_PRE_SCREENING:
            if not self.removal_reason or not self.removal_reason.strip():
                raise ValueError("pre-screening removals require a removal_reason")
        elif self.removal_reason is not None:
            raise ValueError("retained records cannot carry a pre-screening removal_reason")


@dataclass(frozen=True, slots=True)
class PreparedCorpusCounts:
    """Counts captured at the preparation/finalization boundary."""

    source_records: int
    duplicates_removed: int
    pre_screening_removed: int
    retained_for_screening: int

    def __post_init__(self) -> None:
        values = (
            self.source_records,
            self.duplicates_removed,
            self.pre_screening_removed,
            self.retained_for_screening,
        )
        if any(value < 0 for value in values):
            raise ValueError("corpus counts cannot be negative")
        if self.duplicates_removed + self.pre_screening_removed + self.retained_for_screening != self.source_records:
            raise ValueError(
                "source_records must equal duplicates_removed + pre_screening_removed + retained_for_screening"
            )


class PreparedCorpusProvider(Protocol):
    """Future integration boundary supplied by pre-screening review (WP1).

    The provider must return one disposition per canonical prepared record.
    It must not expose WP1's storage schema to finalization callers.
    """

    def prepared_records(self, project_id: str) -> tuple[PreparedCorpusRecord, ...]:
        """Return the current prepared corpus for ``project_id``."""


def count_prepared_corpus(
    records: tuple[PreparedCorpusRecord, ...],
    *,
    source_records: int,
    duplicates_removed: int,
) -> PreparedCorpusCounts:
    """Build auditable counts without treating removals as screening decisions."""

    retained = sum(record.disposition is CorpusRecordDisposition.RETAINED_FOR_SCREENING for record in records)
    removed = sum(record.disposition is CorpusRecordDisposition.REMOVED_DURING_PRE_SCREENING for record in records)
    return PreparedCorpusCounts(
        source_records=source_records,
        duplicates_removed=duplicates_removed,
        pre_screening_removed=removed,
        retained_for_screening=retained,
    )
