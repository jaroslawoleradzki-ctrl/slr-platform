from __future__ import annotations

from uuid import UUID

from app.api.dto.pre_screening import (
    ImportedRecordResponse,
    ImportedRecordsPageResponse,
)
from app.domain.pre_screening import (
    PreScreeningDecision,
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.publication import Publication
from app.repositories.pre_screening_decision_repository import (
    PreScreeningDecisionRepository,
    default_pre_screening_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
    default_project_publication_repository,
)


class PreScreeningRecordNotFoundError(LookupError):
    pass


class PreScreeningReviewService:
    """Service providing pre-screening review, search/filter, manual removal, and restore for imported records."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        decision_repository: PreScreeningDecisionRepository | None = None,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._decision_repo = decision_repository or default_pre_screening_decision_repository()

    def list_imported_records(
        self,
        project_id: str,
        import_id: UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> ImportedRecordsPageResponse:
        self._ensure_project(project_id)
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if offset < 0:
            raise ValueError("offset must not be negative")

        total_imported, retained_count, removed_count = self._pub_repo.get_import_counts(
            project_id, import_id
        )

        filtered_count = self._pub_repo.count_import_publications(
            project_id,
            import_id,
            search=search,
            status_filter=status_filter,
        )

        records_with_status = self._pub_repo.get_import_publications(
            project_id,
            import_id,
            search=search,
            status_filter=status_filter,
            offset=offset,
            limit=limit,
        )

        items: list[ImportedRecordResponse] = []
        for pub, status_str in records_with_status:
            status = PreScreeningStatus(status_str)
            latest_decision = None
            if status == PreScreeningStatus.REMOVED:
                latest_decision = self._decision_repo.get_latest_decision(project_id, pub.record_id)
            items.append(
                ImportedRecordResponse.from_domain(
                    publication=pub,
                    project_id=project_id,
                    import_id=import_id,
                    status=status,
                    latest_decision=latest_decision,
                )
            )

        return ImportedRecordsPageResponse(
            project_id=project_id,
            import_id=import_id,
            total=filtered_count,
            offset=offset,
            limit=limit,
            total_imported=total_imported,
            retained_count=retained_count,
            removed_count=removed_count,
            items=items,
        )

    def remove_record(
        self,
        project_id: str,
        import_id: UUID,
        record_id: UUID,
        *,
        reason: PreScreeningRemovalReason,
        notes: str | None = None,
        reviewer_id: str = "default_reviewer",
    ) -> ImportedRecordResponse:
        self._ensure_project(project_id)
        pub = self._find_record(project_id, record_id)

        decision = PreScreeningDecision(
            project_id=project_id,
            record_id=record_id,
            import_id=import_id,
            status=PreScreeningStatus.REMOVED,
            reason=reason,
            notes=notes,
            reviewer_id=reviewer_id,
        )

        self._decision_repo.save_decision(decision)
        self._pub_repo.update_pre_screening_status(project_id, record_id, "removed")

        return ImportedRecordResponse.from_domain(
            publication=pub,
            project_id=project_id,
            import_id=import_id,
            status=PreScreeningStatus.REMOVED,
            latest_decision=decision,
        )

    def restore_record(
        self,
        project_id: str,
        import_id: UUID,
        record_id: UUID,
        *,
        reviewer_id: str = "default_reviewer",
    ) -> ImportedRecordResponse:
        self._ensure_project(project_id)
        pub = self._find_record(project_id, record_id)

        decision = PreScreeningDecision(
            project_id=project_id,
            record_id=record_id,
            import_id=import_id,
            status=PreScreeningStatus.RETAINED,
            reviewer_id=reviewer_id,
        )

        self._decision_repo.save_decision(decision)
        self._pub_repo.update_pre_screening_status(project_id, record_id, "retained")

        return ImportedRecordResponse.from_domain(
            publication=pub,
            project_id=project_id,
            import_id=import_id,
            status=PreScreeningStatus.RETAINED,
            latest_decision=decision,
        )

    def get_import_counts(
        self, project_id: str, import_id: UUID
    ) -> tuple[int, int, int]:
        self._ensure_project(project_id)
        return self._pub_repo.get_import_counts(project_id, import_id)

    def _ensure_project(self, project_id: str) -> None:
        try:
            self._pub_repo.get_publications(project_id)
        except ProjectNotFoundError as exc:
            raise ProjectNotFoundError(project_id) from exc

    def _find_record(self, project_id: str, record_id: UUID) -> Publication:
        pubs = self._pub_repo.get_publications(project_id)
        for pub in pubs:
            if pub.record_id == record_id:
                return pub
        raise PreScreeningRecordNotFoundError(
            f"Record '{record_id}' not found in project '{project_id}'."
        )


def default_pre_screening_review_service() -> PreScreeningReviewService:
    return PreScreeningReviewService()
