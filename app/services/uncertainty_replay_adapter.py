"""Adapter from WP2 Crossref diagnostic replay rows to WP4 candidates.

WP2 replay is intentionally one row per retrieval path.  This module groups
those rows into one experimental candidate per durable WP2 diagnostic identity
without rerunning canonical validation or treating paths as candidates.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.crossref_diagnostics import RetentionOutcome
from app.services.canonical_query_validator import CanonicalMatchStatus
from app.services.uncertainty_experiment import UncertaintyCandidate


class WP2ReplayDataIntegrityError(ValueError):
    """Raised when path rows disagree about one durable diagnostic candidate."""


class WP2ReplayCandidate(BaseModel):
    """One candidate reconstructed from one or more WP2 replay path rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: UncertaintyCandidate
    job_id: str = Field(min_length=1)
    search_run_id: str | None = None
    source_record_id: str = Field(min_length=1)
    doi: str | None = None
    title: str = Field(min_length=1)
    metadata_completeness: dict[str, bool]
    retention_outcome: RetentionOutcome
    retrieval_path_count: int = Field(ge=1)


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WP2ReplayDataIntegrityError(f"WP2 replay row requires non-empty {key}")
    return value.strip()


def _candidate_key(row: Mapping[str, Any]) -> tuple[str, str | None, str]:
    """The actual WP2 replay identity: job, run, and durable source record."""
    job_id = _required_text(row, "job_id")
    run_id = row.get("search_run_id")
    if run_id is not None and not isinstance(run_id, str):
        raise WP2ReplayDataIntegrityError("WP2 replay search_run_id must be a string or null")
    return job_id, run_id, _required_text(row, "source_record_id")


def _canonical_evidence(row: Mapping[str, Any]) -> tuple[tuple[int, str, tuple[str, ...]], ...]:
    raw = row.get("canonical_group_evidence")
    if not isinstance(raw, list):
        raise WP2ReplayDataIntegrityError("WP2 replay canonical_group_evidence must be a list")
    evidence: list[tuple[int, str, tuple[str, ...]]] = []
    seen_indices: set[int] = set()
    for group in raw:
        if not isinstance(group, Mapping):
            raise WP2ReplayDataIntegrityError("WP2 replay group evidence must contain objects")
        index = group.get("group_index")
        if not isinstance(index, int) or index < 0 or index in seen_indices:
            raise WP2ReplayDataIntegrityError("WP2 replay group evidence has invalid or duplicate group_index")
        seen_indices.add(index)
        try:
            status = CanonicalMatchStatus(str(group["status"])).value
        except (KeyError, ValueError) as exc:
            raise WP2ReplayDataIntegrityError("WP2 replay group evidence has invalid status") from exc
        missing = group.get("missing_fields", [])
        if not isinstance(missing, list) or not all(isinstance(field, str) for field in missing):
            raise WP2ReplayDataIntegrityError("WP2 replay group evidence has invalid missing_fields")
        evidence.append((index, status, tuple(missing)))
    return tuple(sorted(evidence))


def _candidate_facts(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Candidate facts that every retrieval path must report identically."""
    try:
        canonical_status = CanonicalMatchStatus(str(row["canonical_status"]))
        outcome = RetentionOutcome(str(row["retention_outcome"]))
    except (KeyError, ValueError) as exc:
        raise WP2ReplayDataIntegrityError("WP2 replay row has invalid status or retention outcome") from exc
    completeness = row.get("metadata_completeness")
    if not isinstance(completeness, Mapping) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in completeness.items()
    ):
        raise WP2ReplayDataIntegrityError("WP2 replay metadata_completeness must be a boolean mapping")
    title = _required_text(row, "title")
    doi = row.get("doi")
    if doi is not None and not isinstance(doi, str):
        raise WP2ReplayDataIntegrityError("WP2 replay doi must be a string or null")
    return (
        canonical_status,
        _canonical_evidence(row),
        tuple(sorted(completeness.items())),
        outcome,
        title,
        doi,
    )


def adapt_wp2_replay_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[WP2ReplayCandidate, ...]:
    """Group real WP2 path rows into one deterministic WP4 candidate each.

    The input is the schema emitted by ``build_crossref_replay_dataset``.
    Candidate facts must match across every path row.  Retrieval-specific
    fields may differ and only contribute to ``retrieval_path_count``.
    """
    grouped: dict[tuple[str, str | None, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_candidate_key(row), []).append(row)

    candidates: list[WP2ReplayCandidate] = []
    for key in sorted(grouped, key=lambda item: (item[0], item[1] or "", item[2])):
        candidate_rows = grouped[key]
        facts = _candidate_facts(candidate_rows[0])
        if any(_candidate_facts(row) != facts for row in candidate_rows[1:]):
            raise WP2ReplayDataIntegrityError(
                f"conflicting candidate facts across WP2 replay paths for {key[2]!r}"
            )
        canonical_status, evidence, completeness_items, outcome, title, doi = facts
        if outcome is RetentionOutcome.REJECTED_CANONICAL and canonical_status is not CanonicalMatchStatus.NON_MATCH:
            raise WP2ReplayDataIntegrityError("canonical rejection must have canonical NON_MATCH status")
        if outcome is RetentionOutcome.REJECTED_CONSTRAINTS and canonical_status is CanonicalMatchStatus.NON_MATCH:
            raise WP2ReplayDataIntegrityError("constraint rejection cannot have canonical NON_MATCH status")

        completeness = dict(completeness_items)
        group_statuses = tuple(CanonicalMatchStatus(status) for _, status, _ in evidence)
        missing_fields = tuple(
            dict.fromkeys(field for _, _, fields in evidence for field in fields)
        )
        execution_eligible = outcome is RetentionOutcome.RETAINED
        candidate = UncertaintyCandidate(
            candidate_id="|".join((key[0], key[1] or "", key[2])),
            canonical_status=canonical_status,
            positive_group_count=len(evidence),
            evidenced_group_count=sum(status is CanonicalMatchStatus.MATCH for status in group_statuses),
            missing_fields=missing_fields,
            abstract_missing=not completeness.get("abstract_present", False),
            group_statuses=group_statuses,
            # A canonical rejection is classified by its canonical status;
            # Fetch All never reached execution constraints for it.
            execution_eligible=execution_eligible if canonical_status is not CanonicalMatchStatus.NON_MATCH else True,
        )
        candidates.append(
            WP2ReplayCandidate(
                candidate=candidate,
                job_id=key[0],
                search_run_id=key[1],
                source_record_id=key[2],
                doi=doi,
                title=title,
                metadata_completeness=completeness,
                retention_outcome=outcome,
                retrieval_path_count=len(candidate_rows),
            )
        )
    return tuple(candidates)
