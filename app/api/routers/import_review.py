from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.import_review import (
    ImportReviewBlockerResponse,
    ImportReviewDecisionRequest,
    ImportReviewDecisionResponse,
    ImportReviewDecisionSummary,
    ImportReviewDetailResponse,
    ImportWarningCategoryResponse,
)
from app.repositories.import_review_repository import ImportReviewConflictError
from app.services.import_review_service import (
    ImportNotFoundError,
    ImportRejectionBlockedError,
    ImportRejectionConfirmationRequired,
    ImportReviewDetail,
    ImportReviewService,
    ImportReviewStateError,
)

router = APIRouter(prefix="/projects", tags=["import-review"])


def get_import_review_service() -> ImportReviewService:
    return ImportReviewService()


def _decision_summary(detail: ImportReviewDetail) -> ImportReviewDecisionSummary | None:
    decision = detail.decision
    if decision is None:
        return None
    return ImportReviewDecisionSummary(
        decision_id=decision.decision_id,
        decision=cast("Literal['accepted', 'rejected']", decision.decision),
        reviewer_id=decision.reviewer_id,
        rationale=decision.rationale,
        decided_at=decision.decided_at,
        deleted_publication_count=decision.deleted_publication_count,
        retained_source_record_count=decision.retained_source_record_count,
        prisma_treatment=decision.prisma_treatment,
    )


def _detail_response(detail: ImportReviewDetail) -> ImportReviewDetailResponse:
    record = detail.record
    return ImportReviewDetailResponse(
        project_id=record.project_id,
        import_id=record.import_id,
        source_type=cast("Literal['provider', 'file']", record.source_type),
        filename=record.filename,
        format=record.format,
        provider=record.provider,
        query=record.query,
        records_count=record.records_count,
        status=record.status,
        effective_status=detail.effective_status,
        review_status=detail.review_status,
        warnings=list(record.warnings),
        created_at=record.created_at,
        source_record_count=detail.source_record_count,
        canonical_publication_count=detail.canonical_publication_count,
        exact_doi_match_count=detail.exact_doi_match_count,
        repeated_source_count=detail.repeated_source_count,
        title_candidate_count=detail.title_candidate_count,
        similar_title_candidate_count=detail.similar_title_candidate_count,
        skipped_canonical_count=detail.skipped_canonical_count,
        invalid_doi_count=detail.invalid_doi_count,
        validation_error_count=detail.validation_error_count,
        audit_available=detail.audit_available,
        can_accept=detail.can_accept,
        can_reject=detail.can_reject,
        warning_categories=[
            ImportWarningCategoryResponse(
                code=category.code, label=category.label, count=category.count
            )
            for category in detail.warning_categories
        ],
        blockers=[
            ImportReviewBlockerResponse(
                code=blocker.code,
                message=blocker.message,
                count=blocker.count,
                publication_ids=list(blocker.publication_ids),
            )
            for blocker in detail.blockers
        ],
        decision=_decision_summary(detail),
    )


def _raise_review_error(exc: Exception) -> None:
    if isinstance(exc, ImportNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found in project.",
        ) from exc
    if isinstance(exc, ImportRejectionBlockedError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_rejection_blocked",
                "message": str(exc),
                "blockers": [
                    {
                        "code": blocker.code,
                        "message": blocker.message,
                        "count": blocker.count,
                        "publication_ids": list(blocker.publication_ids),
                    }
                    for blocker in exc.blockers
                ],
            },
        ) from exc
    if isinstance(exc, ImportReviewConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "import_review_conflict", "message": str(exc)},
        ) from exc
    if isinstance(exc, ImportRejectionConfirmationRequired):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "confirmation_required", "message": str(exc)},
        ) from exc
    if isinstance(exc, ImportReviewStateError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "import_review_state", "message": str(exc)},
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_review_request", "message": str(exc)},
        ) from exc
    raise exc


@router.get(
    "/{project_id}/imports/{import_id}/review",
    response_model=ImportReviewDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect one import warning and its rejection readiness",
)
def get_import_review(
    project_id: str,
    import_id: UUID,
    service: ImportReviewService = Depends(get_import_review_service),
) -> ImportReviewDetailResponse:
    try:
        return _detail_response(service.get_review(project_id, import_id))
    except Exception as exc:
        _raise_review_error(exc)
        raise AssertionError("unreachable") from exc


@router.post(
    "/{project_id}/imports/{import_id}/review",
    response_model=ImportReviewDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record an explicit accept or reject decision for a warning import",
)
def record_import_review(
    project_id: str,
    import_id: UUID,
    payload: ImportReviewDecisionRequest,
    service: ImportReviewService = Depends(get_import_review_service),
) -> ImportReviewDecisionResponse:
    try:
        if payload.decision == "accept":
            decision = service.accept(
                project_id,
                import_id,
                reviewer_id=payload.reviewer_id,
                rationale=payload.rationale,
            )
        else:
            decision = service.reject(
                project_id,
                import_id,
                reviewer_id=payload.reviewer_id,
                rationale=payload.rationale,
                confirm_rejection=payload.confirm_rejection,
            )
        detail = service.get_review(project_id, import_id)
        summary = _decision_summary(detail)
        if summary is None:
            summary = ImportReviewDecisionSummary(
                decision_id=decision.decision_id,
                decision=cast("Literal['accepted', 'rejected']", decision.decision),
                reviewer_id=decision.reviewer_id,
                rationale=decision.rationale,
                decided_at=decision.decided_at,
                deleted_publication_count=decision.deleted_publication_count,
                retained_source_record_count=decision.retained_source_record_count,
                prisma_treatment=decision.prisma_treatment,
            )
        return ImportReviewDecisionResponse(
            project_id=project_id,
            import_id=decision.import_id,
            decision=summary,
            effective_status=detail.effective_status,
            review_status=detail.review_status,
        )
    except Exception as exc:
        _raise_review_error(exc)
        raise AssertionError("unreachable") from exc
