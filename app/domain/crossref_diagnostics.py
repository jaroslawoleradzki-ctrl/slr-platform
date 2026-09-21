"""Per-record Crossref diagnostic provenance (v0.6.9 WP2).

Observability-only structures answering, for every mapped Crossref candidate:

* which physical subquery (and plan index / page / rank / score) retrieved it,
* whether Crossref supplied the metadata needed for validation,
* what the canonical validator concluded per concept group,
* whether the candidate was finally retained or rejected, and why.

Retrieval facts ride on :class:`ProvenanceEntry` (one entry per retrieval
path, persisted inside snapshots).  Validation and retention facts live in
:class:`CrossrefRecordDiagnostic`, persisted as JSON inside checkpoint
``plan_metadata`` (rejected candidates are never snapshotted, so snapshots
alone cannot carry them).

Nothing here changes retrieval, validation, or retention semantics: the
validators are reused, never reimplemented.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.identifiers import IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    evaluate_expression,
)


class RetentionOutcome(StrEnum):
    """Final disposition of one mapped candidate within its provider run."""

    RETAINED = "retained"
    REJECTED_CANONICAL = "rejected_canonical_validation"
    REJECTED_CONSTRAINTS = "rejected_execution_constraints"


class CrossrefMetadataCompleteness(BaseModel):
    """Which provider-supplied fields were available for validation.

    Additional indicators can be added later as optional fields with
    ``False`` defaults without breaking stored diagnostics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title_present: bool = False
    abstract_present: bool = False
    doi_present: bool = False
    language_present: bool = False
    publication_year_present: bool = False
    publication_date_present: bool = False

    @classmethod
    def for_publication(cls, publication: Publication) -> "CrossrefMetadataCompleteness":
        """Completeness of provider-supplied metadata (pre-enrichment)."""
        return cls(
            title_present=bool(publication.title.strip()),
            abstract_present=publication.abstract is not None,
            doi_present=any(identifier.type is IdentifierType.DOI for identifier in publication.identifiers),
            language_present=publication.language is not None,
            publication_year_present=publication.publication_year is not None,
            publication_date_present=publication.publication_date is not None,
        )


class CanonicalGroupEvidence(BaseModel):
    """Validator evidence for one positive canonical concept group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_index: int = Field(ge=0)
    group_query: str = Field(min_length=1)
    status: CanonicalMatchStatus
    matched_terms: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()


class CrossrefRetrievalPath(BaseModel):
    """One physical retrieval event for a record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    physical_query: str = Field(min_length=1)
    physical_query_index: int = Field(ge=0)
    physical_cursor: str | None = None
    result_rank: int | None = Field(default=None, ge=0)
    provider_score: float | None = None

    @classmethod
    def from_provenance_entry(cls, entry: ProvenanceEntry) -> "CrossrefRetrievalPath | None":
        """Build a path from a retrieval provenance entry, if it carries one."""
        if entry.physical_query is None:
            return None
        return cls(
            physical_query=entry.physical_query,
            physical_query_index=entry.physical_query_index
            if entry.physical_query_index is not None
            else 0,
            physical_cursor=entry.physical_cursor,
            result_rank=entry.result_rank,
            provider_score=entry.provider_score,
        )

    def identity(self) -> tuple[int, str | None, int | None]:
        """Deterministic identity of one retrieval event."""
        return (self.physical_query_index, self.physical_cursor, self.result_rank)


