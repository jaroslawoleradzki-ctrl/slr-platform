"""Service for Phase 10: Synthesis Snapshot Business Rules (Task 10.7).

Snapshots are immutable, append-only, researcher-triggered artifacts:
- Creation is always explicit; no automatic snapshotting, no AI/LLM.
- Content reflects the exact synthesis state at creation time (stored content,
  never live pointers to mutable tables).
- Versions are per-project, monotonic, start at 1, and are never reused.
- Hashes are deterministic SHA-256 digests over canonicalized inputs:
  the eligible COMPLETE extraction dataset, the classification rule set /
  QA configuration, and the assembled snapshot content.
- Only eligible COMPLETE extraction revisions contribute to the extraction
  dataset identity (DRAFT is explicitly excluded).
- No update or delete path exists at the application level.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.domain.quality_assessment import ProjectQualityAssessmentConfiguration
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    ContextAssignment,
    ContextCategory,
    MechanismPathway,
    QAProfileSummary,
    ResearchGap,
    ResearchGapLink,
    ResearchGapLinkType,
    ResearchGapType,
    SynthesisSnapshot,
    SynthesisSnapshotContent,
    TermMapping,
    build_extraction_dataset_items,
    compute_classification_version,
    compute_content_hash,
    compute_extraction_dataset_hash,
)
from app.repositories.extraction_repository import (
    SqliteExtractionRepository,
    default_extraction_repository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.project_repository import (
    ProjectNotFoundError,
    SqliteProjectRepository,
    default_project_repository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
    default_project_quality_assessment_configuration_repository,
    default_quality_assessment_catalog_repository,
    default_quality_assessment_repository,
)
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
    default_synthesis_classification_repository,
)
from app.repositories.synthesis_context_repository import (
    SqliteSynthesisContextRepository,
    default_synthesis_context_repository,
)
from app.repositories.synthesis_gap_repository import (
    SqliteSynthesisGapRepository,
    default_synthesis_gap_repository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
    default_synthesis_matrix_repository,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
    default_synthesis_mechanism_repository,
)
from app.repositories.synthesis_snapshot_repository import (
    SqliteSynthesisSnapshotRepository,
    default_synthesis_snapshot_repository,
)


def _as_datetime(val: str | datetime | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class SnapshotNotFoundError(Exception):
    """Raised when a snapshot does not exist in a project."""


class SnapshotExportError(Exception):
    """Raised when a snapshot export format is unsupported."""


class SynthesisSnapshotService:
    """Deterministic, researcher-driven service for synthesis snapshots."""

    def __init__(
        self,
        snapshot_repo: SqliteSynthesisSnapshotRepository | None = None,
        matrix_repo: SqliteSynthesisMatrixRepository | None = None,
        mechanism_repo: SqliteSynthesisMechanismRepository | None = None,
        context_repo: SqliteSynthesisContextRepository | None = None,
        gap_repo: SqliteSynthesisGapRepository | None = None,
        classification_repo: SqliteSynthesisClassificationRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        publication_repo: SqliteProjectPublicationRepository | None = None,
        project_repo: SqliteProjectRepository | None = None,
        qa_repo: SqliteQualityAssessmentRepository | None = None,
        qa_config_repo: SqliteProjectQualityAssessmentConfigurationRepository | None = None,
        qa_catalog_repo: SqliteQualityAssessmentCatalogRepository | None = None,
        adapter: SynthesisExtractionAdapter | None = None,
    ) -> None:
        self._snapshot_repo = snapshot_repo or default_synthesis_snapshot_repository()
        self._matrix_repo = matrix_repo or default_synthesis_matrix_repository()
        self._mechanism_repo = mechanism_repo or default_synthesis_mechanism_repository()
        self._context_repo = context_repo or default_synthesis_context_repository()
        self._gap_repo = gap_repo or default_synthesis_gap_repository()
        self._classification_repo = classification_repo or default_synthesis_classification_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._project_repo = project_repo or default_project_repository()
        self._qa_repo = qa_repo or default_quality_assessment_repository()
        self._qa_config_repo = qa_config_repo or default_project_quality_assessment_configuration_repository()
        self._qa_catalog_repo = qa_catalog_repo or default_quality_assessment_catalog_repository()
        self._adapter = adapter or SynthesisExtractionAdapter(
            extraction_repo=self._extraction_repo,
            qa_repo=self._qa_repo,
        )

    def _ensure_project_exists(self, project_id: str) -> None:
        proj = self._project_repo.get(project_id)
        if proj is None:
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist")

    # -----------------------------------------------------------------
    # Content assembly
    # -----------------------------------------------------------------

    def _assemble_content(self, project_id: str) -> SynthesisSnapshotContent:
        """Assembles the full analytical synthesis state into snapshot content.

        The content is a stored snapshot of the synthesis state at creation time.
        The repository persists this content as JSON; the snapshot never holds a
        live reference to any mutable synthesis table.
        """
        relations: list[AnalyticalRelation] = self._matrix_repo.list_analytical_relations(project_id)
        pathways: list[MechanismPathway] = self._mechanism_repo.list_pathways(project_id)

        context_assignments: list[ContextAssignment] = []
        for row in self._context_repo.list_links(project_id):
            context_assignments.append(
                ContextAssignment(
                    assignment_id=row["link_id"],
                    project_id=row["project_id"],
                    analytical_relation_id=row["analytical_relation_id"],
                    group_item_id=row["group_item_id"],
                    publication_id=row["publication_id"],
                    latest_revision_id=row["latest_revision_id"],
                    source_context_text=row["source_context_text"],
                    analytical_context_category_id=row["analytical_context_category_id"],
                    context_impact=row["context_impact"],
                    approval_state=ClassificationApprovalState(row["approval_state"]),
                    approved_by=row["approved_by"],
                    approved_at=row["approved_at"],
                    created_at=_as_datetime(row.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=_as_datetime(row.get("updated_at")) or datetime.now(timezone.utc),
                )
            )

        gaps: list[ResearchGap] = []
        gap_links: list[ResearchGapLink] = []
        for gap_row in self._gap_repo.list_gaps(project_id):
            gaps.append(self._gap_from_row(gap_row))
            for link_row in self._gap_repo.list_links_for_gap(project_id, gap_row["gap_id"]):
                gap_links.append(self._link_from_row(link_row))

        term_mappings: list[TermMapping] = self._classification_repo.list_term_mappings(project_id)
        lean_categories = self._classification_repo.list_lean_categories(project_id)
        energy_categories = self._classification_repo.list_energy_categories(project_id)
        mechanism_categories = self._mechanism_repo.list_categories(project_id)
        context_categories: list[ContextCategory] = []
        for row in self._context_repo.list_categories(project_id):
            context_categories.append(
                ContextCategory(
                    category_id=row["category_id"],
                    name=row["name"],
                    project_id=row["project_id"],
                    description=row["description"],
                    display_order=row["display_order"],
                    created_at=row["created_at"] or datetime.now(timezone.utc),
                    updated_at=row["updated_at"] or datetime.now(timezone.utc),
                )
            )

        publication_ids = {
            rel.publication_id for rel in relations
        } | {pathway.publication_id for pathway in pathways} | {
            assignment.publication_id for assignment in context_assignments
        }
        qa_profiles: list[QAProfileSummary] = []
        for publication_id in sorted(publication_ids, key=lambda u: str(u)):
            profile = self._adapter.get_qa_profile_summary(project_id, publication_id)
            if profile is not None:
                qa_profiles.append(profile)

        return SynthesisSnapshotContent(
            project_id=project_id,
            relations=relations,
            mechanism_pathways=pathways,
            context_assignments=context_assignments,
            research_gaps=gaps,
            research_gap_links=gap_links,
            term_mappings=term_mappings,
            lean_categories=lean_categories,
            energy_categories=energy_categories,
            mechanism_categories=mechanism_categories,
            context_categories=context_categories,
            qa_profiles=qa_profiles,
        )

    def _gap_from_row(self, row: dict) -> ResearchGap:
        return ResearchGap(
            gap_id=UUID(row["gap_id"]),
            project_id=row["project_id"],
            gap_type=ResearchGapType(row["gap_type"]),
            title=row["title"],
            rationale=row["rationale"],
            researcher_id=row["researcher_id"],
            created_at=_as_datetime(row.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_as_datetime(row.get("updated_at")) or datetime.now(timezone.utc),
        )

    def _link_from_row(self, row: dict) -> ResearchGapLink:
        return ResearchGapLink(
            link_id=UUID(row["link_id"]),
            project_id=row["project_id"],
            gap_id=UUID(row["gap_id"]),
            link_type=ResearchGapLinkType(row["link_type"]),
            target_id=UUID(row["target_id"]),
            group_item_id=UUID(row["group_item_id"]),
            publication_id=UUID(row["publication_id"]),
            latest_revision_id=UUID(row["latest_revision_id"]),
            created_at=_as_datetime(row.get("created_at")) or datetime.now(timezone.utc),
        )

    # -----------------------------------------------------------------
    # Hash computation
    # -----------------------------------------------------------------

    def _compute_extraction_dataset_hash(self, project_id: str) -> str:
        """Deterministic SHA-256 over the eligible COMPLETE extraction dataset."""
        revisions = self._adapter.get_latest_complete_revision_batch(project_id, self._publication_ids(project_id))
        items = build_extraction_dataset_items([rev for rev in revisions.values() if rev is not None])
        return compute_extraction_dataset_hash(items)

    def _publication_ids(self, project_id: str) -> list[UUID]:
        try:
            publications = self._publication_repo.get_publications(project_id)
        except Exception:
            return []
        return [
            pub.record_id
            for pub in publications
            if getattr(pub, "record_id", None) is not None
        ]

    def _compute_classification_version(self, project_id: str) -> str:
        return compute_classification_version(
            lean_categories=self._classification_repo.list_lean_categories(project_id),
            energy_categories=self._classification_repo.list_energy_categories(project_id),
            mechanism_categories=self._mechanism_repo.list_categories(project_id),
            context_categories=self._context_categories(project_id),
            term_mappings=self._classification_repo.list_term_mappings(project_id),
            qa_configs=self._qa_configs(project_id),
        )

    def _context_categories(self, project_id: str) -> list[ContextCategory]:
        categories: list[ContextCategory] = []
        for row in self._context_repo.list_categories(project_id):
            categories.append(
                ContextCategory(
                    category_id=row["category_id"],
                    name=row["name"],
                    project_id=row["project_id"],
                    description=row["description"],
                    display_order=row["display_order"],
                    created_at=row["created_at"] or datetime.now(timezone.utc),
                    updated_at=row["updated_at"] or datetime.now(timezone.utc),
                )
            )
        return categories

    def _qa_configs(self, project_id: str) -> list[Any]:
        """Resolves the project's QA configuration template for hashing.

        Returns an empty list when no QA configuration is present so the
        classification version remains deterministic and complete.
        """
        config: ProjectQualityAssessmentConfiguration | None
        try:
            config = self._qa_config_repo.get_configuration(project_id)
        except Exception:
            config = None
        if config is None:
            return []
        template = self._qa_catalog_repo.get_template_version(config.template_id)
        if template is None:
            return []
        return [template]

    # -----------------------------------------------------------------
    # Snapshot creation & reads
    # -----------------------------------------------------------------

    def create_snapshot(self, project_id: str, actor: str) -> SynthesisSnapshot:
        """Explicitly creates a new immutable snapshot of the synthesis state.

        Version resolution is monotonic: next = max existing version + 1, so a
        version is never reused. Every explicit call creates a new version even
        when the underlying content is unchanged (narrowest deterministic
        interpretation, documented in tests).
        """
        self._ensure_project_exists(project_id)

        clean_actor = actor.strip()
        if not clean_actor:
            raise ValueError("actor must be non-empty")

        content = self._assemble_content(project_id)
        existing = self._snapshot_repo.list_snapshots(project_id)
        next_version = max((s.version for s in existing), default=0) + 1

        snapshot = SynthesisSnapshot(
            snapshot_id=uuid4(),
            project_id=project_id,
            version=next_version,
            actor=clean_actor,
            extraction_dataset_hash=self._compute_extraction_dataset_hash(project_id),
            classification_version=self._compute_classification_version(project_id),
            content_hash=compute_content_hash(content),
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        self._snapshot_repo.save_snapshot(snapshot)
        return snapshot

    def list_snapshots(self, project_id: str) -> list[SynthesisSnapshot]:
        self._ensure_project_exists(project_id)
        return self._snapshot_repo.list_snapshots(project_id)

    def get_snapshot_by_version(self, project_id: str, version: int) -> SynthesisSnapshot:
        self._ensure_project_exists(project_id)
        snapshot = self._snapshot_repo.get_snapshot_by_version(project_id, version)
        if snapshot is None:
            raise SnapshotNotFoundError(
                f"Snapshot version {version} not found in project '{project_id}'"
            )
        return snapshot

    def get_snapshot(self, project_id: str, snapshot_id: str) -> SynthesisSnapshot:
        self._ensure_project_exists(project_id)
        snapshot = self._snapshot_repo.get_snapshot(project_id, snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(
                f"Snapshot '{snapshot_id}' not found in project '{project_id}'"
            )
        return snapshot

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------

    def export_snapshot(self, project_id: str, version: int, fmt: str = "json") -> dict[str, Any]:
        """Exports a snapshot as JSON (full) or CSV (relations matrix).

        JSON export carries the complete snapshot content, allowing full
        external reconstruction of the synthesis matrices without data loss.
        """
        snapshot = self.get_snapshot_by_version(project_id, version)
        clean_format = fmt.strip().lower()
        if clean_format == "json":
            return self._export_json(snapshot)
        if clean_format == "csv":
            return self._export_csv(snapshot)
        raise SnapshotExportError(f"Unsupported export format '{fmt}'")

    def _export_json(self, snapshot: SynthesisSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": str(snapshot.snapshot_id),
            "project_id": snapshot.project_id,
            "version": snapshot.version,
            "actor": snapshot.actor,
            "created_at": snapshot.created_at.isoformat(),
            "format": "json",
            "extraction_dataset_hash": snapshot.extraction_dataset_hash,
            "classification_version": snapshot.classification_version,
            "content_hash": snapshot.content_hash,
            "content": snapshot.content.model_dump(mode="json"),
        }

    def _export_csv(self, snapshot: SynthesisSnapshot) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for rel in snapshot.content.relations:
            rows.append(
                {
                    "publication_id": str(rel.publication_id),
                    "group_item_id": str(rel.group_item_id),
                    "source_practice": rel.source_practice,
                    "analytical_lean_category_id": rel.analytical_lean_category_id,
                    "source_effect": rel.source_effect,
                    "analytical_energy_category_id": rel.analytical_energy_category_id,
                    "direction": rel.direction.value,
                    "magnitude": rel.magnitude,
                    "evidence_character": rel.evidence_character.value,
                    "approval_state": rel.approval_state.value,
                }
            )
        buffer = io.StringIO()
        fieldnames = [
            "publication_id",
            "group_item_id",
            "source_practice",
            "analytical_lean_category_id",
            "source_effect",
            "analytical_energy_category_id",
            "direction",
            "magnitude",
            "evidence_character",
            "approval_state",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return {
            "snapshot_id": str(snapshot.snapshot_id),
            "project_id": snapshot.project_id,
            "version": snapshot.version,
            "actor": snapshot.actor,
            "created_at": snapshot.created_at.isoformat(),
            "format": "csv",
            "content_csv": buffer.getvalue(),
            "content": snapshot.content.model_dump(mode="json"),
        }


def default_synthesis_snapshot_service() -> SynthesisSnapshotService:
    return SynthesisSnapshotService()
