from __future__ import annotations

from uuid import UUID

from app.domain.integrity_audit import (
    IntegrityAuditReport,
    IntegrityAuditStatus,
    IntegrityCheckLevel,
    IntegrityCheckResult,
)
from app.repositories.duplicate_merge_repository import (
    DuplicateMergeRepository,
    InMemoryDuplicateMergeRepository,
    SqliteDuplicateMergeRepository,
)
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.import_history_repository import (
    ImportHistoryRepository,
    default_import_history_repository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    default_normalization_execution_repository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder, duplicate_group_builder


class ProjectIntegrityAuditService:
    """Read-only, deterministic data integrity audit service for SLR projects."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        import_history_repository: ImportHistoryRepository | None = None,
        normalization_repository: NormalizationExecutionRepository | None = None,
        decision_repository: DuplicateReviewDecisionRepository | None = None,
        merge_repository: DuplicateMergeRepository | None = None,
        group_builder: DuplicateGroupBuilder = duplicate_group_builder,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._import_history_repo = (
            import_history_repository or default_import_history_repository()
        )
        self._norm_repo = normalization_repository or default_normalization_execution_repository()
        self._decision_repo = (
            decision_repository or default_duplicate_review_decision_repository()
        )
        self._group_builder = group_builder
        self._merge_repo = merge_repository or (
            SqliteDuplicateMergeRepository(self._pub_repo._database_path)
            if hasattr(self._pub_repo, "_database_path")
            else InMemoryDuplicateMergeRepository()
        )

    def audit_project(self, project_id: str) -> IntegrityAuditReport:
        checks: list[IntegrityCheckResult] = []

        # 1. Fetch Working Collection
        try:
            publications = self._pub_repo.get_publications(project_id)
            project_exists = True
        except ProjectNotFoundError:
            publications = []
            project_exists = False
            checks.append(
                IntegrityCheckResult(
                    code="WC_PROJECT_NOT_FOUND",
                    level=IntegrityCheckLevel.ERROR,
                    message=f"Project '{project_id}' was not found in Working Collection.",
                    context={"project_id": project_id},
                )
            )

        if project_exists:
            if not publications:
                checks.append(
                    IntegrityCheckResult(
                        code="WC_EMPTY",
                        level=IntegrityCheckLevel.OK,
                        message="Working Collection is empty.",
                        context={"publication_count": 0},
                    )
                )

            # Check WC publication record_id uniqueness & validity
            seen_ids: set[str] = set()
            duplicate_ids: set[str] = set()
            invalid_ids: list[str] = []

            for pub in publications:
                rec_id_str = str(pub.record_id).strip()
                if not rec_id_str:
                    invalid_ids.append(str(pub.record_id))
                if rec_id_str in seen_ids:
                    duplicate_ids.add(rec_id_str)
                else:
                    seen_ids.add(rec_id_str)

            if duplicate_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="WC_DUPLICATE_RECORD_ID",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"{len(duplicate_ids)} duplicate publication ID(s) found in Working Collection.",
                        context={"duplicate_record_ids": sorted(duplicate_ids)},
                    )
                )

            if invalid_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="WC_INVALID_RECORD_ID",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"{len(invalid_ids)} publication(s) have blank or invalid record IDs.",
                        context={"invalid_record_ids": invalid_ids},
                    )
                )

            # Check Provenance completeness and structural integrity
            missing_provenance_ids: list[str] = []
            incomplete_provenance_ids: list[str] = []

            for pub in publications:
                rec_id_str = str(pub.record_id)
                if not pub.provenance:
                    missing_provenance_ids.append(rec_id_str)
                    continue

                for entry in pub.provenance:
                    if not entry.source or not entry.source_record_id:
                        incomplete_provenance_ids.append(rec_id_str)
                        break

            if missing_provenance_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="WC_PROVENANCE_MISSING",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"{len(missing_provenance_ids)} publication(s) in Working Collection lack provenance metadata.",
                        context={
                            "missing_count": len(missing_provenance_ids),
                            "sample_record_ids": missing_provenance_ids[:10],
                        },
                    )
                )

            if incomplete_provenance_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="WC_PROVENANCE_INCOMPLETE",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"{len(incomplete_provenance_ids)} publication(s) contain incomplete provenance entries (missing source or source_record_id).",
                        context={
                            "incomplete_count": len(incomplete_provenance_ids),
                            "sample_record_ids": incomplete_provenance_ids[:10],
                        },
                    )
                )

        # 2. Check Import History
        import_history = self._import_history_repo.list_for_project(project_id)
        if not import_history:
            checks.append(
                IntegrityCheckResult(
                    code="IH_NO_HISTORY",
                    level=IntegrityCheckLevel.OK,
                    message="No import history records found for project.",
                    context={"import_count": 0},
                )
            )
        else:
            total_imported_records = sum(
                rec.records_count
                for rec in import_history
                if rec.status in ("success", "warning")
            )
            # Inspect negative record counts or invalid status values
            invalid_history_ids = [
                str(rec.import_id) for rec in import_history if rec.records_count < 0
            ]
            if invalid_history_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="IH_INVALID_RECORD_COUNT",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"{len(invalid_history_ids)} import history record(s) contain negative records_count.",
                        context={"invalid_import_ids": invalid_history_ids},
                    )
                )

            if project_exists and total_imported_records != len(publications):
                checks.append(
                    IntegrityCheckResult(
                        code="IH_RECORD_COUNT_MISMATCH",
                        level=IntegrityCheckLevel.WARNING,
                        message=(
                            f"Total successful imported records count ({total_imported_records}) "
                            f"does not match Working Collection size ({len(publications)})."
                        ),
                        context={
                            "history_imported_total": total_imported_records,
                            "working_collection_size": len(publications),
                        },
                    )
                )

        # 3. Check Normalization Execution
        norm_exec = self._norm_repo.get_for_project(project_id)
        if norm_exec is None:
            checks.append(
                IntegrityCheckResult(
                    code="NORM_NOT_EXECUTED",
                    level=IntegrityCheckLevel.OK,
                    message="Normalization stage has not been executed yet.",
                    context={
                        "executed": False,
                        "limitation_note": "NormalizationExecution model stores summary metrics only, no per-publication record references.",
                    },
                )
            )
        else:
            if norm_exec.status != "completed":
                checks.append(
                    IntegrityCheckResult(
                        code="NORM_EXECUTION_FAILED",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"Latest normalization execution status is '{norm_exec.status}'.",
                        context={
                            "status": norm_exec.status,
                            "error_message": norm_exec.error_message,
                            "limitation_note": "NormalizationExecution model stores summary metrics only, no per-publication record references.",
                        },
                    )
                )
            elif project_exists and norm_exec.processed_records != len(publications):
                checks.append(
                    IntegrityCheckResult(
                        code="NORM_RECORD_COUNT_MISMATCH",
                        level=IntegrityCheckLevel.WARNING,
                        message=(
                            f"Latest normalization processed records count ({norm_exec.processed_records}) "
                            f"does not match current Working Collection size ({len(publications)})."
                        ),
                        context={
                            "normalization_processed_records": norm_exec.processed_records,
                            "working_collection_size": len(publications),
                            "limitation_note": "NormalizationExecution model stores summary metrics only, no per-publication record references.",
                        },
                    )
                )

        # 4. Check Deduplication Candidates & Review Decisions
        if project_exists:
            pub_by_id = {pub.record_id: pub for pub in publications}
            candidate_groups = self._group_builder.build(publications)
            candidate_group_ids = {str(g.group_id) for g in candidate_groups}

            if not candidate_groups:
                checks.append(
                    IntegrityCheckResult(
                        code="DEDUP_NO_CANDIDATES",
                        level=IntegrityCheckLevel.OK,
                        message="No candidate duplicate groups detected for project.",
                        context={"candidate_groups_count": 0},
                    )
                )

            # Validate publication presence inside candidate groups
            invalid_member_ids: set[str] = set()
            for group in candidate_groups:
                for pid in group.publication_ids:
                    if pid not in pub_by_id:
                        invalid_member_ids.add(str(pid))

            if invalid_member_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="DEDUP_CANDIDATE_MEMBER_MISSING",
                        level=IntegrityCheckLevel.ERROR,
                        message=f"{len(invalid_member_ids)} publication ID(s) in candidate duplicate groups are missing from Working Collection.",
                        context={"missing_publication_ids": sorted(invalid_member_ids)},
                    )
                )

            # Validate stored review decisions (Check for orphaned decisions)
            stored_decisions = self._decision_repo.list_decisions_for_project(project_id)
            orphaned_group_ids = [
                g_id for g_id in stored_decisions if g_id not in candidate_group_ids
            ]

            if orphaned_group_ids:
                checks.append(
                    IntegrityCheckResult(
                        code="DEDUP_DECISION_ORPHANED",
                        level=IntegrityCheckLevel.WARNING,
                        message=f"{len(orphaned_group_ids)} stored duplicate review decision(s) refer to groups no longer present in candidate groups.",
                        context={"orphaned_group_ids": sorted(orphaned_group_ids)},
                    )
                )

            superseded_by: dict[UUID, UUID | None]
            if not hasattr(self._pub_repo, "get_superseded_by_map"):
                superseded_by = {record_id: None for record_id in pub_by_id}
            else:
                superseded_by = self._pub_repo.get_superseded_by_map(project_id)
            for merge in self._merge_repo.list_merges_for_project(project_id).values():
                member_ids = set(merge.merged_publication_ids)
                missing = sorted(str(record_id) for record_id in member_ids if record_id not in pub_by_id)
                if missing:
                    checks.append(IntegrityCheckResult(code="DEDUP_MERGE_MEMBER_MISSING", level=IntegrityCheckLevel.ERROR, message="Merge record references missing publication members.", context={"group_id": merge.group_id, "missing_publication_ids": missing}))
                    continue
                canonical = merge.canonical_record_id
                if canonical not in member_ids or canonical not in pub_by_id:
                    checks.append(IntegrityCheckResult(code="DEDUP_MERGE_CANONICAL_INVALID", level=IntegrityCheckLevel.ERROR, message="Merge canonical record is invalid.", context={"group_id": merge.group_id}))
                    continue
                if superseded_by.get(canonical) is not None:
                    checks.append(IntegrityCheckResult(code="DEDUP_MERGE_CANONICAL_SUPERSEDED", level=IntegrityCheckLevel.ERROR, message="Merge canonical record must remain active.", context={"group_id": merge.group_id, "canonical_record_id": str(canonical)}))
                invalid_members = [str(member) for member in member_ids - {canonical} if superseded_by.get(member) != canonical]
                if invalid_members:
                    checks.append(IntegrityCheckResult(code="DEDUP_MERGE_SUPERSESSION_INVALID", level=IntegrityCheckLevel.ERROR, message="Non-canonical merge members must point directly to the canonical record.", context={"group_id": merge.group_id, "member_ids": sorted(invalid_members)}))

            existing_ids = set(pub_by_id)
            for record_id, target_id in superseded_by.items():
                if target_id is None:
                    continue
                if target_id == record_id:
                    checks.append(IntegrityCheckResult(code="DEDUP_SUPERSESSION_SELF", level=IntegrityCheckLevel.ERROR, message="A publication cannot supersede itself.", context={"record_id": str(record_id)}))
                elif target_id not in existing_ids:
                    checks.append(IntegrityCheckResult(code="DEDUP_SUPERSESSION_BROKEN", level=IntegrityCheckLevel.ERROR, message="A superseded publication references a missing canonical record.", context={"record_id": str(record_id), "superseded_by": str(target_id)}))
                elif superseded_by.get(target_id) is not None:
                    checks.append(IntegrityCheckResult(code="DEDUP_SUPERSESSION_CHAIN", level=IntegrityCheckLevel.ERROR, message="Supersession chains or cycles are not permitted.", context={"record_id": str(record_id), "superseded_by": str(target_id)}))

        # Sort checks deterministically by code
        sorted_checks = tuple(sorted(checks, key=lambda c: c.code))

        # Compute overall status directly from check levels
        overall_status = IntegrityAuditStatus.OK
        if any(c.level == IntegrityCheckLevel.ERROR for c in sorted_checks):
            overall_status = IntegrityAuditStatus.ERROR
        elif any(c.level == IntegrityCheckLevel.WARNING for c in sorted_checks):
            overall_status = IntegrityAuditStatus.WARNING

        return IntegrityAuditReport(
            project_id=project_id,
            status=overall_status,
            checks=sorted_checks,
        )


default_project_integrity_audit_service = ProjectIntegrityAuditService()
