from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.conflict_resolution import ConflictResolution, ResolvedOutcome
from app.domain.screening import ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService, ScreeningConflictStatus


class ConflictResolutionStaleError(Exception):
    def __init__(self, expected_key: str, current_key: str) -> None:
        self.expected_key, self.current_key = expected_key, current_key
        super().__init__("Reviewer decisions have changed since you loaded this conflict.")


class ConflictResolutionPublicationNotFoundError(Exception):
    pass


class ConflictResolutionService:
    def __init__(
        self,
        multi_reviewer: MultiReviewerScreeningService | None = None,
        repository: SqliteConflictResolutionRepository | None = None,
    ) -> None:
        self._multi = multi_reviewer or MultiReviewerScreeningService()
        self._repository = repository or self._multi._resolutions

    def resolve(
        self,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        outcome: ResolvedOutcome,
        resolver_id: str,
        rationale: str,
        expected_key: str,
    ) -> ConflictResolution:
        resolver_id, rationale = resolver_id.strip(), rationale.strip()
        if not resolver_id:
            raise ValueError("resolver_id must not be blank")
        if not rationale:
            raise ValueError("rationale must not be blank")
        input_set = self._multi._input_service.get_input_set(project_id)
        if publication_id not in {item.record_id for item in input_set.publications}:
            raise ConflictResolutionPublicationNotFoundError("Publication is not in the canonical screening input set")
        if not self._multi._assignments.list(project_id, stage, active_only=True):
            raise ValueError("No reviewer roster configured")
        state = self._multi.publication_state(project_id, publication_id, stage, reveal_decisions=True)
        if state is None:
            raise ConflictResolutionPublicationNotFoundError("Publication is not eligible for resolution at this stage")
        if expected_key != state.current_decision_set_key:
            raise ConflictResolutionStaleError(expected_key, state.current_decision_set_key)
        if state.status not in (
            ScreeningConflictStatus.CONFLICT,
            ScreeningConflictStatus.STALE_RESOLUTION,
        ):
            raise ValueError("Publication is not in conflict")
        links = [(d.decision_id, d.reviewer_id, ResolvedOutcome(d.outcome.value)) for d in state.source_decisions]
        value = ConflictResolution(
            uuid4(),
            project_id,
            publication_id,
            stage,
            state.current_decision_set_key,
            outcome,
            resolver_id,
            rationale,
            datetime.now(timezone.utc),
            tuple(d[0] for d in links),
        )
        return self._repository.save(value, links)

    def history(self, project_id: str, publication_id: UUID, stage: ScreeningStage):
        input_set = self._multi._input_service.get_input_set(project_id)
        if publication_id not in {item.record_id for item in input_set.publications}:
            raise ConflictResolutionPublicationNotFoundError("Publication is not in the canonical screening input set")
        state = self._multi.publication_state(project_id, publication_id, stage)
        if state is None:
            raise ConflictResolutionPublicationNotFoundError("Publication is not eligible for resolution at this stage")
        return state.current_decision_set_key, self._repository.history(project_id, publication_id, stage)

    def history_links(self, resolution_ids: list[UUID]):
        return self._repository.links_batch(resolution_ids)
