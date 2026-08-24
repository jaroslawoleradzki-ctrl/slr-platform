from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.publication import Publication
from app.domain.quality_assessment import (
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
)
from app.domain.screening import ScreeningOutcome, ScreeningStage
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.project_repository import ProjectRepository, default_project_repository
from app.repositories.quality_assessment_repository import (
    ProjectQualityAssessmentConfigurationRepository,
    QualityAssessmentCatalogRepository,
    QualityAssessmentRepository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    default_project_quality_assessment_configuration_repository,
    default_quality_assessment_catalog_repository,
    default_quality_assessment_repository,
)


class QualityAssessmentReadinessStatus(StrEnum):
    READY = "ready"
    NO_QUALITY_ASSESSMENT_CONFIGURATION = "no_quality_assessment_configuration"
    NO_ELIGIBLE_PUBLICATIONS = "no_eligible_publications"


class QualityAssessmentStatusFilter(StrEnum):
    ALL = "all"
    UNASSESSED = "unassessed"
    ASSESSED = "assessed"


class PublicationNotEligibleForQualityAssessmentError(Exception):
    def __init__(self, project_id: str, publication_id: UUID, reviewer_id: str) -> None:
        self.project_id = project_id
        self.publication_id = publication_id
        self.reviewer_id = reviewer_id
        super().__init__(
            f"Publication '{publication_id}' is not currently eligible for Quality Assessment by reviewer '{reviewer_id}' in project '{project_id}'."
        )


class PublicationNotFoundError(Exception):
    def __init__(self, publication_id: UUID | str, project_id: str) -> None:
        self.publication_id = str(publication_id)
        self.project_id = project_id
        super().__init__(f"Publication '{self.publication_id}' not found in project '{self.project_id}'.")


class NoQualityAssessmentConfigurationError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(
            f"Project '{project_id}' does not have an active Quality Assessment configuration."
        )


class MissingRequiredQualityCriterionResponseError(Exception):
    def __init__(self, criterion_id: UUID, question: str) -> None:
        self.criterion_id = criterion_id
        self.question = question
        super().__init__(
            f"Response required for criterion '{criterion_id}' ('{question}')."
        )


