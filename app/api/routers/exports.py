"""API Router for research exports (v0.6.1 Slice 1: BibTeX + RIS).

HTTP concerns only: content types, attachment filenames, and error mapping
(mirrors ``extraction.py`` style). Serialization lives in pure writers under
``app/services/export``; dataset selection goes through the read-only
``ExportDatasetService`` facade, which reuses the canonical active-publication
boundary — superseded records are never exported.

Filenames derive from ``project_id`` plus fixed literals only; no user-supplied
text reaches headers (plan §17).
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.repositories.project_publication_repository import ProjectNotFoundError
from app.services.export.bibtex_writer import render_bibtex
from app.services.export.ris_writer import render_ris
from app.services.export_dataset_service import (
    ExportDatasetService,
    default_export_dataset_service,
)

router = APIRouter(prefix="/projects", tags=["exports"])

BIBTEX_MEDIA_TYPE = "application/x-bibtex"
RIS_MEDIA_TYPE = "application/x-research-info-systems"


def get_export_dataset_service() -> ExportDatasetService:
    return default_export_dataset_service()


def _attachment_response(content: str, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{project_id}/exports/bibtex",
    summary="Export the active Working Collection as BibTeX (.bib)",
    description=(
        "Returns one BibTeX entry per active canonical publication, ordered by "
        "collection position. Superseded duplicate records are never exported. "
        "Read-only: the project state is not modified."
    ),
)
def export_bibtex(
    project_id: str,
    service: ExportDatasetService = Depends(get_export_dataset_service),
) -> Response:
    try:
        publications = service.get_bibliographic_records(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _attachment_response(
        render_bibtex(publications),
        BIBTEX_MEDIA_TYPE,
        f"{project_id}_publications.bib",
    )


@router.get(
    "/{project_id}/exports/ris",
    summary="Export the active Working Collection as RIS (.ris)",
    description=(
        "Returns one RIS record per active canonical publication, ordered by "
        "collection position. Superseded duplicate records are never exported. "
        "Read-only: the project state is not modified."
    ),
)
def export_ris(
    project_id: str,
    service: ExportDatasetService = Depends(get_export_dataset_service),
) -> Response:
    try:
        publications = service.get_bibliographic_records(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _attachment_response(
        render_ris(publications),
        RIS_MEDIA_TYPE,
        f"{project_id}_publications.ris",
    )
