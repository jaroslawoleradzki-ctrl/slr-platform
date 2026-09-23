from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.normalization import normalize_publication
from app.repositories.project_publication_repository import ProjectPublicationRepository
from app.services.active_publication_filter import (
    provides_active_corpus,
    provides_publication_update,
)


@dataclass(frozen=True, slots=True)
class NormalizationExecution:
    run_id: UUID
    project_id: str
    status: str
    processed_records: int
    clean_records: int
    warnings_count: int
    errors_count: int
    rules_applied: tuple[str, ...]
    audit_trail: tuple[str, ...]
    started_at: datetime
    completed_at: datetime
    error_message: str | None = None

    @property
    def executed_at(self) -> datetime:
        return self.completed_at


def _changed(before: Publication, after: Publication) -> tuple[int, int, int, int, int]:
    doi_changes = 0
    orcid_changes = 0
    author_changes = 0
    title_changes = int(before.title_normalized != after.title_normalized)
    language_changes = int(before.language != after.language)

    before_dois = [i.value for i in before.identifiers if i.type is IdentifierType.DOI]
    after_dois = [i.value for i in after.identifiers if i.type is IdentifierType.DOI]
    doi_changes = sum(left != right for left, right in zip(before_dois, after_dois))
    doi_changes += abs(len(before_dois) - len(after_dois))

    for before_author, after_author in zip(before.authors, after.authors):
        author_changes += int(
            (before_author.display_name, before_author.given_name, before_author.family_name)
            != (after_author.display_name, after_author.given_name, after_author.family_name)
        )
        before_orcid = [i.value for i in before_author.identifiers if i.type is IdentifierType.ORCID]
        after_orcid = [i.value for i in after_author.identifiers if i.type is IdentifierType.ORCID]
        orcid_changes += sum(left != right for left, right in zip(before_orcid, after_orcid))
        orcid_changes += abs(len(before_orcid) - len(after_orcid))
    return doi_changes, author_changes, orcid_changes, title_changes, language_changes


def _read_active_corpus(
    repository: ProjectPublicationRepository,
    project_id: str,
) -> list[Publication]:
    """Return the authoritative Active Project Corpus for normalization input.

    The Active Corpus contract (WP1) excludes ``pre_screening_status='removed'``
    records, physically archived records, and superseded duplicate members.
    Provider provenance (Crossref / OpenAlex / Semantic Scholar / file imports)
    is treated uniformly: no provider-specific filtering is applied here.

    Repositories without the WP1 ``get_active_publications`` accessor expose
    their whole collection, which is then by definition the active corpus
    (legacy projects without pre-screening decisions remain compatible).
    """
    if provides_active_corpus(repository):
        get_active = getattr(repository, "get_active_publications")
        return list(get_active(project_id))
    return list(repository.get_publications(project_id))


def _persist_normalized_corpus(
    repository: ProjectPublicationRepository,
    project_id: str,
    normalized: list[Publication],
) -> None:
    """Persist normalized active records without touching non-active rows.

    Per-record ``update_publication`` refreshes only Active Corpus members, so
    pre-screening removed rows, superseded duplicate members, and their
    ``import_id`` / ``pre_screening_status`` / ``position`` metadata are never
    rewritten, resurrected, or deleted by normalization. Repositories without
    the WP1 accessor (legacy path where the active corpus is the whole
    collection) keep the previous atomic replace semantics.
    """
    if provides_active_corpus(repository):
        if not provides_publication_update(repository):
            raise TypeError(
                "publication repository provides active-corpus reads but no "
                "per-record update; refusing bulk replace that could delete "
                "non-active rows"
            )
        for publication in normalized:
            repository.update_publication(project_id, publication)
        return
    repository.replace_publications(project_id, normalized)


def normalize_project(
    repository: ProjectPublicationRepository,
    project_id: str,
) -> NormalizationExecution:
    """Normalize exactly the authoritative Active Project Corpus (WP2).

    Only active publications enter and leave normalization: removed records
    are never processed, never rewritten, and a rerun cannot resurrect them.
    Reported ``processed_records`` / ``clean_records`` describe the records
    actually processed, not all ``project_publications`` rows.
    """
    started_at = datetime.now(timezone.utc)
    publications = _read_active_corpus(repository, project_id)
    normalized = [normalize_publication(publication) for publication in publications]
    _persist_normalized_corpus(repository, project_id, normalized)

    counts = [0, 0, 0, 0, 0]
    for before, after in zip(publications, normalized):
        changes = _changed(before, after)
        counts = [left + right for left, right in zip(counts, changes)]

    labels = (
        ("DOI normalized", counts[0]),
        ("authors normalized", counts[1]),
        ("ORCID normalized", counts[2]),
        ("title canonicalized", counts[3]),
        ("language canonicalized", counts[4]),
    )
    processed = len(publications)
    audit_trail = (
        tuple(f"{label}: {count}" for label, count in labels)
        if processed
        else ()
    )
    rules_applied = tuple(label for label, _ in labels)
    return NormalizationExecution(
        run_id=uuid4(),
        project_id=project_id,
        status="completed",
        processed_records=processed,
        clean_records=processed,
        warnings_count=0,
        errors_count=0,
        rules_applied=rules_applied,
        audit_trail=audit_trail,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
