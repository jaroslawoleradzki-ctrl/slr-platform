"""Phase 10: Synthesis-to-Extraction & QA read adapter.

Bridges Phase 9 Extraction revisions and Phase 8 Quality Assessment into
Phase 10 synthesis domain models while enforcing strict traceability and project isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.synthesis import (
    ExtractionEvidenceReference,
    QACriterionAssessmentSummary,
    QAProfileSummary,
)

if TYPE_CHECKING:
    from app.domain.extraction import ExtractionRevision
    from app.repositories.extraction_repository import SqliteExtractionRepository
    from app.repositories.quality_assessment_repository import QualityAssessmentRepository


class SynthesisExtractionAdapter:
    """Read adapter that resolves Phase 9 extraction items and Phase 8 QA assessments."""

    def __init__(
        self,
        extraction_repo: SqliteExtractionRepository,
        qa_repo: QualityAssessmentRepository | None = None,
    ) -> None:
        self._extraction_repo = extraction_repo
        self._qa_repo = qa_repo

    def get_latest_complete_revision(
        self, project_id: str, publication_id: UUID
    ) -> ExtractionRevision | None:
        """Resolves the latest COMPLETE extraction revision for a publication."""
        return self._extraction_repo.get_latest_complete_revision(project_id, publication_id)

    def get_latest_complete_revision_batch(
        self, project_id: str, publication_ids: list[UUID]
    ) -> dict[UUID, ExtractionRevision | None]:
        """Resolves latest COMPLETE extraction revisions across multiple publications."""
        return self._extraction_repo.get_latest_complete_revision_batch(project_id, publication_ids)

    def resolve_relation_traceability(
        self,
        project_id: str,
        publication_id: UUID,
        group_item_id: UUID,
        revision_id: UUID | None = None,
    ) -> ExtractionEvidenceReference:
        """Resolves the exact extraction revision and group item for an analytical relation.

        Enforces project scoping, completeness status on latest resolution, and durable identity validation.
        """
        if revision_id is not None:
            # Check history to find the specific revision
            history = self._extraction_repo.list_revision_history(project_id, publication_id)
            target_rev: ExtractionRevision | None = next((r for r in history if r.revision_id == revision_id), None)
            if target_rev is None:
                raise ValueError(
                    f"Extraction revision '{revision_id}' not found for publication '{publication_id}' in project '{project_id}'"
                )
        else:
            target_rev = self._extraction_repo.get_latest_complete_revision(project_id, publication_id)
            if target_rev is None:
                raise ValueError(
                    f"No extraction revisions found for publication '{publication_id}' in project '{project_id}'"
                )

        if target_rev.project_id != project_id:
            raise ValueError(
                f"Cross-project isolation violation: revision belongs to '{target_rev.project_id}', not '{project_id}'"
            )

        target_item = next((item for item in target_rev.group_items if item.group_item_id == group_item_id), None)
        if target_item is None:
            raise ValueError(f"Group item '{group_item_id}' not found in revision '{target_rev.revision_id}'")

        return ExtractionEvidenceReference(
            project_id=project_id,
            publication_id=publication_id,
            revision_id=target_rev.revision_id,
            group_key=target_item.group_key,
            group_item_id=target_item.group_item_id,
        )

    def resolve_publication_evidence_traceability(
        self,
        project_id: str,
        publication_id: UUID,
        field_key: str,
        revision_id: UUID | None = None,
    ) -> ExtractionEvidenceReference:
        """Resolves publication-level extracted value evidence reference."""
        if revision_id is not None:
            history = self._extraction_repo.list_revision_history(project_id, publication_id)
            target_rev = next((r for r in history if r.revision_id == revision_id), None)
            if target_rev is None:
                raise ValueError(
                    f"Extraction revision '{revision_id}' not found for publication '{publication_id}' in project '{project_id}'"
                )
        else:
            target_rev = self._extraction_repo.get_latest_complete_revision(project_id, publication_id)
            if target_rev is None:
                raise ValueError(
                    f"No extraction revisions found for publication '{publication_id}' in project '{project_id}'"
                )

        if target_rev.project_id != project_id:
            raise ValueError(
                f"Cross-project isolation violation: revision belongs to '{target_rev.project_id}', not '{project_id}'"
            )

        target_val = next((val for val in target_rev.publication_values if val.field_key == field_key), None)
        if target_val is None:
            raise ValueError(
                f"Field '{field_key}' not found in publication values of revision '{target_rev.revision_id}'"
            )

        return ExtractionEvidenceReference(
            project_id=project_id,
            publication_id=publication_id,
            revision_id=target_rev.revision_id,
            group_key=None,
            group_item_id=None,
            field_key=field_key,
        )

    def get_qa_profile_summary(
        self,
        project_id: str,
        publication_id: UUID,
        reviewer_id: str = "",
    ) -> QAProfileSummary | None:
        """Retrieves and aggregates Phase 8 QA assessment for a publication into a synthesis profile summary."""
        if self._qa_repo is None:
            return None

        assessment = self._qa_repo.get_latest_assessment(project_id, publication_id, reviewer_id=reviewer_id)
        if assessment is None:
            return None

        criteria_summaries = [
            QACriterionAssessmentSummary(
                criterion_id=resp.criterion_id,
                question_text=resp.question_snapshot,
                response_value=resp.response_value.value
                if hasattr(resp.response_value, "value")
                else str(resp.response_value),
                justification=resp.justification,
            )
            for resp in assessment.responses
        ]

        return QAProfileSummary(
            assessment_id=assessment.assessment_id,
            template_id=assessment.template_id,
            reviewer_id=assessment.reviewer_id,
            criteria_assessments=criteria_summaries,
        )
