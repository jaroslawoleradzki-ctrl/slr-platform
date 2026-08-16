"""API Router for Phase 10: Research Gap Synthesis (Task 10.6)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dto.synthesis import (
    CreateResearchGapRequestDTO,
    LinkEvidenceRequestDTO,
    QACriterionAssessmentSummaryDTO,
    QAProfileSummaryDTO,
    ResearchGapDetailDTO,
    ResearchGapDTO,
    ResearchGapEvidenceCandidateDTO,
    ResearchGapLinkDTO,
    ResearchGapWorkspaceDataDTO,
    ResearchGapWorkspaceStatsDTO,
    UpdateResearchGapRequestDTO,
)
from app.domain.synthesis import (
    QAProfileSummary,
    ResearchGap,
    ResearchGapEvidenceCandidate,
    ResearchGapLink,
    ResearchGapLinkType,
)
from app.repositories.project_repository import ProjectNotFoundError
from app.services.synthesis_gap_service import (
    ResearchGapEvidenceError,
    ResearchGapNotFoundError,
    SynthesisGapService,
    default_synthesis_gap_service,
)

router = APIRouter(prefix="/projects/{projectId}/synthesis", tags=["Synthesis Research Gaps"])


def _get_gap_service() -> SynthesisGapService:
    return default_synthesis_gap_service()


def _gap_to_dto(gap: ResearchGap) -> ResearchGapDTO:
    return ResearchGapDTO(
        gap_id=gap.gap_id,
        project_id=gap.project_id,
        gap_type=gap.gap_type.value,
        title=gap.title,
        rationale=gap.rationale,
        researcher_id=gap.researcher_id,
        created_at=gap.created_at,
        updated_at=gap.updated_at,
    )


def _gap_link_to_dto(link: ResearchGapLink) -> ResearchGapLinkDTO:
    return ResearchGapLinkDTO(
        link_id=link.link_id,
        project_id=link.project_id,
        gap_id=link.gap_id,
        link_type=link.link_type.value,
        target_id=link.target_id,
        group_item_id=link.group_item_id,
        publication_id=link.publication_id,
        latest_revision_id=link.latest_revision_id,
        created_at=link.created_at,
    )


def _qa_profile_to_dto(qa: QAProfileSummary | None) -> QAProfileSummaryDTO | None:
    if qa is None:
        return None
    return QAProfileSummaryDTO(
        assessment_id=qa.assessment_id,
        template_id=qa.template_id,
        reviewer_id=qa.reviewer_id,
        criteria_assessments=[
            QACriterionAssessmentSummaryDTO(
                criterion_id=c.criterion_id,
                question_text=c.question_text,
                response_value=c.response_value,
                justification=c.justification,
            )
            for c in qa.criteria_assessments
        ],
    )


def _candidate_to_dto(c: ResearchGapEvidenceCandidate) -> ResearchGapEvidenceCandidateDTO:
    return ResearchGapEvidenceCandidateDTO(
        link_type=c.link_type.value,
        target_id=c.target_id,
        group_item_id=c.group_item_id,
        publication_id=c.publication_id,
        latest_revision_id=c.latest_revision_id,
        traceable=c.traceable,
        label=c.label,
        publication_title=c.publication_title,
        publication_year=c.publication_year,
        qa_profile=_qa_profile_to_dto(c.qa_profile),
    )


def _workspace_to_dto(data: Any) -> ResearchGapWorkspaceDataDTO:
    return ResearchGapWorkspaceDataDTO(
        project_id=data.project_id,
        gaps=[
            ResearchGapDetailDTO(
                gap=_gap_to_dto(detail.gap),
                links=[_gap_link_to_dto(link) for link in detail.links],
            )
            for detail in data.gaps
        ],
        stats=ResearchGapWorkspaceStatsDTO(
            total_gaps=data.stats.total_gaps,
            thematic_count=data.stats.thematic_count,
            mechanism_count=data.stats.mechanism_count,
            methodological_count=data.stats.methodological_count,
            contextual_count=data.stats.contextual_count,
            inconsistent_evidence_count=data.stats.inconsistent_evidence_count,
            linked_publication_count=data.stats.linked_publication_count,
        ),
    )


@router.get("/research-gaps", response_model=ResearchGapWorkspaceDataDTO)
def get_research_gap_workspace(projectId: str):
    """Retrieves the complete research gap synthesis workspace dataset."""
    service = _get_gap_service()
    try:
        data = service.get_research_gap_workspace_data(project_id=projectId)
        return _workspace_to_dto(data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/research-gaps/evidence-candidates", response_model=list[ResearchGapEvidenceCandidateDTO])
def list_evidence_candidates(projectId: str):
    """Lists synthesis artifacts eligible for linking to a research gap."""
    service = _get_gap_service()
    try:
        candidates = service.list_linkable_evidence_candidates(project_id=projectId)
        return [_candidate_to_dto(c) for c in candidates]
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/research-gaps/{gapId}", response_model=ResearchGapDetailDTO)
def get_research_gap(projectId: str, gapId: UUID):
    """Retrieves a single research gap with its evidence links."""
    service = _get_gap_service()
    try:
        gap = service.get_research_gap(project_id=projectId, gap_id=str(gapId))
        if gap is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research gap not found")
        links = service.list_links_for_gap(project_id=projectId, gap_id=str(gapId))
        return ResearchGapDetailDTO(gap=_gap_to_dto(gap), links=[_gap_link_to_dto(link) for link in links])
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/research-gaps", response_model=ResearchGapDTO, status_code=status.HTTP_201_CREATED)
def create_research_gap(projectId: str, req: CreateResearchGapRequestDTO):
    """Creates a new researcher-authored research gap."""
    service = _get_gap_service()
    try:
        gap = service.create_research_gap(
            project_id=projectId,
            gap_type=req.gap_type,
            title=req.title,
            rationale=req.rationale,
            researcher_id=req.researcher_id,
        )
        return _gap_to_dto(gap)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/research-gaps/{gapId}", response_model=ResearchGapDTO)
def update_research_gap(projectId: str, gapId: UUID, req: UpdateResearchGapRequestDTO):
    """Updates an existing research gap."""
    service = _get_gap_service()
    try:
        updated = service.update_research_gap(
            project_id=projectId,
            gap_id=str(gapId),
            gap_type=req.gap_type,
            title=req.title,
            rationale=req.rationale,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research gap not found")
        return _gap_to_dto(updated)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/research-gaps/{gapId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research_gap(projectId: str, gapId: UUID):
    """Deletes a research gap and its evidence links (source evidence is preserved)."""
    service = _get_gap_service()
    try:
        deleted = service.delete_research_gap(project_id=projectId, gap_id=str(gapId))
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research gap not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/research-gaps/{gapId}/links", response_model=ResearchGapLinkDTO, status_code=status.HTTP_201_CREATED
)
def link_evidence(projectId: str, gapId: UUID, req: LinkEvidenceRequestDTO):
    """Links a traceable synthesis artifact as evidence for a research gap."""
    service = _get_gap_service()
    try:
        link_type = ResearchGapLinkType(req.link_type)
        link = service.link_evidence(
            project_id=projectId,
            gap_id=str(gapId),
            link_type=link_type,
            target_id=req.target_id,
        )
        return _gap_link_to_dto(link)
    except (ProjectNotFoundError, ResearchGapNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ResearchGapEvidenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/research-gaps/{gapId}/links/{linkId}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_evidence(projectId: str, gapId: UUID, linkId: UUID):
    """Removes an evidence link from a research gap."""
    service = _get_gap_service()
    try:
        removed = service.unlink_evidence(project_id=projectId, gap_id=str(gapId), link_id=str(linkId))
        if not removed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence link not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
