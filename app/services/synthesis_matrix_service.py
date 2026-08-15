"""Phase 10: Synthesis Matrix Service (Task 10.3).

Coordinates analytical relation materialization, Lean-EE matrix aggregation,
cell drill-down, QA profile overlay, and deterministic physical unit conversion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.domain.synthesis import (
    AnalyticalRelation,
    AnalyticalRelationDetail,
    ClassificationApprovalState,
    ConvertedValue,
    EvidenceCharacter,
    MatrixCell,
    MatrixCellDetail,
    RelationDirection,
    SynthesisMatrix,
    TermType,
    convert_physical_energy_unit,
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
from app.services.synthesis_classification_service import (
    CANONICAL_ENERGY_FIELD_KEYS,
    CANONICAL_LEAN_FIELD_KEYS,
    CategoryNotFoundError,
)

if TYPE_CHECKING:
    from app.domain.extraction import ExtractedGroupItemState, ExtractionRevision


class RelationNotFoundError(Exception):
    """Raised when an analytical relation is not found."""


class UnitConversionError(Exception):
    """Raised when a unit conversion request is invalid."""


class SynthesisMatrixService:
    """Business service for Lean–EE matrix aggregation and analytical relation management."""

    def __init__(
        self,
        matrix_repo: SqliteSynthesisMatrixRepository | None = None,
        classification_repo: SqliteSynthesisClassificationRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        project_repo: SqliteProjectRepository | None = None,
        qa_repo: SqliteQualityAssessmentRepository | None = None,
        publication_repo: SqliteProjectPublicationRepository | None = None,
    ) -> None:
        self._matrix_repo = matrix_repo or default_synthesis_matrix_repository()
        self._classification_repo = classification_repo or default_synthesis_classification_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._project_repo = project_repo or default_project_repository()
        self._qa_repo = qa_repo or default_quality_assessment_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._adapter = SynthesisExtractionAdapter(
            extraction_repo=self._extraction_repo,
            qa_repo=self._qa_repo,
        )

    def _ensure_project_exists(self, project_id: str) -> None:
        project = self._project_repo.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found")

    def synchronize_analytical_relations(self, project_id: str) -> list[AnalyticalRelation]:
        """Constructs or refreshes analytical relations from Phase 9 evidence and Task 10.2 mappings."""
        self._ensure_project_exists(project_id)

        # 1. Fetch all classification mappings and active categories for this project
        lean_mappings = {
            m.source_value: m
            for m in self._classification_repo.list_term_mappings(project_id, TermType.LEAN_PRACTICE)
        }
        energy_mappings = {
            m.source_value: m
            for m in self._classification_repo.list_term_mappings(project_id, TermType.ENERGY_EFFECT)
        }

        valid_lean_cats = {c.category_id for c in self._classification_repo.list_lean_categories(project_id)}
        valid_energy_cats = {c.category_id for c in self._classification_repo.list_energy_categories(project_id)}

        # 2. Fetch existing materialized relations to preserve researcher edits (like converted_value)
        existing_relations = {
            rel.group_item_id: rel
            for rel in self._matrix_repo.list_analytical_relations(project_id)
        }

        # 3. Read latest extraction revisions across all publications in the project
        records = self._extraction_repo.list_records(project_id)
        materialized: list[AnalyticalRelation] = []

        for rec in records:
            rev: ExtractionRevision | None = self._extraction_repo.get_latest_revision(
                project_id, rec.publication_id
            )
            if rev is None or not rev.group_items:
                continue

            for group_item in rev.group_items:
                rel = self._build_analytical_relation_from_item(
                    project_id=project_id,
                    publication_id=rec.publication_id,
                    revision=rev,
                    group_item=group_item,
                    lean_mappings=lean_mappings,
                    energy_mappings=energy_mappings,
                    valid_lean_cats=valid_lean_cats,
                    valid_energy_cats=valid_energy_cats,
                    existing_relation=existing_relations.get(group_item.group_item_id),
                )
                if rel is not None:
                    materialized.append(rel)

        # Save all materialized relations
        if materialized:
            self._matrix_repo.save_analytical_relations(materialized)

        return self._matrix_repo.list_analytical_relations(project_id)

    def _build_analytical_relation_from_item(
        self,
        project_id: str,
        publication_id: UUID,
        revision: ExtractionRevision,
        group_item: ExtractedGroupItemState,
        lean_mappings: dict[str, Any],
        energy_mappings: dict[str, Any],
        valid_lean_cats: set[str],
        valid_energy_cats: set[str],
        existing_relation: AnalyticalRelation | None,
    ) -> AnalyticalRelation | None:
        # Extract source practice & effect using canonical keys
        source_practice: str | None = None
        source_effect: str | None = None
        magnitude: float | None = None
        original_unit: str | None = None
        evidence_character = EvidenceCharacter.EMPIRICAL
        direction = RelationDirection.CANNOT_DETERMINE
        context_summary: str | None = None

        for val in group_item.values:
            if val.field_key in CANONICAL_LEAN_FIELD_KEYS and val.text_value:
                source_practice = val.text_value.strip()
            elif val.field_key in CANONICAL_ENERGY_FIELD_KEYS and val.text_value:
                source_effect = val.text_value.strip()
            elif val.field_key == "effect_magnitude":
                if val.float_value is not None:
                    magnitude = val.float_value
                elif val.int_value is not None:
                    magnitude = float(val.int_value)
                if val.unit_value:
                    original_unit = val.unit_value.strip()
            elif val.field_key == "evidence_character" and val.text_value:
                evidence_character = self._parse_evidence_character(val.text_value)
            elif val.field_key == "direction" and val.text_value:
                direction = self._parse_direction(val.text_value)
            elif val.field_key in ("impact_mechanism", "moderating_conditions") and val.text_value:
                if context_summary:
                    context_summary += f"; {val.text_value.strip()}"
                else:
                    context_summary = val.text_value.strip()

        # If source practice or effect not found in item values, check non-canonical fallback for magnitude
        if magnitude is None:
            for val in group_item.values:
                if val.float_value is not None:
                    magnitude = val.float_value
                    if val.unit_value:
                        original_unit = val.unit_value.strip()
                    break

        if not source_practice or not source_effect:
            return None

        # Determine direction default if unstated
        if direction == RelationDirection.CANNOT_DETERMINE:
            if magnitude is not None:
                # In Lean/Energy, negative change in energy use or positive improvement is positive outcome
                direction = RelationDirection.POSITIVE
            else:
                direction = RelationDirection.POSITIVE

        # Resolve analytical category assignments from researcher mappings
        lean_cat_id: str | None = None
        energy_cat_id: str | None = None
        is_lean_approved = False
        is_energy_approved = False

        if source_practice in lean_mappings:
            m = lean_mappings[source_practice]
            if m.analytical_category_id in valid_lean_cats:
                lean_cat_id = m.analytical_category_id
                is_lean_approved = m.approval_state == ClassificationApprovalState.APPROVED

        if source_effect in energy_mappings:
            m = energy_mappings[source_effect]
            if m.analytical_category_id in valid_energy_cats:
                energy_cat_id = m.analytical_category_id
                is_energy_approved = m.approval_state == ClassificationApprovalState.APPROVED

        approval_state = (
            ClassificationApprovalState.APPROVED
            if (is_lean_approved and is_energy_approved)
            else ClassificationApprovalState.PENDING
        )

        # Preserve converted_value if unit didn't change
        converted_val: ConvertedValue | None = None
        rel_id = uuid4()
        if existing_relation is not None:
            rel_id = existing_relation.relation_id
            if (
                existing_relation.converted_value is not None
                and existing_relation.original_unit == original_unit
                and existing_relation.magnitude == magnitude
            ):
                converted_val = existing_relation.converted_value

        return AnalyticalRelation(
            relation_id=rel_id,
            project_id=project_id,
            publication_id=publication_id,
            latest_revision_id=revision.revision_id,
            group_item_id=group_item.group_item_id,
            item_index=group_item.item_index,
            source_practice=source_practice,
            analytical_lean_category_id=lean_cat_id,
            source_effect=source_effect,
            analytical_energy_category_id=energy_cat_id,
            direction=direction,
            magnitude=magnitude,
            original_unit=original_unit,
            converted_value=converted_val,
            evidence_character=evidence_character,
            context_summary=context_summary,
            approval_state=approval_state,
        )

    def _parse_evidence_character(self, text: str) -> EvidenceCharacter:
        t = text.lower()
        if "qualitative" in t:
            return EvidenceCharacter.QUALITATIVE
        if "estimated" in t or "modeled" in t:
            return EvidenceCharacter.ESTIMATED
        if "postulated" in t or "theoretical" in t:
            return EvidenceCharacter.POSTULATED
        return EvidenceCharacter.EMPIRICAL

    def _parse_direction(self, text: str) -> RelationDirection:
        t = text.lower().strip()
        if t in ("positive", "pos", "+", "improvement", "reduction"):
            return RelationDirection.POSITIVE
        if t in ("negative", "neg", "-", "degradation", "increase"):
            return RelationDirection.NEGATIVE
        if t in ("no_effect", "none", "0", "neutral"):
            return RelationDirection.NO_EFFECT
        if t in ("mixed", "inconsistent"):
            return RelationDirection.MIXED
        return RelationDirection.CANNOT_DETERMINE

    def get_matrix(self, project_id: str) -> SynthesisMatrix:
        """Calculates the M × N Lean Category × Energy Effect Category analytical matrix."""
        self._ensure_project_exists(project_id)

        # 1. Synchronize to ensure materialized relations reflect latest evidence and mappings
        self.synchronize_analytical_relations(project_id)

        lean_categories = self._classification_repo.list_lean_categories(project_id)
        energy_categories = self._classification_repo.list_energy_categories(project_id)
        relations = self._matrix_repo.list_analytical_relations(project_id)

        # 2. Group relations by (lean_category_id, energy_category_id)
        cell_lookup: dict[tuple[str, str], list[AnalyticalRelation]] = {}
        unclassified_count = 0
        all_pub_ids: set[UUID] = set()

        for rel in relations:
            all_pub_ids.add(rel.publication_id)
            if (
                not rel.analytical_lean_category_id
                or not rel.analytical_energy_category_id
                or rel.approval_state != ClassificationApprovalState.APPROVED
            ):
                unclassified_count += 1
                continue

            key = (rel.analytical_lean_category_id, rel.analytical_energy_category_id)
            cell_lookup.setdefault(key, []).append(rel)

        # 3. Construct matrix cells for every Lean × Energy combination
        cells: list[MatrixCell] = []
        for l_cat in lean_categories:
            for e_cat in energy_categories:
                cell_rels = cell_lookup.get((l_cat.category_id, e_cat.category_id), [])
                cell_pubs = {r.publication_id for r in cell_rels}

                dir_dist: dict[str, int] = {}
                for r in cell_rels:
                    dir_dist[r.direction.value] = dir_dist.get(r.direction.value, 0) + 1

                char_dist: dict[str, int] = {}
                for r in cell_rels:
                    char_dist[r.evidence_character.value] = char_dist.get(r.evidence_character.value, 0) + 1

                cells.append(
                    MatrixCell(
                        lean_category_id=l_cat.category_id,
                        lean_category_name=l_cat.name,
                        energy_category_id=e_cat.category_id,
                        energy_category_name=e_cat.name,
                        relation_count=len(cell_rels),
                        publication_count=len(cell_pubs),
                        direction_distribution=dir_dist,
                        evidence_character_distribution=char_dist,
                    )
                )

        return SynthesisMatrix(
            project_id=project_id,
            lean_categories=lean_categories,
            energy_categories=energy_categories,
            cells=cells,
            total_relations=len(relations),
            total_publications=len(all_pub_ids),
            unclassified_relations_count=unclassified_count,
        )

    def get_matrix_cell_detail(
        self, project_id: str, lean_category_id: str, energy_category_id: str
    ) -> MatrixCellDetail:
        """Retrieves detailed drill-down information for a specific matrix cell."""
        self._ensure_project_exists(project_id)
        self.synchronize_analytical_relations(project_id)

        lean_cat = self._classification_repo.get_lean_category(project_id, lean_category_id)
        if lean_cat is None:
            raise CategoryNotFoundError(f"Lean category '{lean_category_id}' not found in project '{project_id}'")

        energy_cat = self._classification_repo.get_energy_category(project_id, energy_category_id)
        if energy_cat is None:
            raise CategoryNotFoundError(f"Energy category '{energy_category_id}' not found in project '{project_id}'")

        cell_rels = self._matrix_repo.list_analytical_relations_for_cell(
            project_id=project_id,
            lean_category_id=lean_category_id,
            energy_category_id=energy_category_id,
        )

        # Build relation details with publication metadata, QA profile, and quote provenance
        details: list[AnalyticalRelationDetail] = []
        cell_pubs: set[UUID] = set()
        dir_dist: dict[str, int] = {}
        char_dist: dict[str, int] = {}

        for rel in cell_rels:
            cell_pubs.add(rel.publication_id)
            dir_dist[rel.direction.value] = dir_dist.get(rel.direction.value, 0) + 1
            char_dist[rel.evidence_character.value] = char_dist.get(rel.evidence_character.value, 0) + 1

            # Fetch publication title & year
            pub_title: str | None = None
            pub_year: int | None = None
            try:
                pubs = self._publication_repo.get_publications(project_id)
                pub = next(
                    (
                        p
                        for p in pubs
                        if getattr(p, "record_id", None) == rel.publication_id
                        or getattr(p, "publication_id", None) == rel.publication_id
                    ),
                    None,
                )
                if pub is not None:
                    pub_title = pub.title
                    pub_year = pub.publication_year
            except Exception:
                pass

            # Fetch QA profile
            qa_profile = self._adapter.get_qa_profile_summary(project_id, rel.publication_id)

            # Fetch source quote / locator from extraction revision
            quote: str | None = None
            page: str | None = None
            section: str | None = None

            rev = self._extraction_repo.get_latest_revision(project_id, rel.publication_id)
            if rev is not None:
                item = next((i for i in rev.group_items if i.group_item_id == rel.group_item_id), None)
                if item is not None:
                    for v in item.values:
                        if v.source_quote and not quote:
                            quote = v.source_quote
                        if v.source_page and not page:
                            page = v.source_page
                        if v.source_section and not section:
                            section = v.source_section

            details.append(
                AnalyticalRelationDetail(
                    relation=rel,
                    publication_title=pub_title,
                    publication_year=pub_year,
                    source_quote=quote,
                    source_page=page,
                    source_section=section,
                    qa_profile=qa_profile,
                )
            )

        return MatrixCellDetail(
            lean_category=lean_cat,
            energy_category=energy_cat,
            relation_count=len(cell_rels),
            publication_count=len(cell_pubs),
            direction_distribution=dir_dist,
            evidence_character_distribution=char_dist,
            relations=details,
        )

    def calculate_unit_conversion(
        self, project_id: str, relation_id: UUID, target_unit: str
    ) -> ConvertedValue:
        """Calculates preview unit conversion without mutating or auto-saving."""
        self._ensure_project_exists(project_id)

        rel = self._matrix_repo.get_analytical_relation(project_id, relation_id)
        if rel is None:
            raise RelationNotFoundError(f"Analytical relation '{relation_id}' not found in project '{project_id}'")

        if rel.magnitude is None or not rel.original_unit:
            raise UnitConversionError(
                f"Relation '{relation_id}' does not have a convertible numeric magnitude and unit"
            )

        try:
            converted_val, standard_unit, rule_desc = convert_physical_energy_unit(
                value=rel.magnitude,
                from_unit=rel.original_unit,
                to_unit=target_unit,
            )
        except ValueError as e:
            raise UnitConversionError(str(e)) from e

        return ConvertedValue(
            transformed_value=converted_val,
            transformed_unit=standard_unit,
            conversion_rule=rule_desc,
        )

    def save_converted_value(
        self, project_id: str, relation_id: UUID, target_unit: str
    ) -> AnalyticalRelation:
        """Calculates and explicitly saves researcher-approved unit conversion."""
        self._ensure_project_exists(project_id)

        converted = self.calculate_unit_conversion(project_id, relation_id, target_unit)
        success = self._matrix_repo.update_converted_value(project_id, relation_id, converted)
        if not success:
            raise RelationNotFoundError(f"Analytical relation '{relation_id}' not found in project '{project_id}'")

        updated = self._matrix_repo.get_analytical_relation(project_id, relation_id)
        if updated is None:
            raise RelationNotFoundError(f"Analytical relation '{relation_id}' not found after update")
        return updated


def default_synthesis_matrix_service() -> SynthesisMatrixService:
    return SynthesisMatrixService()
