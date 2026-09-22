from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.corpus_finalization import (
    CorpusFinalization,
    CorpusFinalizationMember,
    CorpusRecordDisposition,
    PreparedCorpusProvider,
    PreparedCorpusRecord,
    count_prepared_corpus,
)
from app.repositories.corpus_finalization_repository import (
    CorpusFinalizationRepository,
    default_corpus_finalization_repository,
)
from app.repositories.pre_screening_decision_repository import (
    PreScreeningDecisionRepository,
    default_pre_screening_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)


class PublicationPreparedCorpusProvider:
    """Adapts ProjectPublicationRepository and PreScreeningDecisionRepository to PreparedCorpusProvider."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository,
        decision_repository: PreScreeningDecisionRepository,
    ) -> None:
        self._pub_repo = publication_repository
        self._decision_repo = decision_repository

    def prepared_records(self, project_id: str) -> tuple[PreparedCorpusRecord, ...]:
        all_pubs = self._pub_repo.get_publications(project_id)
        superseded_map = self._pub_repo.get_superseded_by_map(project_id)
        canonical_pubs = [p for p in all_pubs if superseded_map.get(p.record_id) is None]

        records: list[PreparedCorpusRecord] = []
        for pub in canonical_pubs:
            # Check pre-screening status
            status_str = "retained"
            if hasattr(self._pub_repo, "_pre_screening_statuses"):
                # in-memory demo repo
                status_str = self._pub_repo._pre_screening_statuses.get((project_id, pub.record_id), "retained")
            else:
                # SQLite repo: read document/row pre_screening_status
                # We can check from latest pre_screening_decision or by querying repo
                latest_decision = self._decision_repo.get_latest_decision(project_id, pub.record_id)
                if latest_decision:
                    status_str = latest_decision.status.value

            provenance_tags = tuple(entry.source for entry in pub.provenance) if pub.provenance else ()
            if status_str == "removed":
                latest_decision = self._decision_repo.get_latest_decision(project_id, pub.record_id)
                reason = (
                    latest_decision.reason.value
                    if latest_decision and latest_decision.reason
                    else "pre_screening_removal"
                )
                records.append(
                    PreparedCorpusRecord(
                        record_id=pub.record_id,
                        disposition=CorpusRecordDisposition.REMOVED_DURING_PRE_SCREENING,
                        provenance=provenance_tags,
                        removal_reason=reason,
                    )
                )
            else:
                records.append(
                    PreparedCorpusRecord(
                        record_id=pub.record_id,
                        disposition=CorpusRecordDisposition.RETAINED_FOR_SCREENING,
                        provenance=provenance_tags,
                        removal_reason=None,
                    )
                )

        return tuple(records)


class CorpusFinalizationService:
    """Orchestrates atomic corpus finalization and screening population freeze."""

    def __init__(
        self,
        finalization_repository: CorpusFinalizationRepository | None = None,
        publication_repository: ProjectPublicationRepository | None = None,
        decision_repository: PreScreeningDecisionRepository | None = None,
        prepared_corpus_provider: PreparedCorpusProvider | None = None,
    ) -> None:
        self._finalization_repo = finalization_repository or default_corpus_finalization_repository()
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._decision_repo = decision_repository or default_pre_screening_decision_repository()
        self._provider = prepared_corpus_provider or PublicationPreparedCorpusProvider(
            self._pub_repo, self._decision_repo
        )

    def is_finalized(self, project_id: str) -> bool:
        return self._finalization_repo.get_latest_finalization(project_id) is not None

    def get_finalization(self, project_id: str) -> CorpusFinalization | None:
        return self._finalization_repo.get_latest_finalization(project_id)

    def get_finalization_members(self, finalization_id: UUID) -> list[CorpusFinalizationMember]:
        return self._finalization_repo.get_finalization_members(finalization_id)

    def get_admitted_record_ids(self, project_id: str) -> set[UUID]:
        return self._finalization_repo.get_admitted_record_ids(project_id)

    def finalize_corpus(
        self,
        project_id: str,
        *,
        finalized_by: str = "default_reviewer",
    ) -> CorpusFinalization:
        """Atomically finalize prepared corpus for Screening.

        Idempotent: if the project is already finalized, returns the existing
        finalization event without modifying members.
        """
        # Idempotency check: return existing finalization if already finalized
        existing = self._finalization_repo.get_latest_finalization(project_id)
        if existing is not None:
            return existing

        all_pubs = self._pub_repo.get_publications(project_id)
        source_records_count = len(all_pubs)

        superseded_map = self._pub_repo.get_superseded_by_map(project_id)
        duplicates_removed_count = sum(1 for sup in superseded_map.values() if sup is not None)

        prepared = self._provider.prepared_records(project_id)
        counts = count_prepared_corpus(
            prepared,
            source_records=source_records_count,
            duplicates_removed=duplicates_removed_count,
        )

        finalization_id = uuid4()
        now = datetime.now(timezone.utc)

        members: list[CorpusFinalizationMember] = []
        for rec in prepared:
            admitted = rec.disposition is CorpusRecordDisposition.RETAINED_FOR_SCREENING
            members.append(
                CorpusFinalizationMember(
                    finalization_id=finalization_id,
                    record_id=rec.record_id,
                    disposition=rec.disposition,
                    removal_reason=rec.removal_reason,
                    admitted_to_screening=admitted,
                )
            )

        finalization = CorpusFinalization(
            finalization_id=finalization_id,
            project_id=project_id,
            finalized_by=finalized_by,
            created_at=now,
            source_records_count=counts.source_records,
            duplicates_removed_count=counts.duplicates_removed,
            prescreening_removed_count=counts.pre_screening_removed,
            retained_count=counts.retained_for_screening,
            status="finalized",
        )

        self._finalization_repo.save_finalization(finalization, members)
        return finalization


def default_corpus_finalization_service() -> CorpusFinalizationService:
    return CorpusFinalizationService()