class CriterionResponseInput(BaseModel):
    """Input payload for a single criterion response when saving a Quality Assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    response_value: QualityAssessmentResponseValue
    justification: str = ""


class QualityAssessmentOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness: QualityAssessmentReadinessStatus
    tool_id: str | None = None
    template_id: UUID | None = None
    template_version: int | None = None
    total_eligible: int = 0
    total_assessed: int = 0
    total_remaining: int = 0


class EligiblePublicationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication: Publication
    has_assessment: bool
    latest_assessment: QualityAssessment | None = None


class QualityAssessmentRecordList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[EligiblePublicationRecord]
    total: int
    page: int
    page_size: int
    total_pages: int


class QualityAssessmentRecordDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    publication: Publication
    reviewer_id: str
    is_currently_eligible: bool
    template: QualityAssessmentTemplate
    latest_assessment: QualityAssessment | None = None
    history: list[QualityAssessment] = Field(default_factory=list)


@runtime_checkable
class QualityAssessmentExecutionService(Protocol):
    """Service protocol for executing Quality Assessment workflow."""

    def check_readiness(self, project_id: str, reviewer_id: str) -> QualityAssessmentReadinessStatus: ...

    def get_overview(self, project_id: str, reviewer_id: str) -> QualityAssessmentOverview: ...

    def list_eligible_records(
        self,
        project_id: str,
        reviewer_id: str,
        status_filter: QualityAssessmentStatusFilter = QualityAssessmentStatusFilter.ALL,
        page: int = 1,
        page_size: int = 20,
    ) -> QualityAssessmentRecordList: ...

    def get_record_detail(
        self, project_id: str, publication_id: UUID, reviewer_id: str
    ) -> QualityAssessmentRecordDetail: ...

    def save_assessment(
        self,
        project_id: str,
        publication_id: UUID,
        reviewer_id: str,
        response_inputs: list[CriterionResponseInput],
    ) -> QualityAssessment: ...

    def get_assessment_history(
        self, project_id: str, publication_id: UUID, reviewer_id: str
    ) -> list[QualityAssessment]: ...


class DefaultQualityAssessmentExecutionService:
    def __init__(
        self,
        project_repo: ProjectRepository | None = None,
        publication_repo: ProjectPublicationRepository | None = None,
        screening_decision_repo: ScreeningDecisionRepository | None = None,
        catalog_repo: QualityAssessmentCatalogRepository | None = None,
        config_repo: ProjectQualityAssessmentConfigurationRepository | None = None,
        quality_assessment_repo: QualityAssessmentRepository | None = None,
    ) -> None:
        self._project_repo = project_repo or default_project_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._screening_decision_repo = screening_decision_repo or default_screening_decision_repository()
        self._catalog_repo = catalog_repo or default_quality_assessment_catalog_repository()
        self._config_repo = (
            config_repo or default_project_quality_assessment_configuration_repository()
        )
        self._quality_assessment_repo = (
            quality_assessment_repo or default_quality_assessment_repository()
        )

    def _get_eligible_publication_ids(self, project_id: str, reviewer_id: str) -> list[UUID]:
        """Finds publication_ids where reviewer_id's latest FULL_TEXT decision outcome == INCLUDE."""
        decisions = self._screening_decision_repo.list_by_project(
            project_id=project_id, stage=ScreeningStage.FULL_TEXT
        )
        # Filter for decisions by reviewer_id and find latest per publication
        eligible_pub_ids: set[UUID] = set()

        # Sort by decided_at ASC so later decisions overwrite earlier ones
        sorted_decisions = sorted(decisions, key=lambda d: d.decided_at)
        for d in sorted_decisions:
            if d.reviewer_id == reviewer_id:
                if d.outcome == ScreeningOutcome.INCLUDE:
                    eligible_pub_ids.add(d.publication_id)
                else:
                    eligible_pub_ids.discard(d.publication_id)

        active_ids = {
            publication.record_id
            for publication in (
                self._publication_repo.get_active_publications(project_id)
                if hasattr(self._publication_repo, "get_active_publications")
                else self._publication_repo.get_publications(project_id)
            )
        }
        return sorted(eligible_pub_ids & active_ids, key=lambda u: str(u))

    def check_readiness(self, project_id: str, reviewer_id: str) -> QualityAssessmentReadinessStatus:
        _ = self._project_repo.get(project_id)
        config = self._config_repo.get_configuration(project_id)
        if config is None:
            return QualityAssessmentReadinessStatus.NO_QUALITY_ASSESSMENT_CONFIGURATION

        eligible_ids = self._get_eligible_publication_ids(project_id, reviewer_id)
        if not eligible_ids:
            return QualityAssessmentReadinessStatus.NO_ELIGIBLE_PUBLICATIONS

        return QualityAssessmentReadinessStatus.READY

    def get_overview(self, project_id: str, reviewer_id: str) -> QualityAssessmentOverview:
        _ = self._project_repo.get(project_id)
        config = self._config_repo.get_configuration(project_id)
        if config is None:
            return QualityAssessmentOverview(
                readiness=QualityAssessmentReadinessStatus.NO_QUALITY_ASSESSMENT_CONFIGURATION
            )

        template = self._catalog_repo.get_template_version(config.template_id)
        eligible_ids = self._get_eligible_publication_ids(project_id, reviewer_id)
        if not eligible_ids:
            return QualityAssessmentOverview(
                readiness=QualityAssessmentReadinessStatus.NO_ELIGIBLE_PUBLICATIONS,
                tool_id=config.tool_id,
                template_id=config.template_id,
                template_version=template.version if template else None,
            )

        assessed_count = 0
        for pub_id in eligible_ids:
            latest = self._quality_assessment_repo.get_latest_assessment(
                project_id, pub_id, reviewer_id
            )
            if latest is not None:
                assessed_count += 1

        total_eligible = len(eligible_ids)
        total_remaining = total_eligible - assessed_count

        return QualityAssessmentOverview(
            readiness=QualityAssessmentReadinessStatus.READY,
            tool_id=config.tool_id,
            template_id=config.template_id,
            template_version=template.version if template else None,
            total_eligible=total_eligible,
            total_assessed=assessed_count,
            total_remaining=total_remaining,
        )

    def list_eligible_records(
        self,
        project_id: str,
        reviewer_id: str,
        status_filter: QualityAssessmentStatusFilter = QualityAssessmentStatusFilter.ALL,
        page: int = 1,
        page_size: int = 20,
    ) -> QualityAssessmentRecordList:
        _ = self._project_repo.get(project_id)
        eligible_ids = self._get_eligible_publication_ids(project_id, reviewer_id)

        all_publications = (
            self._publication_repo.get_active_publications(project_id)
            if hasattr(self._publication_repo, "get_active_publications")
            else self._publication_repo.get_publications(project_id)
        )
        pub_map = {p.record_id: p for p in all_publications}

        records: list[EligiblePublicationRecord] = []
        for pub_id in eligible_ids:
            pub = pub_map.get(pub_id)
            if pub is None:
                continue

            latest = self._quality_assessment_repo.get_latest_assessment(
                project_id, pub_id, reviewer_id
            )
            has_assessed = latest is not None

            if status_filter == QualityAssessmentStatusFilter.ASSESSED and not has_assessed:
                continue
            if status_filter == QualityAssessmentStatusFilter.UNASSESSED and has_assessed:
                continue

            records.append(
                EligiblePublicationRecord(
                    publication=pub,
                    has_assessment=has_assessed,
                    latest_assessment=latest,
                )
            )

        total = len(records)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        safe_page = max(1, min(page, total_pages))
        start_idx = (safe_page - 1) * page_size
        end_idx = start_idx + page_size
        items = records[start_idx:end_idx]

        return QualityAssessmentRecordList(
            items=items,
            total=total,
            page=safe_page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_record_detail(
        self, project_id: str, publication_id: UUID, reviewer_id: str
    ) -> QualityAssessmentRecordDetail:
        _ = self._project_repo.get(project_id)
        config = self._config_repo.get_configuration(project_id)
        if config is None:
            raise NoQualityAssessmentConfigurationError(project_id)

        template = self._catalog_repo.get_template_version(config.template_id)
        if template is None:
            raise RuntimeError(f"Configured template '{config.template_id}' not found in catalog.")

        all_publications = (
            self._publication_repo.get_active_publications(project_id)
            if hasattr(self._publication_repo, "get_active_publications")
            else self._publication_repo.get_publications(project_id)
        )
        pub_map = {p.record_id: p for p in all_publications}
        if publication_id not in pub_map:
            raise PublicationNotFoundError(publication_id, project_id)
        pub = pub_map[publication_id]

        eligible_ids = self._get_eligible_publication_ids(project_id, reviewer_id)
        is_eligible = publication_id in eligible_ids

        latest = self._quality_assessment_repo.get_latest_assessment(
            project_id, publication_id, reviewer_id
        )
        history = self._quality_assessment_repo.list_assessments_for_publication(
            project_id, publication_id, reviewer_id
        )

        return QualityAssessmentRecordDetail(
            project_id=project_id,
            publication=pub,
            reviewer_id=reviewer_id,
            is_currently_eligible=is_eligible,
            template=template,
            latest_assessment=latest,
            history=history,
        )

    def save_assessment(
        self,
        project_id: str,
        publication_id: UUID,
        reviewer_id: str,
        response_inputs: list[CriterionResponseInput],
    ) -> QualityAssessment:
        # 1. Verify project
        _ = self._project_repo.get(project_id)

        # 2. Verify current eligibility
        eligible_ids = self._get_eligible_publication_ids(project_id, reviewer_id)
        if publication_id not in eligible_ids:
            raise PublicationNotEligibleForQualityAssessmentError(
                project_id, publication_id, reviewer_id
            )

        # 3. Verify active configuration
        config = self._config_repo.get_configuration(project_id)
        if config is None:
            raise NoQualityAssessmentConfigurationError(project_id)

        template = self._catalog_repo.get_template_version(config.template_id)
        if template is None:
            raise RuntimeError(f"Configured template '{config.template_id}' not found in catalog.")

        # 4. Validate completeness and correctness of inputs
        criteria_map = {c.criterion_id: c for c in template.criteria}
        input_map: dict[UUID, CriterionResponseInput] = {}
        for inp in response_inputs:
            if inp.criterion_id in input_map:
                raise ValueError(f"Duplicate response input for criterion_id '{inp.criterion_id}'")
            if inp.criterion_id not in criteria_map:
                raise ValueError(
                    f"Criterion '{inp.criterion_id}' does not belong to active assessment template '{template.template_id}'"
                )
            if inp.response_value in (
                QualityAssessmentResponseValue.NO,
                QualityAssessmentResponseValue.CANNOT_DETERMINE,
            ) and not inp.justification.strip():
                raise ValueError(
                    f"Non-blank justification required for criterion '{inp.criterion_id}' with response '{inp.response_value.value}'"
                )
            input_map[inp.criterion_id] = inp

        # Check required criteria
        for criterion in template.criteria:
            if criterion.is_required and criterion.criterion_id not in input_map:
                raise MissingRequiredQualityCriterionResponseError(
                    criterion.criterion_id, criterion.question
                )

        # 5. Build responses with authoritative snapshots
        now = datetime.now(timezone.utc)
        assessment_id = uuid4()

        responses: list[QualityAssessmentResponse] = []
        for criterion in template.criteria:
            if criterion.criterion_id in input_map:
                inp = input_map[criterion.criterion_id]
                responses.append(
                    QualityAssessmentResponse(
                        assessment_id=assessment_id,
                        criterion_id=criterion.criterion_id,
                        question_snapshot=criterion.question,
                        guidance_snapshot=criterion.guidance,
                        is_required_snapshot=criterion.is_required,
                        response_value=inp.response_value,
                        justification=inp.justification.strip(),
                        created_at=now,
                    )
                )

        assessment = QualityAssessment(
            assessment_id=assessment_id,
            project_id=project_id,
            publication_id=publication_id,
            reviewer_id=reviewer_id,
            template_id=template.template_id,
            responses=responses,
            assessed_at=now,
        )

        return self._quality_assessment_repo.save_assessment(assessment)

    def get_assessment_history(
        self, project_id: str, publication_id: UUID, reviewer_id: str
    ) -> list[QualityAssessment]:
        _ = self._project_repo.get(project_id)
        return self._quality_assessment_repo.list_assessments_for_publication(
            project_id, publication_id, reviewer_id
        )


def default_quality_assessment_execution_service() -> DefaultQualityAssessmentExecutionService:
    return DefaultQualityAssessmentExecutionService()
