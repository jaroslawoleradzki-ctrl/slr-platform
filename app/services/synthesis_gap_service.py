"""Service for Phase 10: Research Gap Synthesis Business Rules (Task 10.6)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.domain.synthesis import (
    ResearchGap,
    ResearchGapDetail,
    ResearchGapEvidenceCandidate,
    ResearchGapLink,
    ResearchGapLinkType,
    ResearchGapType,
    ResearchGapWorkspaceData,
    ResearchGapWorkspaceStats,
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


class ResearchGapNotFoundError(Exception):
    """Raised when a research gap is not found in a project."""


class ResearchGapEvidenceError(Exception):
    """Raised when linking evidence to a research gap fails validation."""


class SynthesisGapService:
    """Deterministic, researcher-driven service for research gap synthesis.

    Business invariants:
    - Gaps are researcher-authored analytical conclusions. No automatic gap
      detection, creation, ranking, or scoring. No AI/LLM.
    - Low publication count alone never establishes a gap; it is evidence input.
    - Every gap link must trace to an eligible COMPLETE extraction revision.
      DRAFT revisions are explicitly excluded as gap evidence.
    - Deleting a gap removes its links but never the underlying source evidence.
    """

    def __init__(
        self,
        gap_repo: SqliteSynthesisGapRepository | None = None,
        matrix_repo: SqliteSynthesisMatrixRepository | None = None,
        mechanism_repo: SqliteSynthesisMechanismRepository | None = None,
        context_repo: SqliteSynthesisContextRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        publication_repo: SqliteProjectPublicationRepository | None = None,
        project_repo: SqliteProjectRepository | None = None,
        qa_repo: SqliteQualityAssessmentRepository | None = None,
        adapter: SynthesisExtractionAdapter | None = None,
    ) -> None:
        self._gap_repo = gap_repo or default_synthesis_gap_repository()
        self._matrix_repo = matrix_repo or default_synthesis_matrix_repository()
        self._mechanism_repo = mechanism_repo or default_synthesis_mechanism_repository()
        self._context_repo = context_repo or default_synthesis_context_repository()
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
    # Research Gap CRUD
    # -----------------------------------------------------------------

    def create_research_gap(
        self,
        project_id: str,
        gap_type: str,
        title: str,
        rationale: str,
        researcher_id: str,
    ) -> ResearchGap:
        self._ensure_project_exists(project_id)

        clean_type = gap_type.strip()
        try:
            gap_type_enum = ResearchGapType(clean_type)
        except ValueError as e:
            raise ValueError(
                f"Invalid research gap type '{clean_type}'. Must be one of {[t.value for t in ResearchGapType]}"
            ) from e

        clean_title = title.strip()
        clean_rationale = rationale.strip()
        clean_researcher = researcher_id.strip()
        if not clean_title:
            raise ValueError("Research gap title must be non-empty")
        if not clean_rationale:
            raise ValueError("Research gap rationale must be non-empty (publication count alone is not proof)")
        if not clean_researcher:
            raise ValueError("researcher_id must be non-empty")

        gap_id = str(uuid4())
        self._gap_repo.create_gap(
            gap_id=gap_id,
            project_id=project_id,
            gap_type=gap_type_enum.value,
            title=clean_title,
            rationale=clean_rationale,
            researcher_id=clean_researcher,
        )
        result = self.get_research_gap(project_id, gap_id)
        if result is None:
            raise ValueError(f"Failed to create research gap '{gap_id}'")
        return result

    def get_research_gap(self, project_id: str, gap_id: str) -> ResearchGap | None:
        self._ensure_project_exists(project_id)
        row = self._gap_repo.get_gap(project_id, gap_id)
        if row is None:
            return None
        return self._gap_from_row(row)

    def update_research_gap(
        self,
        project_id: str,
        gap_id: str,
        gap_type: str | None = None,
        title: str | None = None,
        rationale: str | None = None,
    ) -> ResearchGap | None:
        self._ensure_project_exists(project_id)

        clean_type: str | None = None
        if gap_type is not None:
            clean_type = gap_type.strip()
            try:
                ResearchGapType(clean_type)
            except ValueError as e:
                raise ValueError(
                    f"Invalid research gap type '{clean_type}'. Must be one of {[t.value for t in ResearchGapType]}"
                ) from e

        clean_title = title.strip() if title is not None else None
        if clean_title is not None and not clean_title:
            raise ValueError("Research gap title must be non-empty")

        clean_rationale = rationale.strip() if rationale is not None else None
        if clean_rationale is not None and not clean_rationale:
            raise ValueError("Research gap rationale must be non-empty")

        row = self._gap_repo.update_gap(
            project_id=project_id,
            gap_id=gap_id,
            gap_type=clean_type,
            title=clean_title,
            rationale=clean_rationale,
        )
        if row is None:
            return None
        return self._gap_from_row(row)

    def delete_research_gap(self, project_id: str, gap_id: str) -> bool:
        self._ensure_project_exists(project_id)
        return self._gap_repo.delete_gap(project_id, gap_id)

    def list_research_gaps(self, project_id: str) -> list[ResearchGap]:
        self._ensure_project_exists(project_id)
        return [self._gap_from_row(row) for row in self._gap_repo.list_gaps(project_id)]

    # -----------------------------------------------------------------
    # Evidence linking (traceability enforced)
    # -----------------------------------------------------------------

    def _resolve_evidence_artifact(
        self, project_id: str, link_type: ResearchGapLinkType, target_id: UUID
    ) -> tuple[str, str, str]:
        """Resolves a link target to (group_item_id, publication_id, latest_revision_id).

        Raises ResearchGapEvidenceError when the target does not exist in the project.
        """
        if link_type == ResearchGapLinkType.ANALYTICAL_RELATION:
            rel = self._matrix_repo.get_analytical_relation(project_id, target_id)
            if rel is None:
                raise ResearchGapEvidenceError(
                    f"Analytical relation '{target_id}' not found in project '{project_id}'"
                )
            return str(rel.group_item_id), str(rel.publication_id), str(rel.latest_revision_id)

        if link_type == ResearchGapLinkType.MECHANISM_PATHWAY:
            pathway = self._mechanism_repo.get_pathway(project_id, target_id)
            if pathway is None:
                raise ResearchGapEvidenceError(
                    f"Mechanism pathway '{target_id}' not found in project '{project_id}'"
                )
            return str(pathway.group_item_id), str(pathway.publication_id), str(pathway.latest_revision_id)

        if link_type == ResearchGapLinkType.CONTEXT_FACTOR_LINK:
            ctx = self._context_repo.get_link(str(target_id))
            if ctx is None:
                raise ResearchGapEvidenceError(
                    f"Context factor link '{target_id}' not found in project '{project_id}'"
                )
            if ctx["project_id"] != project_id:
                raise ResearchGapEvidenceError(
                    f"Cross-project isolation violation: context link belongs to '{ctx['project_id']}'"
                )
            return str(ctx["group_item_id"]), str(ctx["publication_id"]), str(ctx["latest_revision_id"])

        raise ResearchGapEvidenceError(f"Unsupported link type '{link_type}'")

    def _resolve_complete_revision(
        self, project_id: str, publication_id: str, group_item_id: str
    ) -> str:
        """Resolves the latest eligible COMPLETE revision id for a group item.

        Raises ResearchGapEvidenceError when no eligible COMPLETE revision
        contains the group item (DRAFT revisions are never gap evidence).
        """
        try:
            ref = self._adapter.resolve_relation_traceability(
                project_id=project_id,
                publication_id=UUID(publication_id),
                group_item_id=UUID(group_item_id),
            )
        except (ValueError, KeyError) as e:
            raise ResearchGapEvidenceError(
                f"Evidence '{group_item_id}' is not traceable to an eligible COMPLETE "
                f"extraction revision in project '{project_id}'"
            ) from e
        return str(ref.revision_id)

    def link_evidence(
        self,
        project_id: str,
        gap_id: str,
        link_type: ResearchGapLinkType,
        target_id: UUID,
    ) -> ResearchGapLink:
        self._ensure_project_exists(project_id)

        gap = self._gap_repo.get_gap(project_id, gap_id)
        if gap is None:
            raise ResearchGapNotFoundError(f"Research gap '{gap_id}' not found in project '{project_id}'")

        group_item_id, publication_id, _ = self._resolve_evidence_artifact(project_id, link_type, target_id)
        resolved_revision_id = self._resolve_complete_revision(project_id, publication_id, group_item_id)

        existing = self._gap_repo.get_link_by_gap_target(project_id, gap_id, link_type.value, str(target_id))
        if existing is not None:
            if existing["latest_revision_id"] != resolved_revision_id:
                advanced = self._gap_repo.update_link_latest_revision(
                    existing["link_id"], resolved_revision_id
                )
                if advanced is not None:
                    return self._link_from_row(advanced)
            return self._link_from_row(existing)

        link_id = str(uuid4())
        row = self._gap_repo.add_link(
            link_id=link_id,
            project_id=project_id,
            gap_id=gap_id,
            link_type=link_type.value,
            target_id=str(target_id),
            group_item_id=group_item_id,
            publication_id=publication_id,
            latest_revision_id=resolved_revision_id,
        )
        return self._link_from_row(row)

    def unlink_evidence(self, project_id: str, gap_id: str, link_id: str) -> bool:
        self._ensure_project_exists(project_id)
        link = self._gap_repo.get_link(link_id)
        if link is None:
            return False
        if link["project_id"] != project_id or link["gap_id"] != gap_id:
            return False
        return self._gap_repo.remove_link(link_id)

    def list_links_for_gap(self, project_id: str, gap_id: str) -> list[ResearchGapLink]:
        self._ensure_project_exists(project_id)
        return [self._link_from_row(row) for row in self._gap_repo.list_links_for_gap(project_id, gap_id)]

    # -----------------------------------------------------------------
    # Workspace data & candidate evidence listing
    # -----------------------------------------------------------------

    def get_research_gap_workspace_data(self, project_id: str) -> ResearchGapWorkspaceData:
        self._ensure_project_exists(project_id)

        gaps: list[ResearchGapDetail] = []
        linked_publications: set[UUID] = set()
        for gap_row in self._gap_repo.list_gaps(project_id):
            gap = self._gap_from_row(gap_row)
            links = [self._link_from_row(r) for r in self._gap_repo.list_links_for_gap(project_id, gap_row["gap_id"])]
            linked_publications.update(link.publication_id for link in links)
            gaps.append(ResearchGapDetail(gap=gap, links=links))

        counts = self._gap_repo.count_by_type(project_id)
        stats = ResearchGapWorkspaceStats(
            total_gaps=len(gaps),
            thematic_count=counts.get(ResearchGapType.THEMATIC.value, 0),
            mechanism_count=counts.get(ResearchGapType.MECHANISM.value, 0),
            methodological_count=counts.get(ResearchGapType.METHODOLOGICAL.value, 0),
            contextual_count=counts.get(ResearchGapType.CONTEXTUAL.value, 0),
            inconsistent_evidence_count=counts.get(ResearchGapType.INCONSISTENT_EVIDENCE.value, 0),
            linked_publication_count=len(linked_publications),
        )

        return ResearchGapWorkspaceData(project_id=project_id, gaps=gaps, stats=stats)

    def list_linkable_evidence_candidates(self, project_id: str) -> list[ResearchGapEvidenceCandidate]:
        """Lists candidate synthesis artifacts eligible for linking to a research gap.

        Each candidate reports whether it currently traces to an eligible COMPLETE
        extraction revision. Non-traceable (e.g. DRAFT-only) artifacts must never
        become gap evidence and are flagged accordingly.
        """
        self._ensure_project_exists(project_id)

        candidates: list[ResearchGapEvidenceCandidate] = []

        for rel in self._matrix_repo.list_analytical_relations(project_id):
            candidates.append(
                self._build_candidate(
                    project_id=project_id,
                    link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
                    target_id=rel.relation_id,
                    group_item_id=rel.group_item_id,
                    publication_id=rel.publication_id,
                    latest_revision_id=rel.latest_revision_id,
                    label=f"{rel.source_practice} -> {rel.source_effect}",
                )
            )

        for pathway in self._mechanism_repo.list_pathways(project_id):
            candidates.append(
                self._build_candidate(
                    project_id=project_id,
                    link_type=ResearchGapLinkType.MECHANISM_PATHWAY,
                    target_id=pathway.pathway_id,
                    group_item_id=pathway.group_item_id,
                    publication_id=pathway.publication_id,
                    latest_revision_id=pathway.latest_revision_id,
                    label=pathway.source_mechanism_text or "Mechanism pathway",
                )
            )

        for ctx in self._context_repo.list_links(project_id):
            candidates.append(
                self._build_candidate(
                    project_id=project_id,
                    link_type=ResearchGapLinkType.CONTEXT_FACTOR_LINK,
                    target_id=UUID(ctx["link_id"]),
                    group_item_id=UUID(ctx["group_item_id"]),
                    publication_id=UUID(ctx["publication_id"]),
                    latest_revision_id=UUID(ctx["latest_revision_id"]),
                    label=ctx["source_context_text"] or "Context factor",
                )
            )

        return candidates

    def _build_candidate(
        self,
        project_id: str,
        link_type: ResearchGapLinkType,
        target_id: UUID,
        group_item_id: UUID,
        publication_id: UUID,
        latest_revision_id: UUID,
        label: str,
    ) -> ResearchGapEvidenceCandidate:
        traceable = False
        try:
            self._resolve_complete_revision(project_id, str(publication_id), str(group_item_id))
            traceable = True
        except ResearchGapEvidenceError:
            traceable = False

        pub_title: str | None = None
        pub_year: int | None = None
        try:
            pubs = self._publication_repo.get_publications(project_id)
            pub = next(
                (
                    x
                    for x in pubs
                    if getattr(x, "record_id", None) == publication_id
                    or getattr(x, "publication_id", None) == publication_id
                ),
                None,
            )
            if pub is not None:
                pub_title = getattr(pub, "title", None)
                pub_year = getattr(pub, "publication_year", None)
        except Exception:
            pass

        return ResearchGapEvidenceCandidate(
            link_type=link_type,
            target_id=target_id,
            group_item_id=group_item_id,
            publication_id=publication_id,
            latest_revision_id=latest_revision_id,
            traceable=traceable,
            label=label,
            publication_title=pub_title,
            publication_year=pub_year,
            qa_profile=self._adapter.get_qa_profile_summary(project_id, publication_id),
        )


def default_synthesis_gap_service() -> SynthesisGapService:
    return SynthesisGapService()
