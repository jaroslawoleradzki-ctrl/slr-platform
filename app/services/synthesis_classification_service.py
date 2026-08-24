"""Service managing Phase 10 Terminology Classification workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.synthesis import (
    ClassificationApprovalState,
    ClassifiedSourceTerm,
    EnergyEffectCategory,
    LeanPracticeCategory,
    TermMapping,
    TermType,
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
from app.repositories.synthesis_classification_repository import (
    SynthesisClassificationRepository,
    default_synthesis_classification_repository,
)
from app.services.active_publication_filter import active_publication_ids


class CategoryNotFoundError(Exception):
    """Raised when an analytical category cannot be found."""


class CategoryDomainMismatchError(Exception):
    """Raised when a term type is mapped to an incompatible category domain."""


class MappingNotFoundError(Exception):
    """Raised when a term mapping is not found."""


class CategoryConflictError(Exception):
    """Raised when a category already exists."""


# Canonical Phase 9 Extraction field keys defined in the official Phase 9 template contract
# (see app/services/extraction_template_seed_service.py - Lean Energy Extraction v1.0.0: E4 & E6).
# No fallback, guessing, or convenience aliases are allowed.
CANONICAL_LEAN_FIELD_KEYS: frozenset[str] = frozenset({"lean_practice"})
CANONICAL_ENERGY_FIELD_KEYS: frozenset[str] = frozenset({"energy_effect_indicator"})


class SynthesisClassificationService:
    """Coordinates terminology discovery, analytical category management, and mapping approvals."""

    def __init__(
        self,
        classification_repo: SynthesisClassificationRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        project_repo: SqliteProjectRepository | None = None,
        publication_repo: SqliteProjectPublicationRepository | None = None,
    ) -> None:
        self._classification_repo = classification_repo or default_synthesis_classification_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._project_repo = project_repo or default_project_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()

    def _ensure_project_exists(self, project_id: str) -> None:
        if self._project_repo.get(project_id) is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found")

    # -------------------------------------------------------------------------
    # Analytical Category Management
    # -------------------------------------------------------------------------

    def list_lean_categories(self, project_id: str) -> list[LeanPracticeCategory]:
        self._ensure_project_exists(project_id)
        return self._classification_repo.list_lean_categories(project_id)

    def get_lean_category(self, project_id: str, category_id: str) -> LeanPracticeCategory | None:
        self._ensure_project_exists(project_id)
        return self._classification_repo.get_lean_category(project_id, category_id)

    def create_lean_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> LeanPracticeCategory:
        self._ensure_project_exists(project_id)
        cat_id = category_id.strip()
        cat_name = name.strip()
        if not cat_id:
            raise ValueError("category_id cannot be blank")
        if not cat_name:
            raise ValueError("category name cannot be blank")

        existing = self._classification_repo.get_lean_category(project_id, cat_id)
        if existing is not None:
            raise CategoryConflictError(f"Lean category '{cat_id}' already exists in project '{project_id}'")

        category = LeanPracticeCategory(
            project_id=project_id,
            category_id=cat_id,
            name=cat_name,
            description=description.strip() if description else None,
            display_order=display_order,
        )
        return self._classification_repo.create_lean_category(category)

    def update_lean_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> LeanPracticeCategory:
        self._ensure_project_exists(project_id)
        cat_name = name.strip()
        if not cat_name:
            raise ValueError("category name cannot be blank")

        existing = self._classification_repo.get_lean_category(project_id, category_id)
        if existing is None:
            raise CategoryNotFoundError(f"Lean category '{category_id}' not found in project '{project_id}'")

        updated = LeanPracticeCategory(
            project_id=project_id,
            category_id=category_id,
            name=cat_name,
            description=description.strip() if description else None,
            display_order=display_order,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._classification_repo.update_lean_category(updated)

    def delete_lean_category(self, project_id: str, category_id: str) -> bool:
        self._ensure_project_exists(project_id)
        return self._classification_repo.delete_lean_category(project_id, category_id)

    def list_energy_categories(self, project_id: str) -> list[EnergyEffectCategory]:
        self._ensure_project_exists(project_id)
        return self._classification_repo.list_energy_categories(project_id)

    def get_energy_category(self, project_id: str, category_id: str) -> EnergyEffectCategory | None:
        self._ensure_project_exists(project_id)
        return self._classification_repo.get_energy_category(project_id, category_id)

    def create_energy_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> EnergyEffectCategory:
        self._ensure_project_exists(project_id)
        cat_id = category_id.strip()
        cat_name = name.strip()
        if not cat_id:
            raise ValueError("category_id cannot be blank")
        if not cat_name:
            raise ValueError("category name cannot be blank")

        existing = self._classification_repo.get_energy_category(project_id, cat_id)
        if existing is not None:
            raise CategoryConflictError(f"Energy category '{cat_id}' already exists in project '{project_id}'")

        category = EnergyEffectCategory(
            project_id=project_id,
            category_id=cat_id,
            name=cat_name,
            description=description.strip() if description else None,
            display_order=display_order,
        )
        return self._classification_repo.create_energy_category(category)

    def update_energy_category(
        self,
        project_id: str,
        category_id: str,
        name: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> EnergyEffectCategory:
        self._ensure_project_exists(project_id)
        cat_name = name.strip()
        if not cat_name:
            raise ValueError("category name cannot be blank")

        existing = self._classification_repo.get_energy_category(project_id, category_id)
        if existing is None:
            raise CategoryNotFoundError(f"Energy category '{category_id}' not found in project '{project_id}'")

        updated = EnergyEffectCategory(
            project_id=project_id,
            category_id=category_id,
            name=cat_name,
            description=description.strip() if description else None,
            display_order=display_order,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._classification_repo.update_energy_category(updated)

    def delete_energy_category(self, project_id: str, category_id: str) -> bool:
        self._ensure_project_exists(project_id)
        return self._classification_repo.delete_energy_category(project_id, category_id)

    # -------------------------------------------------------------------------
    # Terminology Discovery & Mapping
    # -------------------------------------------------------------------------

    def get_workspace_classifications(self, project_id: str) -> dict[str, Any]:
        """Discovers extracted source terms and joins with current analytical mappings."""
        self._ensure_project_exists(project_id)

        # 1. Discover unique source terms from Phase 9 extraction revisions
        active_ids = active_publication_ids(self._publication_repo, project_id)
        records = [
            record
            for record in self._extraction_repo.list_records(project_id)
            if active_ids is None or record.publication_id in active_ids
        ]
        lean_occurrences: dict[str, dict[str, Any]] = {}
        energy_occurrences: dict[str, dict[str, Any]] = {}

        for rec in records:
            rev = self._extraction_repo.get_latest_complete_revision(project_id, rec.publication_id)
            if rev is None:
                continue

            # Scan repeating-group items strictly matching canonical field keys
            for item in rev.group_items:
                for val in item.values:
                    txt = (val.text_value or "").strip()
                    if not txt:
                        continue

                    fkey = val.field_key.strip().lower()
                    if fkey in CANONICAL_LEAN_FIELD_KEYS:
                        entry = lean_occurrences.setdefault(txt, {"count": 0, "pubs": set()})
                        entry["count"] += 1
                        entry["pubs"].add(rec.publication_id)
                    elif fkey in CANONICAL_ENERGY_FIELD_KEYS:
                        entry = energy_occurrences.setdefault(txt, {"count": 0, "pubs": set()})
                        entry["count"] += 1
                        entry["pubs"].add(rec.publication_id)

            # Scan publication-level extracted values strictly matching canonical field keys
            for pval in rev.publication_values:
                ptxt = (pval.text_value or "").strip()
                if not ptxt:
                    continue
                pfkey = pval.field_key.strip().lower()
                if pfkey in CANONICAL_LEAN_FIELD_KEYS:
                    entry = lean_occurrences.setdefault(ptxt, {"count": 0, "pubs": set()})
                    entry["count"] += 1
                    entry["pubs"].add(rec.publication_id)
                elif pfkey in CANONICAL_ENERGY_FIELD_KEYS:
                    entry = energy_occurrences.setdefault(ptxt, {"count": 0, "pubs": set()})
                    entry["count"] += 1
                    entry["pubs"].add(rec.publication_id)

        # 2. Fetch categories and mappings
        lean_categories = self._classification_repo.list_lean_categories(project_id)
        energy_categories = self._classification_repo.list_energy_categories(project_id)

        lean_cat_map = {c.category_id: c.name for c in lean_categories}
        energy_cat_map = {c.category_id: c.name for c in energy_categories}

        all_mappings = self._classification_repo.list_term_mappings(project_id)
        mapping_dict = {(m.term_type, m.source_value): m for m in all_mappings}

        # 3. Build classified term items
        classified_lean_terms: list[ClassifiedSourceTerm] = []
        for term, data in sorted(lean_occurrences.items(), key=lambda x: x[0].lower()):
            m = mapping_dict.get((TermType.LEAN_PRACTICE, term))
            cat_id = m.analytical_category_id if m else None
            cat_name = lean_cat_map.get(cat_id) if cat_id else None
            app_state = m.approval_state if m else ClassificationApprovalState.PENDING
            classified_lean_terms.append(
                ClassifiedSourceTerm(
                    project_id=project_id,
                    term_type=TermType.LEAN_PRACTICE,
                    source_value=term,
                    occurrence_count=data["count"],
                    publication_count=len(data["pubs"]),
                    analytical_category_id=cat_id,
                    analytical_category_name=cat_name,
                    approval_state=app_state,
                    approved_by=m.approved_by if m else None,
                    approved_at=m.approved_at if m else None,
                    mapping_id=m.mapping_id if m else None,
                )
            )

        classified_energy_terms: list[ClassifiedSourceTerm] = []
        for term, data in sorted(energy_occurrences.items(), key=lambda x: x[0].lower()):
            m = mapping_dict.get((TermType.ENERGY_EFFECT, term))
            cat_id = m.analytical_category_id if m else None
            cat_name = energy_cat_map.get(cat_id) if cat_id else None
            app_state = m.approval_state if m else ClassificationApprovalState.PENDING
            classified_energy_terms.append(
                ClassifiedSourceTerm(
                    project_id=project_id,
                    term_type=TermType.ENERGY_EFFECT,
                    source_value=term,
                    occurrence_count=data["count"],
                    publication_count=len(data["pubs"]),
                    analytical_category_id=cat_id,
                    analytical_category_name=cat_name,
                    approval_state=app_state,
                    approved_by=m.approved_by if m else None,
                    approved_at=m.approved_at if m else None,
                    mapping_id=m.mapping_id if m else None,
                )
            )

        # Include mapped terms that might not be in currently active revisions
        for m in all_mappings:
            if m.term_type == TermType.LEAN_PRACTICE and m.source_value not in lean_occurrences:
                classified_lean_terms.append(
                    ClassifiedSourceTerm(
                        project_id=project_id,
                        term_type=TermType.LEAN_PRACTICE,
                        source_value=m.source_value,
                        occurrence_count=0,
                        publication_count=0,
                        analytical_category_id=m.analytical_category_id,
                        analytical_category_name=lean_cat_map.get(m.analytical_category_id),
                        approval_state=m.approval_state,
                        approved_by=m.approved_by,
                        approved_at=m.approved_at,
                        mapping_id=m.mapping_id,
                    )
                )
            elif m.term_type == TermType.ENERGY_EFFECT and m.source_value not in energy_occurrences:
                classified_energy_terms.append(
                    ClassifiedSourceTerm(
                        project_id=project_id,
                        term_type=TermType.ENERGY_EFFECT,
                        source_value=m.source_value,
                        occurrence_count=0,
                        publication_count=0,
                        analytical_category_id=m.analytical_category_id,
                        analytical_category_name=energy_cat_map.get(m.analytical_category_id),
                        approval_state=m.approval_state,
                        approved_by=m.approved_by,
                        approved_at=m.approved_at,
                        mapping_id=m.mapping_id,
                    )
                )

        total_terms = len(classified_lean_terms) + len(classified_energy_terms)
        mapped_count = sum(
            1 for t in (classified_lean_terms + classified_energy_terms) if t.analytical_category_id is not None
        )
        approved_count = sum(
            1
            for t in (classified_lean_terms + classified_energy_terms)
            if t.approval_state == ClassificationApprovalState.APPROVED
        )

        return {
            "project_id": project_id,
            "lean_categories": lean_categories,
            "energy_categories": energy_categories,
            "lean_terms": classified_lean_terms,
            "energy_terms": classified_energy_terms,
            "stats": {
                "total_lean_terms": len(classified_lean_terms),
                "total_energy_terms": len(classified_energy_terms),
                "total_terms": total_terms,
                "mapped_count": mapped_count,
                "approved_count": approved_count,
            },
        }

    def set_term_mapping(
        self,
        project_id: str,
        term_type: TermType,
        source_value: str,
        analytical_category_id: str,
    ) -> TermMapping:
        """Sets or updates an analytical category mapping for an empirical source term."""
        self._ensure_project_exists(project_id)
        s_val = source_value.strip()
        cat_id = analytical_category_id.strip()

        if not s_val:
            raise ValueError("source_value cannot be blank")
        if not cat_id:
            raise ValueError("analytical_category_id cannot be blank")

        # Validate that category exists in the appropriate domain
        if term_type == TermType.LEAN_PRACTICE:
            lean_cat = self._classification_repo.get_lean_category(project_id, cat_id)
            if lean_cat is None:
                raise CategoryNotFoundError(f"Lean category '{cat_id}' not found in project '{project_id}'")
        elif term_type == TermType.ENERGY_EFFECT:
            energy_cat = self._classification_repo.get_energy_category(project_id, cat_id)
            if energy_cat is None:
                raise CategoryNotFoundError(f"Energy category '{cat_id}' not found in project '{project_id}'")
        else:
            raise ValueError(f"Unknown term type: {term_type}")

        existing = self._classification_repo.get_term_mapping(project_id, term_type, s_val)

        # Invariant: If changing category on an existing mapping, approval state resets to PENDING
        now = datetime.now(timezone.utc)
        if existing is not None:
            if existing.analytical_category_id == cat_id:
                # Retain existing approval state if category didn't change
                approval_state = existing.approval_state
                approved_by = existing.approved_by
                approved_at = existing.approved_at
            else:
                approval_state = ClassificationApprovalState.PENDING
                approved_by = None
                approved_at = None

            mapping = TermMapping(
                mapping_id=existing.mapping_id,
                project_id=project_id,
                term_type=term_type,
                source_value=s_val,
                analytical_category_id=cat_id,
                approval_state=approval_state,
                approved_by=approved_by,
                approved_at=approved_at,
                created_at=existing.created_at,
                updated_at=now,
            )
        else:
            mapping = TermMapping(
                project_id=project_id,
                term_type=term_type,
                source_value=s_val,
                analytical_category_id=cat_id,
                approval_state=ClassificationApprovalState.PENDING,
                created_at=now,
                updated_at=now,
            )

        return self._classification_repo.save_term_mapping(mapping)

    def approve_term_mapping(
        self,
        project_id: str,
        term_type: TermType,
        source_value: str,
        reviewer_id: str,
    ) -> TermMapping:
        """Explicitly approves a term mapping by a researcher."""
        self._ensure_project_exists(project_id)
        s_val = source_value.strip()
        rev_id = reviewer_id.strip()

        if not s_val:
            raise ValueError("source_value cannot be blank")
        if not rev_id:
            raise ValueError("reviewer_id cannot be blank")

        existing = self._classification_repo.get_term_mapping(project_id, term_type, s_val)
        if existing is None:
            raise MappingNotFoundError(f"No mapping found for '{s_val}' ({term_type.value}) in project '{project_id}'")

        now = datetime.now(timezone.utc)
        updated = TermMapping(
            mapping_id=existing.mapping_id,
            project_id=project_id,
            term_type=term_type,
            source_value=s_val,
            analytical_category_id=existing.analytical_category_id,
            approval_state=ClassificationApprovalState.APPROVED,
            approved_by=rev_id,
            approved_at=now,
            created_at=existing.created_at,
            updated_at=now,
        )
        return self._classification_repo.save_term_mapping(updated)


def default_synthesis_classification_service() -> SynthesisClassificationService:
    return SynthesisClassificationService(
        classification_repo=default_synthesis_classification_repository(),
        extraction_repo=default_extraction_repository(),
        project_repo=default_project_repository(),
        publication_repo=default_project_publication_repository(),
    )
