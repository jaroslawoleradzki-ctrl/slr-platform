"""Authoritative Active Corpus boundaries and accessors for SLR projects (WP1 Foundation)."""

from __future__ import annotations

from uuid import UUID

from app.domain.publication import Publication
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
    default_project_publication_repository,
)


def get_active_project_publications(
    project_id: str,
    repository: ProjectPublicationRepository | None = None,
) -> list[Publication]:
    """Return the authoritative active publication corpus for a project.

    An active publication is defined as:
    1. Persisted in the project's collection (`project_publications`).
    2. Not superseded by a duplicate merge (`superseded_by IS NULL`).
    3. Not removed during Pre-Screening / Import Review (`pre_screening_status != 'removed'`).
    4. Not physically archived to `pre_screening_archive`.

    This function is the single source of truth for the active corpus across all
    downstream pipeline stages (Normalization, Deduplication, Finalization, Screening, etc.).
    """
    repo = repository or default_project_publication_repository()
    return repo.get_active_publications(project_id)


def count_active_project_publications(
    project_id: str,
    repository: ProjectPublicationRepository | None = None,
) -> int:
    """Return the exact count of active publications in the project corpus."""
    repo = repository or default_project_publication_repository()
    return repo.count_active_by_project(project_id)


def repository_provides_method(repository: object, method_name: str) -> bool:
    """Return True when the repository genuinely implements ``method_name``.

    ``ProjectPublicationRepository`` subclasses inherit ``...`` protocol stubs
    returning ``None``; only a real override (or instance attribute) counts as
    support, so legacy minimal repositories safely fall back instead of
    calling an unimplemented stub.
    """
    stub = ProjectPublicationRepository.__dict__.get(method_name)
    for klass in type(repository).__mro__:
        if method_name in klass.__dict__:
            candidate = klass.__dict__[method_name]
            return callable(candidate) and candidate is not stub
    instance_attr = getattr(repository, "__dict__", {}).get(method_name)
    return callable(instance_attr)


def provides_active_corpus(repository: object) -> bool:
    """Return True when the repository genuinely implements the WP1 accessor."""
    return repository_provides_method(repository, "get_active_publications")


def provides_publication_update(repository: object) -> bool:
    """Return True when the repository genuinely implements per-record update."""
    return repository_provides_method(repository, "update_publication")


def provides_removed_record_listing(repository: object) -> bool:
    """Return True when the repository can list pre-screening removed IDs."""
    return repository_provides_method(repository, "get_pre_screening_removed_record_ids")


def active_publication_ids(repository: object, project_id: str) -> set[UUID] | None:
    """Return active record IDs, or ``None`` for legacy evidence-only projects.

    Some pre-publication-mapping test/import data has extraction evidence but no
    project-publication collection at all. It cannot contain a superseded
    record, so preserving that legacy state is safe. Once a collection exists,
    this function is the authoritative active-only boundary.
    """
    getter = getattr(repository, "get_active_publications", None)
    all_getter = getattr(repository, "get_publications", None)
    if getter is None and all_getter is None:
        raise TypeError("publication repository does not provide a read method")
    try:
        publications = getter(project_id) if getter is not None else all_getter(project_id)  # type: ignore[misc]
    except ProjectNotFoundError:
        return None
    ids = {publication.record_id for publication in publications}
    return ids or None
