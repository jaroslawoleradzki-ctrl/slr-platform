"""Service for Phase 10: Context Synthesis Business Rules (Task 10.5)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.api.dto.synthesis import (
    ContextSynthesisSummaryDTO,
)
from app.domain.extraction import ExtractionCompletenessStatus, ExtractionRevision
from app.domain.synthesis import (
    ClassificationApprovalState,
    ContextAssignment,
    ContextCategory,
    ContextWorkspaceData,
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
from app.repositories.synthesis_context_repository import (
    SqliteSynthesisContextRepository,
    default_synthesis_context_repository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
    default_synthesis_matrix_repository,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
    default_synthesis_mechanism_repository,
)
from app.services.active_publication_filter import active_publication_ids

CANONICAL_CONTEXT_FIELD_KEYS: set[str] = {"moderating_conditions"}


def _as_datetime(val: str | datetime | None) -> datetime | None:
    """Converts a database string or datetime to a timezone-aware datetime."""
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


def _ensure_project_isolation(project_id: str, effective_project_id: str) -> None:
    """Ensure the project exists and is isolated for context operations."""
    project = default_project_repository().get(project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project '{project_id}' not found")


class SynthesisContextService:
    """Business rules for Phase 10 context synthesis.

    Orchestrates context category management, relation context linking,
    and synchronization from latest COMPLETE extraction revisions only.
    Only evidence from revisions with status COMPLETE enters synthesis.
    DRAFT revisions are explicitly excluded.
    Researcher-entered assignments are preserved where valid.
    """

    def __init__(
        self,
        context_repo: SqliteSynthesisContextRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        matrix_repo: SqliteSynthesisMatrixRepository | None = None,
        mechanism_repo: SqliteSynthesisMechanismRepository | None = None,
        project_repo: SqliteProjectRepository | None = None,
        publication_repo: SqliteProjectPublicationRepository | None = None,
        adapter: SynthesisExtractionAdapter | None = None,
    ) -> None:
        self._context_repo = context_repo or default_synthesis_context_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._matrix_repo = matrix_repo or default_synthesis_matrix_repository()
        self._mechanism_repo = mechanism_repo or default_synthesis_mechanism_repository()
        self._project_repo = project_repo or default_project_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._adapter = adapter or SynthesisExtractionAdapter(
            extraction_repo=self._extraction_repo,
            publication_repo=self._publication_repo,
        )

    # -----------------------------------------------------------------
    # Context Category CRUD
    # -----------------------------------------------------------------

    def create_context_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> ContextCategory:
        _ensure_project_isolation(project_id, project_id)

        existing = self._context_repo.get_category(project_id, category_id)
        if existing is not None:
            raise ValueError(f"Context category '{category_id}' already exists in project '{project_id}'")

        self._context_repo.create_category(
            category_id=category_id,
            name=name,
            project_id=project_id,
            description=description,
            display_order=display_order,
        )

        result = self.get_context_category(project_id, category_id)
        if result is None:
            raise ValueError(f"Failed to create context category '{category_id}'")
        return result

    def get_context_category(
        self, project_id: str, category_id: str
    ) -> ContextCategory | None:
        _ensure_project_isolation(project_id, project_id)
        result = self._context_repo.get_category(project_id, category_id)
        if result is None:
            return None
        return ContextCategory(
            category_id=result["category_id"],
            name=result["name"],
            project_id=result["project_id"],
            description=result.get("description"),
            display_order=result.get("display_order", 0),
            created_at=_as_datetime(result.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_as_datetime(result.get("updated_at")) or datetime.now(timezone.utc),
        )

    def list_context_categories(self, project_id: str) -> list[ContextCategory]:
        _ensure_project_isolation(project_id, project_id)
        results = self._context_repo.list_categories(project_id)
        return [
            ContextCategory(
                category_id=r["category_id"],
                name=r["name"],
                project_id=r["project_id"],
                description=r.get("description"),
                display_order=r.get("display_order", 0),
                created_at=_as_datetime(r.get("created_at")) or datetime.now(timezone.utc),
                updated_at=_as_datetime(r.get("updated_at")) or datetime.now(timezone.utc),
            )
            for r in results
        ]

    def update_context_category(
        self,
        project_id: str,
        category_id: str,
        name: str | None = None,
        description: str | None = None,
        display_order: int | None = None,
    ) -> ContextCategory | None:
        _ensure_project_isolation(project_id, project_id)

        result = self._context_repo.update_category(
            project_id=project_id,
            category_id=category_id,
            name=name,
            description=description,
            display_order=display_order,
        )
        if result is None:
            return None
        return ContextCategory(
            category_id=result["category_id"],
            name=result["name"],
            project_id=result["project_id"],
            description=result.get("description"),
            display_order=result.get("display_order", 0),
            created_at=_as_datetime(result.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_as_datetime(result.get("updated_at")) or datetime.now(timezone.utc),
        )

    def delete_context_category(
        self, project_id: str, category_id: str
    ) -> bool:
        _ensure_project_isolation(project_id, project_id)
        return self._context_repo.delete_category(project_id, category_id)

    # -----------------------------------------------------------------
    # Context Assignment operations
    # -----------------------------------------------------------------

    def assign_context_to_relation(
        self,
        project_id: str,
        group_item_id: UUID,
        publication_id: UUID,
        latest_revision_id: UUID,
        source_context_text: str,
        category_id: str,
        context_impact: str = "ENABLE",
    ) -> ContextAssignment:
        _ensure_project_isolation(project_id, project_id)

        # Verify category exists and belongs to project
        category = self._context_repo.get_category(project_id, category_id)
        if category is None:
            raise ValueError(f"Context category '{category_id}' not found in project '{project_id}'")

        # Check if there's already a link for this group_item_id in this project
        existing = self._context_repo.get_link_by_group_item(project_id, group_item_id)
        if existing is not None:
            # Link already exists - remap/assign to same relation, preserving impact
            remapped = self.remap_context_assignment(
                link_id=existing["link_id"],
                new_category_id=category_id,
                project_id=project_id,
                context_impact=context_impact,
            )
            if remapped is None:
                raise ValueError(f"Failed to remap context assignment for link '{existing['link_id']}'")
            return remapped

        # Get the analytical relation linked to this group_item_id
        rel = self._matrix_repo.get_analytical_relation_by_group_item(project_id, group_item_id)
        if rel is None:
            raise ValueError(
                f"No analytical relation found for group_item_id '{group_item_id}' in project '{project_id}'"
            )

        analytical_relation_id = str(rel.relation_id)

        # Create the link
        link_id = str(uuid4())
        link_result = self._context_repo.create_link(
            link_id=link_id,
            project_id=project_id,
            analytical_relation_id=analytical_relation_id,
            group_item_id=str(group_item_id),
            publication_id=str(publication_id),
            latest_revision_id=str(latest_revision_id),
            source_context_text=source_context_text,
            analytical_context_category_id=category_id,
            context_impact=context_impact,
            approval_state="pending",
        )
        if link_result is None:
            raise ValueError("Failed to create context link")

        return ContextAssignment(
            assignment_id=UUID(link_result["link_id"]),
            project_id=link_result["project_id"],
            analytical_relation_id=UUID(link_result["analytical_relation_id"]),
            group_item_id=UUID(link_result["group_item_id"]),
            publication_id=UUID(link_result["publication_id"]),
            latest_revision_id=UUID(link_result["latest_revision_id"]),
            source_context_text=link_result["source_context_text"],
            analytical_context_category_id=link_result["analytical_context_category_id"],
            context_impact=link_result["context_impact"],
            approval_state=ClassificationApprovalState(link_result["approval_state"]),
            approved_by=link_result.get("approved_by"),
            approved_at=link_result.get("approved_at"),
            created_at=_as_datetime(link_result.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_as_datetime(link_result.get("updated_at")) or datetime.now(timezone.utc),
        )

    def remap_context_assignment(
        self,
        link_id: str,
        new_category_id: str,
        project_id: str,
        context_impact: str | None = None,
    ) -> ContextAssignment | None:
        _ensure_project_isolation(project_id, project_id)

        # Resolve the link first so a missing link is a 404, not a 400/500.
        link = self._context_repo.get_link(link_id)
        if link is None:
            return None

        # Verify new category exists and belongs to project
        new_category = self._context_repo.get_category(project_id, new_category_id)
        if new_category is None:
            raise ValueError(f"Context category '{new_category_id}' not found in project '{project_id}'")

        # Update the link's category (and impact when the researcher provides one)
        link = self._context_repo.update_link(
            link_id=link_id,
            analytical_context_category_id=new_category_id,
            context_impact=context_impact,
        )
        if link is None:
            return None

        return ContextAssignment(
            assignment_id=UUID(link["link_id"]),
            project_id=link["project_id"],
            analytical_relation_id=UUID(link["analytical_relation_id"]),
            group_item_id=UUID(link["group_item_id"]),
            publication_id=UUID(link["publication_id"]),
            latest_revision_id=UUID(link["latest_revision_id"]),
            source_context_text=link["source_context_text"],
            analytical_context_category_id=link["analytical_context_category_id"],
            context_impact=link["context_impact"],
            approval_state=ClassificationApprovalState(link["approval_state"]),
            approved_by=link.get("approved_by"),
            approved_at=_as_datetime(link.get("approved_at")),
            created_at=_as_datetime(link.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_as_datetime(link.get("updated_at")) or datetime.now(timezone.utc),
        )

    def unassign_context_from_relation(self, link_id: str, project_id: str) -> bool:
        _ensure_project_isolation(project_id, project_id)
        return self._context_repo.delete_link(link_id)

    # -----------------------------------------------------------------
    # Synchronization from extraction (latest COMPLETE only)
    # -----------------------------------------------------------------

    def synchronize_context_from_extraction(self, project_id: str) -> ContextWorkspaceData:
        """Synchronize context synthesis from the latest COMPLETE extraction revisions.

        Only evidence from revisions with status COMPLETE enters synthesis.
        DRAFT revisions are explicitly excluded.
        Researcher-entered assignments are preserved where valid.
        """
        _ensure_project_isolation(project_id, project_id)

        valid_cats = {c["category_id"] for c in self._context_repo.list_categories(project_id)}
        existing_links = self._context_repo.list_links(project_id)
        existing_by_rel = {link["analytical_relation_id"]: link for link in existing_links}
        existing_by_group = {link["group_item_id"]: link for link in existing_links}

        active_ids = active_publication_ids(self._publication_repo, project_id)
        relations = [
            relation
            for relation in self._matrix_repo.list_analytical_relations(project_id)
            if active_ids is None or relation.publication_id in active_ids
        ]
        synced_link_ids: set[str] = set()

        for rel in relations:
            # 1. Discover source context text from latest eligible COMPLETE extraction revision
            source_context_text: str | None = None
            rev: ExtractionRevision | None = None
            try:
                rev = self._adapter.get_latest_complete_revision(project_id, rel.publication_id)
                if rev is not None:
                    item = next((i for i in rev.group_items if i.group_item_id == rel.group_item_id), None)
                    if item is not None:
                        for v in item.values:
                            if v.field_key in CANONICAL_CONTEXT_FIELD_KEYS and v.text_value:
                                source_context_text = v.text_value.strip()
                                break
            except Exception:
                pass

            resolved_rev_id = rev.revision_id if rev is not None else rel.latest_revision_id

            existing = existing_by_rel.get(str(rel.relation_id)) or existing_by_group.get(str(rel.group_item_id))
            if existing is not None:
                synced_link_ids.add(existing["link_id"])
                # Retain researcher assignments if category is still valid
                raw_cat_id = existing["analytical_context_category_id"]
                cat_id = raw_cat_id if raw_cat_id in valid_cats else None
                approval_state = existing["approval_state"] if cat_id else "pending"
                approved_by = existing.get("approved_by") if cat_id else None
                approved_at = existing.get("approved_at") if cat_id else None
                context_impact = existing.get("context_impact") or "ENABLE"

                if rev is not None:
                    final_text = source_context_text or ""
                else:
                    final_text = existing["source_context_text"]

                self._context_repo.create_link(
                    link_id=existing["link_id"],
                    project_id=project_id,
                    analytical_relation_id=str(rel.relation_id),
                    group_item_id=str(rel.group_item_id),
                    publication_id=str(rel.publication_id),
                    latest_revision_id=str(resolved_rev_id),
                    source_context_text=final_text,
                    analytical_context_category_id=cat_id,
                    context_impact=context_impact,
                    approval_state=approval_state,
                    approved_by=approved_by,
                    approved_at=approved_at,
                    notes=existing.get("notes"),
                )
            else:
                link_id = str(uuid4())
                synced_link_ids.add(link_id)
                self._context_repo.create_link(
                    link_id=link_id,
                    project_id=project_id,
                    analytical_relation_id=str(rel.relation_id),
                    group_item_id=str(rel.group_item_id),
                    publication_id=str(rel.publication_id),
                    latest_revision_id=str(resolved_rev_id),
                    source_context_text=source_context_text or "",
                    analytical_context_category_id=None,
                    context_impact="ENABLE",
                    approval_state="pending",
                    approved_by=None,
                    approved_at=None,
                    notes=None,
                )

        # Handle any existing links not linked to active matrix relations
        for existing in existing_links:
            if existing["link_id"] in synced_link_ids:
                continue
            try:
                pub_id = UUID(existing["publication_id"])
                rev = self._adapter.get_latest_complete_revision(project_id, pub_id)
                if rev is not None and rev.completeness_status == ExtractionCompletenessStatus.COMPLETE:
                    item = next((i for i in rev.group_items if str(i.group_item_id) == str(existing["group_item_id"])), None)
                    if item is not None:
                        extracted = ""
                        for v in item.values:
                            if v.field_key in CANONICAL_CONTEXT_FIELD_KEYS and v.text_value:
                                extracted = v.text_value.strip()
                                break
                        final_text = extracted
                    elif len(rev.group_items) > 0:
                        final_text = ""
                    else:
                        final_text = existing["source_context_text"]

                    raw_cat_id = existing["analytical_context_category_id"]
                    cat_id = raw_cat_id if raw_cat_id in valid_cats else None
                    approval_state = existing["approval_state"] if cat_id else "pending"
                    approved_by = existing.get("approved_by") if cat_id else None
                    approved_at = existing.get("approved_at") if cat_id else None

                    self._context_repo.create_link(
                        link_id=existing["link_id"],
                        project_id=project_id,
                        analytical_relation_id=existing["analytical_relation_id"],
                        group_item_id=existing["group_item_id"],
                        publication_id=existing["publication_id"],
                        latest_revision_id=str(rev.revision_id),
                        source_context_text=final_text,
                        analytical_context_category_id=cat_id,
                        context_impact=existing["context_impact"],
                        approval_state=approval_state,
                        approved_by=approved_by,
                        approved_at=approved_at,
                        notes=existing.get("notes"),
                    )
            except Exception:
                pass

        current_links = self._context_repo.list_links(project_id)
        assignments = [
            ContextAssignment(
                assignment_id=UUID(link["link_id"]),
                project_id=link["project_id"],
                analytical_relation_id=UUID(link["analytical_relation_id"]),
                group_item_id=UUID(link["group_item_id"]),
                publication_id=UUID(link["publication_id"]),
                latest_revision_id=UUID(link["latest_revision_id"]),
                source_context_text=link["source_context_text"],
                analytical_context_category_id=link["analytical_context_category_id"],
                context_impact=link["context_impact"],
                approval_state=ClassificationApprovalState(link["approval_state"]),
                approved_by=link.get("approved_by"),
                approved_at=_as_datetime(link.get("approved_at")),
                created_at=_as_datetime(link.get("created_at")) or datetime.now(timezone.utc),
                updated_at=_as_datetime(link.get("updated_at")) or datetime.now(timezone.utc),
            )
            for link in current_links
            if active_ids is None or UUID(link["publication_id"]) in active_ids
        ]

        categories = self.list_context_categories(project_id)
        summary = self.calculate_context_synthesis_summary(project_id)

        return ContextWorkspaceData(
            project_id=project_id,
            categories=categories,
            assignments=assignments,
            stats={
                "total_relations": summary["distinct_analytical_relation_count"],
                "total_publications": summary["distinct_publication_count"],
                "categorized_relations": summary["distinct_mechanism_pathway_count"],
                "total_assignments": summary["context_evidence_count"],
            },
        )

    # -----------------------------------------------------------------
    # Synthesis summary
    # -----------------------------------------------------------------

    def get_context_synthesis_summary(self, project_id: str) -> ContextSynthesisSummaryDTO:
        _ensure_project_isolation(project_id, project_id)

        active_ids = active_publication_ids(self._publication_repo, project_id)
        links = [
            link
            for link in self._context_repo.list_links(project_id)
            if active_ids is None or UUID(link["publication_id"]) in active_ids
        ]

        total_relations = len({link["analytical_relation_id"] for link in links})
        categorized_relations = len({
            link["analytical_context_category_id"] for link in links
            if link["analytical_context_category_id"] is not None
        })

        # Context impact distribution
        impact_counts: dict[str, int] = {}
        for link in links:
            impact = link["context_impact"]
            impact_counts[impact] = impact_counts.get(impact, 0) + 1

        # Approval state distribution
        approval_counts: dict[str, int] = {}
        for link in links:
            state = link["approval_state"]
            approval_counts[state] = approval_counts.get(state, 0) + 1

        return ContextSynthesisSummaryDTO(
            context_evidence_count=len(links),
            distinct_publication_count=len({link["publication_id"] for link in links}),
            distinct_analytical_relation_count=total_relations,
            distinct_mechanism_pathway_count=categorized_relations,
        )

    def calculate_context_synthesis_summary(self, project_id: str) -> dict[str, int]:
        """Calculates deterministic context synthesis summary statistics.

        Returns a dict compatible with the API DTO construction.
        """
        summary = self.get_context_synthesis_summary(project_id)
        return {
            "context_evidence_count": summary.context_evidence_count,
            "distinct_publication_count": summary.distinct_publication_count,
            "distinct_analytical_relation_count": summary.distinct_analytical_relation_count,
            "distinct_mechanism_pathway_count": summary.distinct_mechanism_pathway_count,
        }

    # -----------------------------------------------------------------
    # Remap operation
    # -----------------------------------------------------------------

    def remap_context(self, project_id: str, from_category_id: str, to_category_id: str) -> int:
        """Remap all assignments from one category to another within a project.

        Returns the number of assignments remapped.
        """
        _ensure_project_isolation(project_id, project_id)

        # Get all links assigned to the from_category
        links = self._context_repo.list_links_by_category(project_id, from_category_id)

        remapped = 0
        for link in links:
            # Update the link's category to the target
            self._context_repo.update_link(
                link_id=link["link_id"],
                analytical_context_category_id=to_category_id,
            )
            remapped += 1

        return remapped


def default_synthesis_context_service() -> SynthesisContextService:
    return SynthesisContextService()
