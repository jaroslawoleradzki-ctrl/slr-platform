"""Shared active-publication boundary for downstream research workflows."""

from __future__ import annotations

from uuid import UUID

from app.repositories.project_publication_repository import ProjectNotFoundError


def active_publication_ids(repository: object, project_id: str) -> set[UUID] | None:
    """Return active records, or ``None`` for legacy evidence-only projects.

    Some pre-publication-mapping test/import data has extraction evidence but no
    project-publication collection at all.  It cannot contain a superseded
    record, so preserving that legacy state is safe.  Once a collection exists,
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