class CrossrefRecordDiagnostic(BaseModel):
    """Complete diagnostic record for one mapped Crossref candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_record_id: str = Field(min_length=1)
    doi: str | None = None
    title: str = Field(min_length=1)
    search_run_id: UUID | None = None
    retrieval_paths: tuple[CrossrefRetrievalPath, ...] = ()
    completeness: CrossrefMetadataCompleteness = CrossrefMetadataCompleteness()
    canonical_status: CanonicalMatchStatus
    group_evidence: tuple[CanonicalGroupEvidence, ...] = ()
    retention_outcome: RetentionOutcome

    def with_retrieval_path(self, path: CrossrefRetrievalPath) -> "CrossrefRecordDiagnostic":
        """Return a copy with ``path`` merged; duplicate events are ignored."""
        identities = {existing.identity() for existing in self.retrieval_paths}
        if path.identity() in identities:
            return self
        return self.model_copy(update={"retrieval_paths": (*self.retrieval_paths, path)})


def group_evidence_for(query: SearchQuery, publication: Publication) -> tuple[CanonicalGroupEvidence, ...]:
    """Evaluate each positive top-level concept group with the real validator.

    The canonical strategy query is an AND of per-group OR expressions, so
    each child is evaluated independently.  Non-AND queries are treated as a
    single group.  No validation logic is duplicated here.
    """
    expression = query.expression
    if isinstance(expression, SearchGroup) and expression.operator is BooleanOperator.AND:
        children = list(expression.children)
    else:
        children = [expression]
    evidence: list[CanonicalGroupEvidence] = []
    for index, child in enumerate(children):
        result = evaluate_expression(child, publication)
        evidence.append(
            CanonicalGroupEvidence(
                group_index=index,
                group_query=child.to_boolean_query(),
                status=result.status,
                matched_terms=result.matched_terms,
                missing_fields=result.missing_fields,
            )
        )
    return tuple(evidence)


def retrieval_entries_from(publication: Publication, *, provider: str = "crossref") -> list[ProvenanceEntry]:
    """Provider retrieval entries, excluding enrichment entries."""
    return [
        entry
        for entry in publication.provenance
        if entry.source.casefold() == provider.casefold() and entry.physical_query is not None
    ]


def retrieval_paths_from(publication: Publication, *, provider: str = "crossref") -> list[CrossrefRetrievalPath]:
    """Deterministic retrieval paths recorded on a mapped publication."""
    paths: list[CrossrefRetrievalPath] = []
    for entry in retrieval_entries_from(publication, provider=provider):
        path = CrossrefRetrievalPath.from_provenance_entry(entry)
        if path is not None and all(path.identity() != existing.identity() for existing in paths):
            paths.append(path)
    return paths


def merge_retrieval_entries(
    first: list[ProvenanceEntry],
    additional: list[ProvenanceEntry],
) -> list[ProvenanceEntry]:
    """Combine provenance entries, preserving every distinct retrieval path.

    Entries are identical when provider, record, run, and retrieval position
    match; enrichment entries (no retrieval position) merge by provider,
    record, and run.
    """
    merged = list(first)
    seen = {
        (
            entry.source.casefold(),
            entry.source_record_id,
            entry.run_id,
            entry.transformation,
            entry.physical_query_index,
            entry.physical_cursor,
            entry.result_rank,
        )
        for entry in merged
    }
    for entry in additional:
        key = (
            entry.source.casefold(),
            entry.source_record_id,
            entry.run_id,
            entry.transformation,
            entry.physical_query_index,
            entry.physical_cursor,
            entry.result_rank,
        )
        if key not in seen:
            merged.append(entry)
            seen.add(key)
    return merged


def _replay_row(
    *,
    job_id: str,
    search_run_id: UUID | None,
    diagnostic: CrossrefRecordDiagnostic,
    path: CrossrefRetrievalPath | None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "search_run_id": str(search_run_id) if search_run_id is not None else None,
        "source_record_id": diagnostic.source_record_id,
        "doi": diagnostic.doi,
        "title": diagnostic.title,
        "physical_query": path.physical_query if path is not None else None,
        "physical_query_index": path.physical_query_index if path is not None else None,
        "physical_cursor": path.physical_cursor if path is not None else None,
        "result_rank": path.result_rank if path is not None else None,
        "provider_score": path.provider_score if path is not None else None,
        "metadata_completeness": diagnostic.completeness.model_dump(mode="json"),
        "canonical_group_evidence": [
            {
                "group_index": group.group_index,
                "group_query": group.group_query,
                "status": group.status.value,
                "matched_terms": list(group.matched_terms),
                "missing_fields": list(group.missing_fields),
            }
            for group in diagnostic.group_evidence
        ],
        "canonical_status": diagnostic.canonical_status.value,
        "retention_outcome": diagnostic.retention_outcome.value,
    }


def _replay_sort_key(row: dict[str, Any]) -> tuple[str, int, str, int]:
    return (
        row["source_record_id"] or "",
        row["physical_query_index"] if row["physical_query_index"] is not None else -1,
        row["physical_cursor"] or "",
        row["result_rank"] if row["result_rank"] is not None else -1,
    )


def sort_replay_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically order replay rows across merged diagnostic sources."""
    return sorted(rows, key=_replay_sort_key)


def build_crossref_replay_dataset(
    diagnostics: list[CrossrefRecordDiagnostic],
    *,
    job_id: str,
    search_run_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Build a bounded, deterministic replay dataset from record diagnostics.

    One row per (record, retrieval path); records with several retrieval paths
    keep every path.  Rows are sorted by
    ``(source_record_id, physical_query_index, physical_cursor, result_rank)``
    so repeated builds over the same diagnostics are byte-identical.
    """
    rows: list[dict[str, Any]] = []
    for diagnostic in sorted(diagnostics, key=lambda item: item.source_record_id):
        run_id = diagnostic.search_run_id if diagnostic.search_run_id is not None else search_run_id
        paths = sorted(diagnostic.retrieval_paths, key=lambda path: path.identity())
        if not paths:
            rows.append(_replay_row(job_id=job_id, search_run_id=run_id, diagnostic=diagnostic, path=None))
        for path in paths:
            rows.append(_replay_row(job_id=job_id, search_run_id=run_id, diagnostic=diagnostic, path=path))
    return sort_replay_rows(rows)
