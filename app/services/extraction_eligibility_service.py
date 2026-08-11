"""Service for evaluating publication eligibility for Data Extraction (Phase 9.3)."""

from __future__ import annotations

from uuid import UUID

from app.domain.conflict_resolution import PublicationScreeningStatus, ResolvedOutcome
from app.domain.extraction import (
    ExtractionEligibilityResult,
    ExtractionEligibilityStatus,
)
from app.domain.screening import ScreeningOutcome, ScreeningStage
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
    default_extraction_configuration_service,
)
from app.services.multi_reviewer_screening_service import (
    MultiReviewerScreeningService,
)
from app.services.screening_input_service import (
    ScreeningInputService,
)


class ExtractionEligibilityService:
    """Evaluates publication readiness and eligibility for Data Extraction."""

    def __init__(
        self,
        config_service: ExtractionConfigurationService | None = None,
        input_service: ScreeningInputService | None = None,
        multi_reviewer_service: MultiReviewerScreeningService | None = None,
        decisions_repo: ScreeningDecisionRepository | None = None,
        qa_service: object | None = None,
    ) -> None:
        self._config_service = config_service or default_extraction_configuration_service()
        self._input_service = input_service or ScreeningInputService()
        self._multi_reviewer_service = multi_reviewer_service or MultiReviewerScreeningService()
        self._decisions_repo = decisions_repo or default_screening_decision_repository()
        self._qa_service = qa_service

    def evaluate_publication(
        self, project_id: str, publication_id: UUID, reviewer_id: str = ""
    ) -> ExtractionEligibilityResult:
        """Evaluates whether a single publication is eligible for data extraction."""
        # 1. Project Configuration Check
        config = self._config_service.get_configuration(project_id)
        if config is None:
            return ExtractionEligibilityResult(
                publication_id=publication_id,
                status=ExtractionEligibilityStatus.NO_EXTRACTION_CONFIGURATION,
                is_eligible=False,
                reason_details="Project has no active data extraction configuration.",
            )

        # 2. Screening Gate (Full-Text Stage)
        stage = ScreeningStage.FULL_TEXT
        has_roster = self._has_active_roster(project_id, stage)

        if has_roster:
            # Multi-reviewer mode: check project-level screening outcome
            outcome = self._multi_reviewer_service.project_outcome(project_id, publication_id, stage)
            if outcome.status == PublicationScreeningStatus.INCOMPLETE:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_SCREENING_INCOMPLETE,
                    is_eligible=False,
                    reason_details="Full-text screening is incomplete.",
                )
            if outcome.status == PublicationScreeningStatus.CONFLICT:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_SCREENING_CONFLICT,
                    is_eligible=False,
                    reason_details="Full-text screening has an unresolved conflict.",
                )
            if outcome.status == PublicationScreeningStatus.STALE_RESOLUTION:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_SCREENING_STALE_RESOLUTION,
                    is_eligible=False,
                    reason_details="Full-text screening resolution is stale.",
                )
            if outcome.status in (PublicationScreeningStatus.AGREEMENT, PublicationScreeningStatus.RESOLVED):
                if outcome.outcome is ResolvedOutcome.INCLUDE:
                    pass  # Screening Gate Passed!
                elif outcome.outcome is ResolvedOutcome.EXCLUDE:
                    return ExtractionEligibilityResult(
                        publication_id=publication_id,
                        status=ExtractionEligibilityStatus.BLOCKED_SCREENING_EXCLUDED,
                        is_eligible=False,
                        reason_details="Publication was excluded during full-text screening.",
                    )
                elif outcome.outcome is ResolvedOutcome.UNCERTAIN:
                    return ExtractionEligibilityResult(
                        publication_id=publication_id,
                        status=ExtractionEligibilityStatus.BLOCKED_SCREENING_UNCERTAIN,
                        is_eligible=False,
                        reason_details="Publication screening outcome is UNCERTAIN.",
                    )
                else:
                    return ExtractionEligibilityResult(
                        publication_id=publication_id,
                        status=ExtractionEligibilityStatus.BLOCKED_SCREENING_INCOMPLETE,
                        is_eligible=False,
                        reason_details="Full-text screening outcome is not INCLUDE.",
                    )
        else:
            # Single-reviewer mode: check latest decision for reviewer_id
            decisions = self._decisions_repo.list_by_project(project_id, stage)
            reviewer_decisions = [
                d for d in decisions if d.publication_id == publication_id and (not reviewer_id or d.reviewer_id == reviewer_id)
            ]
            if not reviewer_decisions:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_SCREENING_INCOMPLETE,
                    is_eligible=False,
                    reason_details="No full-text screening decision exists for this publication.",
                )
            latest = max(reviewer_decisions, key=lambda d: (d.decided_at, str(d.decision_id)))
            if latest.outcome is ScreeningOutcome.INCLUDE:
                pass  # Screening Gate Passed!
            elif latest.outcome is ScreeningOutcome.EXCLUDE:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_SCREENING_EXCLUDED,
                    is_eligible=False,
                    reason_details="Publication was excluded during full-text screening.",
                )
            elif latest.outcome is ScreeningOutcome.UNCERTAIN:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_SCREENING_UNCERTAIN,
                    is_eligible=False,
                    reason_details="Full-text screening decision is UNCERTAIN.",
                )

        # 3. Quality Assessment Gate
        if self._qa_service is not None and getattr(self._qa_service, "is_qa_configured", lambda p: False)(project_id):
            is_qa_complete = getattr(self._qa_service, "is_qa_completed", lambda p, pub, rev: True)(
                project_id, publication_id, reviewer_id
            )
            if not is_qa_complete:
                return ExtractionEligibilityResult(
                    publication_id=publication_id,
                    status=ExtractionEligibilityStatus.BLOCKED_QA_INCOMPLETE,
                    is_eligible=False,
                    reason_details="Quality Assessment is incomplete for this publication.",
                )

        # 4. All Gates Passed!
        return ExtractionEligibilityResult(
            publication_id=publication_id,
            status=ExtractionEligibilityStatus.ELIGIBLE,
            is_eligible=True,
        )

    def get_eligible_publications(
        self, project_id: str, reviewer_id: str = ""
    ) -> list[ExtractionEligibilityResult]:
        """Returns batched eligibility evaluation for all publications in a project."""
        input_set = self._input_service.get_input_set(project_id)
        if not input_set.ready:
            return []

        results: list[ExtractionEligibilityResult] = []
        for pub in input_set.publications:
            res = self.evaluate_publication(project_id, pub.record_id, reviewer_id=reviewer_id)
            results.append(res)
        return results

    def _has_active_roster(self, project_id: str, stage: ScreeningStage) -> bool:
        roster = self._multi_reviewer_service.roster(project_id, stage)
        return roster is not None and len(roster) > 0


def default_extraction_eligibility_service() -> ExtractionEligibilityService:
    return ExtractionEligibilityService()
