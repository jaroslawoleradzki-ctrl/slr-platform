"""API Router for Data Extraction Project Configuration, Eligibility & Execution (Phase 9.3 & 9.4)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dto.extraction import (
    ExtractedGroupItemStateDTO,
    ExtractedValueStateDTO,
    ExtractionEligibilityListResponseDTO,
    ExtractionEligibilityResultDTO,
    ExtractionMatrixResponseDTO,
    ExtractionMatrixRowDTO,
    ExtractionProgressResponseDTO,
    ExtractionRecordListResponseDTO,
    ExtractionRecordResponseDTO,
    ExtractionRecordSummaryDTO,
    ExtractionRevisionHistoryResponseDTO,
    ExtractionRevisionResponseDTO,
    ExtractionRevisionSubmitRequestDTO,
    ProjectExtractionConfigurationRequestDTO,
    ProjectExtractionConfigurationResponseDTO,
)
from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionConfigurationError,
    ExtractionConfigurationLockedError,
    ExtractionConfigurationNotFoundError,
    ExtractionIneligibleError,
    ExtractionRevision,
    ExtractionTemplateVersion,
    ExtractionValidationError,
    InvalidRevisionError,
    InvalidValueError,
    ValueOrigin,
    ValueStatus,
)
from app.repositories.extraction_template_repository import (
    ExtractionTemplateNotFoundError,
    default_extraction_template_repository,
)
from app.repositories.project_repository import (
    ProjectNotFoundError,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
    default_extraction_configuration_service,
)
from app.services.extraction_dataset_service import (
    ExtractionDatasetService,
    default_extraction_dataset_service,
)
from app.services.extraction_eligibility_service import (
    ExtractionEligibilityService,
    default_extraction_eligibility_service,
)
from app.services.extraction_execution_service import (
    ExtractionExecutionService,
    default_extraction_execution_service,
)

catalog_router = APIRouter(prefix="/extraction-templates", tags=["extraction"])
router = APIRouter(prefix="/projects", tags=["extraction"])


def _get_config_service() -> ExtractionConfigurationService:
    return default_extraction_configuration_service()


def _get_eligibility_service() -> ExtractionEligibilityService:
    return default_extraction_eligibility_service()


def _get_execution_service() -> ExtractionExecutionService:
    return default_extraction_execution_service()


@catalog_router.get(
    "",
    response_model=list[ExtractionTemplateVersion],
    status_code=status.HTTP_200_OK,
    summary="List active published data extraction template versions",
)
def list_extraction_template_versions() -> list[ExtractionTemplateVersion]:
    return default_extraction_template_repository().list_active_published_versions()


@catalog_router.get(
    "/{template_id}/versions/{version}",
    response_model=ExtractionTemplateVersion,
    status_code=status.HTTP_200_OK,
    summary="Get a data extraction template version",
)
def get_extraction_template_version(
    template_id: str, version: str
) -> ExtractionTemplateVersion:
    try:
        template_version = default_extraction_template_repository().get_version(
            template_id, version
        )
    except ExtractionTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not template_version.is_active or not template_version.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction template version '{template_id}' v{version} was not found.",
        )
    return template_version


@router.get(
    "/{project_id}/extraction/configuration",
    response_model=ProjectExtractionConfigurationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get project data extraction configuration",
)
def get_project_extraction_configuration(project_id: str) -> ProjectExtractionConfigurationResponseDTO:
    service = _get_config_service()
    config = service.get_configuration(project_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' has no extraction configuration.",
        )
    return ProjectExtractionConfigurationResponseDTO(
        project_id=config.project_id,
        template_id=config.template_id,
        template_version=config.template_version,
        configured_at=config.configured_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


@router.put(
    "/{project_id}/extraction/configuration",
    response_model=ProjectExtractionConfigurationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Set or update project data extraction configuration",
)
def set_project_extraction_configuration(
    project_id: str, request: ProjectExtractionConfigurationRequestDTO
) -> ProjectExtractionConfigurationResponseDTO:
    service = _get_config_service()
    try:
        config = service.set_configuration(project_id, request.template_id, request.template_version)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExtractionTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExtractionConfigurationLockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return ProjectExtractionConfigurationResponseDTO(
        project_id=config.project_id,
        template_id=config.template_id,
        template_version=config.template_version,
        configured_at=config.configured_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


@router.get(
    "/{project_id}/extraction/eligibility",
    response_model=ExtractionEligibilityListResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get publication eligibility list for data extraction",
)
def get_project_extraction_eligibility(
    project_id: str,
    reviewer_id: str = Query(
        min_length=1,
        description="Reviewer whose Full-Text decision and QA completion gate are evaluated.",
    ),
) -> ExtractionEligibilityListResponseDTO:
    service = _get_eligibility_service()
    results = service.get_eligible_publications(project_id, reviewer_id=reviewer_id)

    dtos = [
        ExtractionEligibilityResultDTO(
            publication_id=r.publication_id,
            status=r.status.value,
            is_eligible=r.is_eligible,
            reason_details=r.reason_details,
        )
        for r in results
    ]
    eligible_count = sum(1 for r in results if r.is_eligible)

    return ExtractionEligibilityListResponseDTO(
        project_id=project_id,
        total_publications=len(results),
        eligible_count=eligible_count,
        items=dtos,
    )


@router.get(
    "/{project_id}/extraction/template",
    response_model=ExtractionTemplateVersion,
    status_code=status.HTTP_200_OK,
    summary="Get the active extraction template version for a project",
)
def get_project_extraction_template(project_id: str) -> ExtractionTemplateVersion:
    config = _get_config_service().get_configuration(project_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' has no extraction configuration.",
        )
    try:
        return default_extraction_template_repository().get_version(
            config.template_id, config.template_version
        )
    except ExtractionTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{project_id}/extraction/records/{publication_id}",
    response_model=ExtractionRecordResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get latest extraction record and revision state for a publication",
)
def get_extraction_record(project_id: str, publication_id: UUID) -> ExtractionRecordResponseDTO:
    service = _get_execution_service()
    record = service.get_record(project_id, publication_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction record for project '{project_id}' and publication '{publication_id}' was not found.",
        )
    latest_rev = service.get_latest_revision(project_id, publication_id)
    latest_dto = _revision_to_dto(latest_rev) if latest_rev else None

    return ExtractionRecordResponseDTO(
        record_id=record.record_id,
        project_id=record.project_id,
        publication_id=record.publication_id,
        template_id=record.template_id,
        template_version=record.template_version,
        current_status=record.current_status.value,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        latest_revision=latest_dto,
    )


@router.post(
    "/{project_id}/extraction/records/{publication_id}/revisions",
    response_model=ExtractionRevisionResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new append-only extraction revision for a publication",
)
def submit_extraction_revision(
    project_id: str, publication_id: UUID, request: ExtractionRevisionSubmitRequestDTO
) -> ExtractionRevisionResponseDTO:
    service = _get_execution_service()

    try:
        pub_values = [_dto_to_value_state(v) for v in request.publication_values]
        group_items = [_dto_to_group_item_state(g) for g in request.group_items]

        revision = service.submit_revision(
            project_id=project_id,
            publication_id=publication_id,
            reviewer_id=request.reviewer_id,
            publication_values=pub_values,
            group_items=group_items,
            mark_complete=request.mark_complete,
        )
    except ExtractionConfigurationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExtractionIneligibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (
        ExtractionValidationError,
        ExtractionConfigurationError,
        InvalidValueError,
        InvalidRevisionError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _revision_to_dto(revision)


@router.get(
    "/{project_id}/extraction/records/{publication_id}/history",
    response_model=ExtractionRevisionHistoryResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get append-only revision history for a publication",
)
def get_extraction_revision_history(project_id: str, publication_id: UUID) -> ExtractionRevisionHistoryResponseDTO:
    service = _get_execution_service()
    record = service.get_record(project_id, publication_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction record for project '{project_id}' and publication '{publication_id}' was not found.",
        )
    history = service.get_revision_history(project_id, publication_id)
    dtos = [_revision_to_dto(rev) for rev in history]

    return ExtractionRevisionHistoryResponseDTO(
        project_id=project_id,
        publication_id=publication_id,
        total_revisions=len(dtos),
        revisions=dtos,
    )


def _dto_to_value_state(dto: ExtractedValueStateDTO) -> ExtractedValueState:
    if dto.value_id is not None:
        return ExtractedValueState(
            value_id=dto.value_id,
            field_key=dto.field_key,
            status=ValueStatus(dto.status),
            origin=ValueOrigin(dto.origin) if dto.origin is not None else None,
            text_value=dto.text_value,
            int_value=dto.int_value,
            float_value=dto.float_value,
            bool_value=dto.bool_value,
            unit_value=dto.unit_value,
            json_value=dto.json_value,
            source_page=dto.source_page,
            source_section=dto.source_section,
            source_locator=dto.source_locator,
            source_quote=dto.source_quote,
            reviewer_note=dto.reviewer_note,
        )
    return ExtractedValueState(
        field_key=dto.field_key,
        status=ValueStatus(dto.status),
        origin=ValueOrigin(dto.origin) if dto.origin is not None else None,
        text_value=dto.text_value,
        int_value=dto.int_value,
        float_value=dto.float_value,
        bool_value=dto.bool_value,
        unit_value=dto.unit_value,
        json_value=dto.json_value,
        source_page=dto.source_page,
        source_section=dto.source_section,
        source_locator=dto.source_locator,
        source_quote=dto.source_quote,
        reviewer_note=dto.reviewer_note,
    )


def _dto_to_group_item_state(dto: ExtractedGroupItemStateDTO) -> ExtractedGroupItemState:
    values = [_dto_to_value_state(v) for v in dto.values]
    if dto.group_item_id is not None:
        return ExtractedGroupItemState(
            group_item_id=dto.group_item_id,
            group_key=dto.group_key,
            item_index=dto.item_index,
            values=values,
        )
    return ExtractedGroupItemState(
        group_key=dto.group_key,
        item_index=dto.item_index,
        values=values,
    )


def _value_state_to_dto(v: ExtractedValueState) -> ExtractedValueStateDTO:
    return ExtractedValueStateDTO(
        value_id=v.value_id,
        field_key=v.field_key,
        status=v.status.value,
        origin=v.origin.value if v.origin is not None else None,
        text_value=v.text_value,
        int_value=v.int_value,
        float_value=v.float_value,
        bool_value=v.bool_value,
        unit_value=v.unit_value,
        json_value=v.json_value,
        source_page=v.source_page,
        source_section=v.source_section,
        source_locator=v.source_locator,
        source_quote=v.source_quote,
        reviewer_note=v.reviewer_note,
    )


def _revision_to_dto(rev: ExtractionRevision) -> ExtractionRevisionResponseDTO:
    pub_vals = [_value_state_to_dto(v) for v in rev.publication_values]
    grp_items = [
        ExtractedGroupItemStateDTO(
            group_item_id=gi.group_item_id,
            group_key=gi.group_key,
            item_index=gi.item_index,
            values=[_value_state_to_dto(v) for v in gi.values],
        )
        for gi in rev.group_items
    ]
    return ExtractionRevisionResponseDTO(
        revision_id=rev.revision_id,
        record_id=rev.record_id,
        project_id=rev.project_id,
        publication_id=rev.publication_id,
        revision_index=rev.revision_index,
        reviewer_id=rev.reviewer_id,
        completeness_status=rev.completeness_status.value,
        publication_values=pub_vals,
        group_items=grp_items,
        created_at=rev.created_at.isoformat(),
    )


@router.get(
    "/{project_id}/extraction/progress",
    response_model=ExtractionProgressResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get project data extraction progress metrics (Phase 9.6)",
)
def get_extraction_progress(
    project_id: str,
    reviewer_id: str = Query(default="", description="Optional reviewer ID filter"),
) -> ExtractionProgressResponseDTO:
    """Returns authoritative project extraction progress metrics and status counts."""
    service = _get_execution_service()
    data = service.get_progress(project_id, reviewer_id=reviewer_id)
    return ExtractionProgressResponseDTO(**data)


@router.get(
    "/{project_id}/extraction/records",
    response_model=ExtractionRecordListResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get eligible publication extraction record summaries (Phase 9.6)",
)
def list_extraction_records(
    project_id: str,
    reviewer_id: str = Query(default="", description="Optional reviewer ID filter"),
) -> ExtractionRecordListResponseDTO:
    """Returns batch-hydrated list of publication extraction record summaries."""
    service = _get_execution_service()
    summaries = service.list_record_summaries(project_id, reviewer_id=reviewer_id)
    items = [ExtractionRecordSummaryDTO(**s) for s in summaries]
    return ExtractionRecordListResponseDTO(
        project_id=project_id,
        total_records=len(items),
        items=items,
    )


@router.get(
    "/{project_id}/extraction/matrix",
    response_model=ExtractionMatrixResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get cross-study repeating group extraction matrix (Phase 9.6)",
)
def get_extraction_matrix(
    project_id: str,
    reviewer_id: str = Query(default="", description="Optional reviewer ID filter"),
) -> ExtractionMatrixResponseDTO:
    """Returns template-driven cross-study matrix for repeating group items across publications."""
    service = _get_execution_service()
    try:
        data = service.get_matrix(project_id, reviewer_id=reviewer_id)
    except ExtractionConfigurationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    items = [
        ExtractionMatrixRowDTO(
            publication_id=row["publication_id"],
            publication_title=row["publication_title"],
            group_key=row["group_key"],
            group_name=row["group_name"],
            group_item_id=row["group_item_id"],
            item_index=row["item_index"],
            values=[_value_state_to_dto(v) for v in row["values"]],
        )
        for row in data["items"]
    ]

    return ExtractionMatrixResponseDTO(
        project_id=data["project_id"],
        template_id=data["template_id"],
        template_version=data["template_version"],
        total_relationships=data["total_relationships"],
        group_keys=data["group_keys"],
        items=items,
    )


def _get_dataset_service() -> ExtractionDatasetService:
    return default_extraction_dataset_service()


@router.get(
    "/{project_id}/extraction/export",
    summary="Export structured extraction dataset (JSON or CSV) (Phase 9.8)",
)
def export_extraction_dataset(
    project_id: str,
    format: str = Query(default="json", description="Export format: 'json' or 'csv'"),
    dataset: str = Query(default="publications", description="Dataset grain: 'publications' or 'relationships'"),
    reviewer_id: str = Query(default="", description="Optional reviewer ID filter"),
    include_all: bool = Query(default=False, description="Set True to include all records regardless of completeness"),
):
    """Exports structured extraction dataset as JSON or CSV based on latest revisions."""
    if format not in ("json", "csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'format' must be either 'json' or 'csv'.",
        )

    if dataset not in ("publications", "relationships"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'dataset' must be either 'publications' or 'relationships'.",
        )

    service = _get_dataset_service()
    status_filter = None if include_all else ExtractionCompletenessStatus.COMPLETE

    try:
        if format == "csv":
            csv_content = service.export_csv(
                project_id, dataset=dataset, reviewer_id=reviewer_id, status_filter=status_filter
            )
            filename = f"{project_id}_{dataset}_dataset.csv"
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:
            json_data = service.export_json(
                project_id, dataset=dataset, reviewer_id=reviewer_id, status_filter=status_filter
            )
            return json_data
    except (ExtractionConfigurationNotFoundError, ProjectNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
