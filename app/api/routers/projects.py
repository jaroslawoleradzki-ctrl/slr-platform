import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.domain.project import Project
from app.repositories.project_repository import (
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ProjectRepository,
    default_project_repository,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_repository() -> ProjectRepository:
    return default_project_repository()


def generate_project_id(title: str) -> str:
    """Generate a collision-resistant, human-readable, stable project_id.

    Formula: slug(title) + '-' + short_hex(6).
    Example: 'Lean Management' -> 'lean-management-3a8f9b'.
    """
    clean = title.strip().lower()
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r"[^\w]+", "-", clean)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug).strip("-")

    short_hex = uuid4().hex[:6]
    if not slug:
        return f"project-{short_hex}"
    # Truncate slug to 40 chars max for clean URLs
    return f"{slug[:40]}-{short_hex}"


@router.get(
    "",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List SLR projects",
    description="Returns list of SLR projects. Filter by active vs archived status using include_archived parameter.",
)
def list_projects(
    include_archived: bool = Query(
        default=False, description="Whether to include archived projects."
    ),
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectListResponse:
    projects = repo.list_all(include_archived=include_archived)
    items = [ProjectResponse.from_domain(p) for p in projects]
    return ProjectListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SLR project",
    description="Creates a new SLR project. Generates a stable, collision-resistant project_id server-side.",
)
def create_project(
    payload: ProjectCreateRequest,
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectResponse:
    project_id = generate_project_id(payload.title)
    # Ensure project_id collision safety
    try:
        repo.get(project_id)
        # If by rare chance it exists, generate a new one
        project_id = generate_project_id(payload.title)
    except ProjectNotFoundError:
        pass

    try:
        project = Project(
            project_id=project_id,
            title=payload.title,
            description=payload.description,
            protocol_version=payload.protocol_version,
        )
        saved = repo.create(project)
        return ProjectResponse.from_domain(saved)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ProjectAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project details by ID",
)
def get_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectResponse:
    try:
        project = repo.get(project_id)
        return ProjectResponse.from_domain(project)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project metadata",
    description="Updates title, description, or protocol_version. Project ID remains unchanged.",
)
def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectResponse:
    try:
        updated = repo.update(
            project_id,
            title=payload.title,
            description=payload.description,
            protocol_version=payload.protocol_version,
        )
        return ProjectResponse.from_domain(updated)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a project",
    description="Sets project status to 'archived'. Project data and publications remain untouched.",
)
def archive_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectResponse:
    try:
        archived = repo.archive(project_id)
        return ProjectResponse.from_domain(archived)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{project_id}/restore",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived project",
    description="Sets project status back to 'active'.",
)
def restore_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_project_repository),
) -> ProjectResponse:
    try:
        restored = repo.restore(project_id)
        return ProjectResponse.from_domain(restored)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
