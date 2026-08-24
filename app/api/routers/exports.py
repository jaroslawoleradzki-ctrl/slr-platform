"""API Router for research exports (v0.6.1 Slice 1: BibTeX + RIS).

HTTP concerns only: content types, attachment filenames, and error mapping
(mirrors ``extraction.py`` style). Serialization lives in pure writers under
``app/services/export``; dataset selection goes through the read-only
``ExportDatasetService`` facade, which reuses the canonical active-publication
boundary — superseded records are never exported.

Filenames derive from ``project_id`` plus fixed literals only; no user-supplied
text reaches headers (plan §17).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.version import get_app_version
from app.domain.prisma_flow import PrismaFlowModel
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.repositories.project_repository import (
    ProjectNotFoundError as ProjectRepoNotFoundError,
)
from app.services.export.bibtex_writer import render_bibtex
from app.services.export.ris_writer import render_ris
from app.services.export.xlsx_workbook import build_research_matrix_workbook
from app.services.export_dataset_service import (
    ExportDatasetService,
    default_export_dataset_service,
)

router = APIRouter(prefix="/projects", tags=["exports"])

BIBTEX_MEDIA_TYPE = "application/x-bibtex"
RIS_MEDIA_TYPE = "application/x-research-info-systems"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SVG_MEDIA_TYPE = "image/svg+xml"
PDF_MEDIA_TYPE = "application/pdf"


def get_export_dataset_service() -> ExportDatasetService:
    return default_export_dataset_service()


def _attachment_response(
    content: str | bytes,
    media_type: str,
    filename: str,
    project_id: str | None = None,
    service: ExportDatasetService | None = None,
) -> Response:
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Application-Version": get_app_version(),
        "X-Generated-At": datetime.now(timezone.utc).isoformat(),
    }
    if project_id:
        headers["X-Project-Id"] = project_id
        if service is not None:
            project = service.get_project(project_id)
            if project is not None and getattr(project, "protocol_version", None):
                headers["X-Protocol-Version"] = str(project.protocol_version)
    return Response(
        content=content,
        media_type=media_type,
        headers=headers,
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
        project_id=project_id,
        service=service,
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
        project_id=project_id,
        service=service,
    )


@router.get(
    "/{project_id}/exports/xlsx",
    summary="Export the research matrix workbook (.xlsx)",
    description=(
        "Returns a multi-sheet XLSX research matrix assembled from persisted "
        "project state: active canonical publications, latest screening "
        "decisions, quality-assessment profiles, the COMPLETE extraction "
        "dataset, approved synthesis relations, and an authoritative PRISMA "
        "summary. Stages without persisted rows are emitted as header-only "
        "sheets. Read-only: the project state is not modified."
    ),
)
def export_xlsx(
    project_id: str,
    reviewer_id: str = Query(default="default_reviewer"),
    service: ExportDatasetService = Depends(get_export_dataset_service),
) -> Response:
    try:
        payload = build_research_matrix_workbook(service, project_id, reviewer_id=reviewer_id)
    except (ProjectNotFoundError, ProjectRepoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _attachment_response(
        payload,
        XLSX_MEDIA_TYPE,
        f"{project_id}_publications.xlsx",
        project_id=project_id,
        service=service,
    )


@router.get(
    "/{project_id}/prisma/flow",
    response_model=PrismaFlowModel,
    summary="Get presentation-neutral PRISMA 2020 flow model",
    description=(
        "Returns the presentation-neutral PRISMA 2020 flow model containing "
        "stage nodes, flow edges, audit metadata, and presentation-derived exclusions "
        "(duplicates removed, stage exclusions). Read-only: project state is not modified."
    ),
)
def get_prisma_flow(
    project_id: str,
    response: Response = Response(),
    reviewer_id: str = Query(default="default_reviewer"),
    service: ExportDatasetService = Depends(get_export_dataset_service),
) -> PrismaFlowModel:
    try:
        model = service.get_prisma_flow_model(project_id, reviewer_id=reviewer_id)
    except (ProjectNotFoundError, ProjectRepoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if response is not None:
        response.headers["X-Project-Id"] = project_id
        response.headers["X-Application-Version"] = get_app_version()
        response.headers["X-Generated-At"] = datetime.now(timezone.utc).isoformat()
        if model.metadata.protocol_version:
            response.headers["X-Protocol-Version"] = str(model.metadata.protocol_version)
    return model


@router.get(
    "/{project_id}/prisma/flow.svg",
    summary="Export PRISMA 2020 flow diagram as standalone SVG",
    description=(
        "Returns a standalone, printable PRISMA 2020 SVG flow diagram rendered from "
        "the presentation-neutral flow model using authoritative metrics. "
        "Deterministic: repeated calls for identical project state yield byte-identical SVG. "
        "Read-only: project state is not modified."
    ),
)
@router.get(
    "/{project_id}/exports/prisma/flow.svg",
    include_in_schema=False,
)
def export_prisma_svg(
    project_id: str,
    reviewer_id: str = Query(default="default_reviewer"),
    service: ExportDatasetService = Depends(get_export_dataset_service),
) -> Response:
    try:
        svg_content = service.get_prisma_svg(project_id, reviewer_id=reviewer_id)
    except (ProjectNotFoundError, ProjectRepoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _attachment_response(
        svg_content,
        SVG_MEDIA_TYPE,
        f"{project_id}_prisma_flow.svg",
        project_id=project_id,
        service=service,
    )


@router.get(
    "/{project_id}/prisma/flow.pdf",
    summary="Export PRISMA 2020 flow diagram as standalone PDF",
    description=(
        "Returns a standalone, printable PRISMA 2020 PDF flow diagram rendered from "
        "the presentation-neutral flow model using authoritative metrics and embedded "
        "Unicode fonts for selectable multilingual text. "
        "Read-only: project state is not modified."
    ),
)
@router.get(
    "/{project_id}/exports/prisma/flow.pdf",
    include_in_schema=False,
)
def export_prisma_pdf(
    project_id: str,
    reviewer_id: str = Query(default="default_reviewer"),
    service: ExportDatasetService = Depends(get_export_dataset_service),
) -> Response:
    try:
        pdf_bytes = service.get_prisma_pdf(project_id, reviewer_id=reviewer_id)
    except (ProjectNotFoundError, ProjectRepoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _attachment_response(
        pdf_bytes,
        PDF_MEDIA_TYPE,
        f"{project_id}_prisma_flow.pdf",
        project_id=project_id,
        service=service,
    )
