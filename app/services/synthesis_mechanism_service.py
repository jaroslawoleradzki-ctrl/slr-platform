"""Phase 10: Service Layer for Mechanism Synthesis & Impact Pathways (Task 10.4)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.domain.extraction import ExtractionCompletenessStatus
from app.domain.synthesis import (
    AnalyticalMechanismCategory,
    ClassificationApprovalState,
    EvidenceCharacter,
    MechanismPathway,
    MechanismPathwayDetail,
    MechanismSynthesisPathway,
    MechanismWorkspaceData,
    MechanismWorkspaceStats,
    RelationDirection,
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
    SqliteQualityAssessmentRepository,
    default_quality_assessment_repository,
)
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
    default_synthesis_classification_repository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
    default_synthesis_matrix_repository,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
    default_synthesis_mechanism_repository,
)

if TYPE_CHECKING:
    from app.domain.extraction import ExtractionRevision

CANONICAL_MECHANISM_FIELD_KEYS: set[str] = {"impact_mechanism"}


class MechanismCategoryNotFoundError(Exception):
    """Raised when an analytical mechanism category is not found."""


class MechanismCategoryConflictError(Exception):
    """Raised when attempting to create a duplicate mechanism category."""


class MechanismPathwayNotFoundError(Exception):
    """Raised when a mechanism pathway is not found."""


class MechanismAssignmentError(Exception):
    """Raised when a mechanism pathway assignment fails validation."""


class SynthesisMechanismService:
    """Deterministic, researcher-driven service for mechanism classification and synthesis."""

    def __init__(
        self,
        mechanism_repo: SqliteSynthesisMechanismRepository | None = None,
        matrix_repo: SqliteSynthesisMatrixRepository | None = None,
        classification_repo: SqliteSynthesisClassificationRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        publication_repo: SqliteProjectPublicationRepository | None = None,
        project_repo: SqliteProjectRepository | None = None,
        qa_repo: SqliteQualityAssessmentRepository | None = None,
        adapter: SynthesisExtractionAdapter | None = None,
    ) -> None:
        self._mechanism_repo = mechanism_repo or default_synthesis_mechanism_repository()
        self._matrix_repo = matrix_repo or default_synthesis_matrix_repository()
        self._classification_repo = classification_repo or default_synthesis_classification_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._project_repo = project_repo or default_project_repository()
        self._qa_repo = qa_repo or default_quality_assessment_repository()
        self._adapter = adapter or SynthesisExtractionAdapter(
            extraction_repo=self._extraction_repo,
            qa_repo=self._qa_repo,
        )

    def _ensure_project_exists(self, project_id: str) -> None:
        proj = self._project_repo.get(project_id)
        if proj is None:
            raise ProjectNotFoundError(f"Project '{project_id}' does not exist")

    # ==========================================
    # Mechanism Category Operations
    # ==========================================

    def create_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> AnalyticalMechanismCategory:
        self._ensure_project_exists(project_id)
        clean_cat_id = category_id.strip()
        clean_name = name.strip()
        if not clean_cat_id or not clean_name:
            raise ValueError("Category ID and name must be non-empty")

        existing = self._mechanism_repo.get_category(project_id, clean_cat_id)
        if existing is not None:
            raise MechanismCategoryConflictError(
                f"Mechanism category '{clean_cat_id}' already exists in project '{project_id}'"
            )

        cat = AnalyticalMechanismCategory(
            category_id=clean_cat_id,
            name=clean_name,
            project_id=project_id,
            description=description.strip() if description else None,
            display_order=display_order,
        )
        return self._mechanism_repo.create_category(cat)

    def get_category(self, project_id: str, category_id: str) -> AnalyticalMechanismCategory:
        self._ensure_project_exists(project_id)
        cat = self._mechanism_repo.get_category(project_id, category_id)
        if cat is None:
            raise MechanismCategoryNotFoundError(
                f"Mechanism category '{category_id}' not found in project '{project_id}'"
            )
        return cat

    def list_categories(self, project_id: str) -> list[AnalyticalMechanismCategory]:
        self._ensure_project_exists(project_id)
        return self._mechanism_repo.list_categories(project_id)

    def update_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> AnalyticalMechanismCategory:
        self._ensure_project_exists(project_id)
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Category name must be non-empty")

        cat = self.get_category(project_id, category_id)
        updated = AnalyticalMechanismCategory(
            category_id=cat.category_id,
            name=clean_name,
            project_id=project_id,
            description=description.strip() if description else None,
            display_order=display_order,
            created_at=cat.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._mechanism_repo.update_category(updated)

    def delete_category(self, project_id: str, category_id: str) -> bool:
        self._ensure_project_exists(project_id)
        return self._mechanism_repo.delete_category(project_id, category_id)

    # ==========================================
    # Synchronization & Ingestion
    # ==========================================

    def synchronize_mechanism_pathways(self, project_id: str) -> list[MechanismPathway]:
        """Discovers and synchronizes mechanism evidence from analytical relations and eligible COMPLETE extraction revisions."""
        self._ensure_project_exists(project_id)

        relations = self._matrix_repo.list_analytical_relations(project_id)
        existing_pathways = {p.analytical_relation_id: p for p in self._mechanism_repo.list_pathways(project_id)}
        valid_cats = {c.category_id for c in self._mechanism_repo.list_categories(project_id)}

        synced: list[MechanismPathway] = []
        for rel in relations:
            # 1. Discover source mechanism text from latest eligible COMPLETE extraction revision
            source_mech_text: str | None = None
            rev: ExtractionRevision | None = None
            try:
                if rel.latest_revision_id:
                    history = self._extraction_repo.list_revision_history(project_id, rel.publication_id)
                    rev = next(
                        (
                            r
                            for r in history
                            if r.revision_id == rel.latest_revision_id
                            and r.completeness_status == ExtractionCompletenessStatus.COMPLETE
                        ),
                        None,
                    )
                if rev is None:
                    rev = self._adapter.get_latest_complete_revision(project_id, rel.publication_id)

                if rev is not None:
                    item = next((i for i in rev.group_items if i.group_item_id == rel.group_item_id), None)
                    if item is not None:
                        for v in item.values:
                            if v.field_key in CANONICAL_MECHANISM_FIELD_KEYS and v.text_value:
                                source_mech_text = v.text_value.strip()
                                break
            except Exception:
                pass

            resolved_rev_id = rev.revision_id if rev is not None else rel.latest_revision_id

            existing = existing_pathways.get(rel.relation_id)
            if existing is not None:
                # Retain researcher assignments if category is still valid
                cat_id = (
                    existing.analytical_mechanism_category_id
                    if existing.analytical_mechanism_category_id in valid_cats
                    else None
                )
                pathway = MechanismPathway(
                    pathway_id=existing.pathway_id,
                    project_id=project_id,
                    analytical_relation_id=rel.relation_id,
                    group_item_id=rel.group_item_id,
                    publication_id=rel.publication_id,
                    latest_revision_id=resolved_rev_id,
                    source_mechanism_text=source_mech_text,
                    analytical_mechanism_category_id=cat_id,
                    is_review_synthesized=existing.is_review_synthesized,
                    approval_state=existing.approval_state if cat_id else ClassificationApprovalState.PENDING,
                    approved_by=existing.approved_by if cat_id else None,
                    approved_at=existing.approved_at if cat_id else None,
                    notes=existing.notes,
                    created_at=existing.created_at,
                    updated_at=datetime.now(timezone.utc),
                )
            else:
                pathway = MechanismPathway(
                    pathway_id=uuid4(),
                    project_id=project_id,
                    analytical_relation_id=rel.relation_id,
                    group_item_id=rel.group_item_id,
                    publication_id=rel.publication_id,
                    latest_revision_id=resolved_rev_id,
                    source_mechanism_text=source_mech_text,
                    analytical_mechanism_category_id=None,
                    is_review_synthesized=False,
                    approval_state=ClassificationApprovalState.PENDING,
                    approved_by=None,
                    approved_at=None,
                    notes=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            synced.append(pathway)

        return self._mechanism_repo.save_pathways(synced)

    # ==========================================
    # Classification & Approval
    # ==========================================

    def assign_mechanism_category(
        self,
        project_id: str,
        pathway_id: UUID,
        category_id: str | None,
        is_review_synthesized: bool = False,
        notes: str | None = None,
    ) -> MechanismPathway:
        """Assigns an analytical mechanism category to a pathway."""
        self._ensure_project_exists(project_id)

        pathway = self._mechanism_repo.get_pathway(project_id, pathway_id)
        if pathway is None:
            raise MechanismPathwayNotFoundError(f"Mechanism pathway '{pathway_id}' not found in project '{project_id}'")

        if category_id is not None:
            cat = self._mechanism_repo.get_category(project_id, category_id)
            if cat is None:
                raise MechanismCategoryNotFoundError(
                    f"Mechanism category '{category_id}' not found in project '{project_id}'"
                )

        updated = MechanismPathway(
            pathway_id=pathway.pathway_id,
            project_id=pathway.project_id,
            analytical_relation_id=pathway.analytical_relation_id,
            group_item_id=pathway.group_item_id,
            publication_id=pathway.publication_id,
            latest_revision_id=pathway.latest_revision_id,
            source_mechanism_text=pathway.source_mechanism_text,
            analytical_mechanism_category_id=category_id,
            is_review_synthesized=is_review_synthesized,
            approval_state=ClassificationApprovalState.PENDING,
            approved_by=None,
            approved_at=None,
            notes=notes.strip() if notes else None,
            created_at=pathway.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._mechanism_repo.save_pathway(updated)

    def approve_mechanism_pathway(
        self,
        project_id: str,
        pathway_id: UUID,
        reviewer_id: str,
    ) -> MechanismPathway:
        """Explicitly approves a mechanism pathway classification."""
        self._ensure_project_exists(project_id)
        if not reviewer_id.strip():
            raise ValueError("Reviewer ID must be specified to approve a mechanism pathway")

        pathway = self._mechanism_repo.get_pathway(project_id, pathway_id)
        if pathway is None:
            raise MechanismPathwayNotFoundError(f"Mechanism pathway '{pathway_id}' not found in project '{project_id}'")

        if not pathway.analytical_mechanism_category_id:
            raise MechanismAssignmentError(
                "Cannot approve a mechanism pathway that has no analytical mechanism category assigned"
            )

        updated = MechanismPathway(
            pathway_id=pathway.pathway_id,
            project_id=pathway.project_id,
            analytical_relation_id=pathway.analytical_relation_id,
            group_item_id=pathway.group_item_id,
            publication_id=pathway.publication_id,
            latest_revision_id=pathway.latest_revision_id,
            source_mechanism_text=pathway.source_mechanism_text,
            analytical_mechanism_category_id=pathway.analytical_mechanism_category_id,
            is_review_synthesized=pathway.is_review_synthesized,
            approval_state=ClassificationApprovalState.APPROVED,
            approved_by=reviewer_id.strip(),
            approved_at=datetime.now(timezone.utc),
            notes=pathway.notes,
            created_at=pathway.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._mechanism_repo.save_pathway(updated)

    # ==========================================
    # Workspace & Synthesis Views
    # ==========================================

    def get_mechanism_workspace_data(self, project_id: str) -> MechanismWorkspaceData:
        """Assembles the complete dataset for the Mechanism Synthesis Workspace."""
        self._ensure_project_exists(project_id)
        self.synchronize_mechanism_pathways(project_id)

        categories = self._mechanism_repo.list_categories(project_id)
        pathways = self._mechanism_repo.list_pathways(project_id)
        relations = {r.relation_id: r for r in self._matrix_repo.list_analytical_relations(project_id)}
        lean_cats = {c.category_id: c.name for c in self._classification_repo.list_lean_categories(project_id)}
        energy_cats = {c.category_id: c.name for c in self._classification_repo.list_energy_categories(project_id)}
        mech_cats = {c.category_id: c.name for c in categories}

        # Build detailed pathways with publication metadata and QA profile
        details: list[MechanismPathwayDetail] = []
        mapped_count = 0
        unmapped_count = 0
        approved_count = 0
        all_pubs: set[UUID] = set()

        for p in pathways:
            all_pubs.add(p.publication_id)
            if p.analytical_mechanism_category_id:
                mapped_count += 1
            else:
                unmapped_count += 1

            if p.approval_state == ClassificationApprovalState.APPROVED:
                approved_count += 1

            rel = relations.get(p.analytical_relation_id)
            pub_title: str | None = None
            pub_year: int | None = None
            try:
                pubs = self._publication_repo.get_publications(project_id)
                pub = next(
                    (
                        x
                        for x in pubs
                        if getattr(x, "record_id", None) == p.publication_id
                        or getattr(x, "publication_id", None) == p.publication_id
                    ),
                    None,
                )
                if pub is not None:
                    pub_title = pub.title
                    pub_year = pub.publication_year
            except Exception:
                pass

            qa_profile = self._adapter.get_qa_profile_summary(project_id, p.publication_id)

            l_id = rel.analytical_lean_category_id if rel else None
            e_id = rel.analytical_energy_category_id if rel else None

            details.append(
                MechanismPathwayDetail(
                    pathway=p,
                    publication_title=pub_title,
                    publication_year=pub_year,
                    source_practice=rel.source_practice if rel else "Unspecified Lean Practice",
                    source_effect=rel.source_effect if rel else "Unspecified Energy Effect",
                    analytical_lean_category_id=l_id,
                    analytical_lean_category_name=lean_cats.get(l_id, l_id) if l_id else None,
                    analytical_energy_category_id=e_id,
                    analytical_energy_category_name=energy_cats.get(e_id, e_id) if e_id else None,
                    analytical_mechanism_category_name=mech_cats.get(
                        p.analytical_mechanism_category_id, p.analytical_mechanism_category_id
                    )
                    if p.analytical_mechanism_category_id
                    else None,
                    direction=rel.direction if rel else RelationDirection.CANNOT_DETERMINE,
                    evidence_character=rel.evidence_character if rel else EvidenceCharacter.EMPIRICAL,
                    qa_profile=qa_profile,
                )
            )

        # Build synthesis chains for approved classifications
        chain_map: dict[tuple[str, str, str], list[MechanismPathwayDetail]] = {}
        for d in details:
            if (
                d.pathway.approval_state == ClassificationApprovalState.APPROVED
                and d.analytical_lean_category_id
                and d.pathway.analytical_mechanism_category_id
                and d.analytical_energy_category_id
            ):
                key = (
                    d.analytical_lean_category_id,
                    d.pathway.analytical_mechanism_category_id,
                    d.analytical_energy_category_id,
                )
                chain_map.setdefault(key, []).append(d)

        synthesis_chains: list[MechanismSynthesisPathway] = []
        for (l_id, m_id, e_id), chain_items in chain_map.items():
            chain_pubs = {item.pathway.publication_id for item in chain_items}
            chain_rels = {item.pathway.analytical_relation_id for item in chain_items}
            synthesis_chains.append(
                MechanismSynthesisPathway(
                    lean_category_id=l_id,
                    lean_category_name=lean_cats.get(l_id, l_id),
                    mechanism_category_id=m_id,
                    mechanism_category_name=mech_cats.get(m_id, m_id),
                    energy_category_id=e_id,
                    energy_category_name=energy_cats.get(e_id, e_id),
                    pathway_count=len(chain_items),
                    publication_count=len(chain_pubs),
                    relation_count=len(chain_rels),
                    pathways=chain_items,
                )
            )

        stats = MechanismWorkspaceStats(
            total_pathways=len(pathways),
            mapped_count=mapped_count,
            unmapped_count=unmapped_count,
            approved_count=approved_count,
            total_publications=len(all_pubs),
        )

        return MechanismWorkspaceData(
            project_id=project_id,
            categories=categories,
            pathways=details,
            synthesis_chains=synthesis_chains,
            stats=stats,
        )


def default_synthesis_mechanism_service() -> SynthesisMechanismService:
    return SynthesisMechanismService()
