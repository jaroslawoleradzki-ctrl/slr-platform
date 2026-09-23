"""Final Independent Integration Review test suite for SLR Platform v0.7.1.

Verifies the integration of WP1, WP2, WP3, and WP4 in an isolated, disposable environment:
1. WP2 <-> WP4 contract: Physical reconciliation leaves database in state from which WP2 rebuilds clean derived state.
2. WP3 <-> WP4 contract: PRISMA accounting before and after physical deletion is semantically identical.
3. WP4 failure-injection matrix: All safety preconditions prevent corruption.
4. History survival with rich metadata: Document JSON, identifiers, provenance, and audit trail survive deletion.
5. Legacy compatibility matrix: Pre-archive projects, in-table removals, missing history handled cleanly without fabrication.
6. End-to-end multi-provider adversarial lifecycle.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.duplicate_review import DuplicateDecision
from app.domain.pre_screening import PreScreeningRemovalReason
from app.domain.project import Project
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.corpus_finalization_repository import SqliteCorpusFinalizationRepository
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.pre_screening_archive_repository import SqlitePreScreeningArchiveRepository
from app.repositories.pre_screening_decision_repository import SqlitePreScreeningDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
from app.services.corpus_derived_state_service import CorpusDerivedStateService
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.pre_screening_review_service import PreScreeningReviewService
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.production_reconciliation_service import (
    ProductionReconciliationService,
    ReconciliationRequest,
    ReconciliationSafetyError,
)
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_workflow_status_service import ProjectWorkflowStatusService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService
from tests.fixtures.factories import make_import_history, make_publication


def _build_test_env(tmp_path: Path, project_id: str = "proj_integration"):
    db_path = tmp_path / "integration_review.db"
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id=project_id, title="Integration Review Project"))

    pubs_repo = SqliteProjectPublicationRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    archive_repo = SqlitePreScreeningArchiveRepository(db_path)
    dup_decisions_repo = SqliteDuplicateReviewDecisionRepository(db_path)
    dup_merge_repo = SqliteDuplicateMergeRepository(db_path)
    screening_decisions_repo = SqliteScreeningDecisionRepository(db_path)
    finalization_repo = SqliteCorpusFinalizationRepository(db_path)
    norm_exec_repo = SqliteNormalizationExecutionRepository(db_path)
    assignments_repo = SqliteScreeningReviewerAssignmentRepository(db_path)
    resolutions_repo = SqliteConflictResolutionRepository(db_path)
    reporting_repo = ScreeningReportingRepository(db_path)
    pre_screening_decisions_repo = SqlitePreScreeningDecisionRepository(db_path)

    input_service = ScreeningInputService(pubs_repo, dup_decisions_repo)
    multi_service = MultiReviewerScreeningService(
        assignments=assignments_repo,
        reporting=reporting_repo,
        input_service=input_service,
        resolutions=resolutions_repo,
    )
    adapter = ScreeningEligibilityAdapter(
        input_service=input_service,
        assignments_repo=assignments_repo,
        decisions_repo=screening_decisions_repo,
        multi_reviewer_service=multi_service,
    )
    workflow_status = ProjectWorkflowStatusService(
        publication_repository=pubs_repo,
        decision_repository=screening_decisions_repo,
        assignment_repository=assignments_repo,
        resolution_repository=resolutions_repo,
        reporting_repository=reporting_repo,
        input_service=input_service,
        multi_reviewer_service=multi_service,
        eligibility_adapter=adapter,
    )
    prisma_service = PrismaMetricsService(
        publication_repository=pubs_repo,
        import_history_repository=history_repo,
        decision_repository=dup_decisions_repo,
        workflow_status_service=workflow_status,
        builder=DuplicateGroupBuilder(),
        archive_repository=archive_repo,
    )
    review_service = PreScreeningReviewService(
        publication_repository=pubs_repo,
        decision_repository=pre_screening_decisions_repo,
        archive_repository=archive_repo,
    )
    dup_service = ProjectDuplicateService(
        repository=pubs_repo,
        decision_repository=dup_decisions_repo,
        merge_repository=dup_merge_repo,
    )
    derived_state_service = CorpusDerivedStateService(
        publication_repository=pubs_repo,
        normalization_execution_repository=norm_exec_repo,
        duplicate_service=dup_service,
        finalization_repository=finalization_repo,
    )
    reconcile_service = ProductionReconciliationService(db_path)

    return {
        "db_path": db_path,
        "project_id": project_id,
        "pubs": pubs_repo,
        "history": history_repo,
        "archive": archive_repo,
        "dup_decisions": dup_decisions_repo,
        "dup_merges": dup_merge_repo,
        "screening_decisions": screening_decisions_repo,
        "finalizations": finalization_repo,
        "norm_exec": norm_exec_repo,
        "prisma": prisma_service,
        "review": review_service,
        "dup_service": dup_service,
        "derived_state": derived_state_service,
        "reconcile": reconcile_service,
    }


def test_wp2_wp4_lifecycle_contract(tmp_path: Path):
    """Verify WP4 physical reconciliation leaves database in state where WP2 rebuilds clean derived state."""
    env = _build_test_env(tmp_path, "wp2_wp4_proj")
    pid = env["project_id"]
    import_id = uuid4()

    # 1. 20 records imported from Crossref
    pubs = [make_publication(i, source="Crossref", source_id=f"CR-{i}") for i in range(1, 21)]
    env["pubs"].import_source_publications(pid, pubs, import_id=import_id)
    env["history"].create(make_import_history(pid, records_count=20, provider="crossref", import_id=import_id))

    # 2. 8 records marked removed in pre-screening (13..20)
    removed_ids = tuple(pubs[i].record_id for i in range(12, 20))
    for rid in removed_ids:
        env["pubs"].update_pre_screening_status(pid, rid, "removed")

    assert env["pubs"].count_by_project(pid) == 20
    assert env["pubs"].count_active_by_project(pid) == 12

    # 3. Execute WP4 reconciliation to archive and physically remove the 8 records
    req = ReconciliationRequest(
        project_id=pid,
        import_id=import_id,
        record_ids=removed_ids,
        expected_target_count=8,
        actor="integration-reviewer",
    )
    report = env["reconcile"].execute(req, backup_acknowledged=True)
    assert report.status == "complete"
    assert report.physical_rows_to_remove == 8
    assert report.expected_active_corpus_after == 12

    # 4. Execute WP2 derived-state rebuild on post-reconciliation DB
    rebuild_report = env["derived_state"].rebuild(pid)
    assert rebuild_report.normalization_processed_records == 12
    assert rebuild_report.normalization_clean_records == 12

    # 5. Verify all contracts
    assert env["pubs"].count_by_project(pid) == 12
    assert env["pubs"].count_active_by_project(pid) == 12
    assert env["archive"].count_archived_for_project(pid) == 8
    assert env["history"].list_for_project(pid)[0].records_count == 20
    assert len(env["screening_decisions"].list_by_project(pid)) == 0


def test_wp3_wp4_prisma_parity_before_and_after_physical_delete(tmp_path: Path):
    """Verify PRISMA accounting before and after physical deletion is semantically identical."""
    env = _build_test_env(tmp_path, "wp3_wp4_proj")
    pid = env["project_id"]
    import_id = uuid4()

    # 20 records: 15 provider, 5 file. Pubs 3 and 4 share a duplicate DOI.
    pubs = [
        make_publication(
            i,
            source="Crossref",
            source_id=f"CR-{i}",
            doi="10.1234/dup" if i in (3, 4) else f"10.1234/unique-{i}",
        )
        for i in range(1, 21)
    ]
    env["pubs"].import_source_publications(pid, pubs, import_id=import_id)
    env["history"].create(make_import_history(pid, records_count=15, source_type="provider", provider="crossref", import_id=import_id))
    env["history"].create(make_import_history(pid, records_count=5, source_type="file", source_database="scopus"))

    # 8 removed during corpus prep (13..20)
    removed_ids = tuple(pubs[i].record_id for i in range(12, 20))
    for rid in removed_ids:
        env["pubs"].update_pre_screening_status(pid, rid, "removed")

    # Formally screen 2 active records: 1 include, 1 exclude
    env["screening_decisions"].save(
        ScreeningDecision(
            project_id=pid,
            publication_id=pubs[0].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="rev_1",
        )
    )
    env["screening_decisions"].save(
        ScreeningDecision(
            project_id=pid,
            publication_id=pubs[1].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="rev_1",
        )
    )

    # Legitimate duplicate merge among active records: merge group via dup_service
    groups = env["dup_service"].get_candidate_duplicate_groups(pid).groups
    assert len(groups) >= 1
    dup_group_id = groups[0].group_id
    env["dup_service"].record_decision(pid, dup_group_id, DuplicateDecision.APPROVE)
    env["dup_service"].merge_group(pid, dup_group_id)

    # PRISMA BEFORE physical deletion
    m_before = env["prisma"].get_metrics(pid, reviewer_id="rev_1")
    assert m_before.total_identified == 20
    assert m_before.records_identified_providers == 15
    assert m_before.records_identified_imports == 5
    assert m_before.records_removed_prescreening == 8
    assert m_before.records_before_dedup == 12
    assert m_before.records_after_technical_merger == 11
    assert m_before.records_screened_title_abstract == 2
    assert m_before.records_excluded_title_abstract == 1

    # Physically reconcile the 8 removed records
    req = ReconciliationRequest(
        project_id=pid,
        import_id=import_id,
        record_ids=removed_ids,
        expected_target_count=8,
        actor="reconciler",
    )
    env["reconcile"].execute(req, backup_acknowledged=True)

    # PRISMA AFTER physical deletion
    m_after = env["prisma"].get_metrics(pid, reviewer_id="rev_1")
    assert m_after.total_identified == m_before.total_identified == 20
    assert m_after.records_identified_providers == m_before.records_identified_providers == 15
    assert m_after.records_identified_imports == m_before.records_identified_imports == 5
    assert m_after.records_removed_prescreening == m_before.records_removed_prescreening == 8
    assert m_after.records_before_dedup == m_before.records_before_dedup == 12
    assert m_after.records_after_technical_merger == m_before.records_after_technical_merger == 11
    assert m_after.records_screened_title_abstract == m_before.records_screened_title_abstract == 2
    assert m_after.records_excluded_title_abstract == m_before.records_excluded_title_abstract == 1


def test_wp4_failure_injection_comprehensive(tmp_path: Path):
    """Verify WP4 failure injection and safety controls A through L."""
    env = _build_test_env(tmp_path, "fail_injection_proj")
    pid = env["project_id"]
    import_id = uuid4()

    pubs = [make_publication(i, source="Crossref", source_id=f"CR-{i}") for i in range(1, 11)]
    env["pubs"].import_source_publications(pid, pubs, import_id=import_id)
    env["history"].create(make_import_history(pid, records_count=10, provider="crossref", import_id=import_id))

    # Mark 3 removed
    removed = tuple(pubs[i].record_id for i in range(7, 10))
    for rid in removed:
        env["pubs"].update_pre_screening_status(pid, rid, "removed")

    service = env["reconcile"]

    # L. Dry-run writes zero changes
    dry_req = ReconciliationRequest(pid, import_id, removed, 3, "actor")
    dry_report = service.dry_run(dry_req)
    assert dry_report.status == "preflight-ok"
    assert env["pubs"].count_by_project(pid) == 10

    # Missing backup acknowledgment
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.execute(dry_req, backup_acknowledged=False)
    assert failure.value.code == "BACKUP_ACKNOWLEDGEMENT_REQUIRED"

    # B. Target not removed
    bad_targets_req = ReconciliationRequest(pid, import_id, (pubs[0].record_id,), 1, "actor")
    with pytest.raises(ReconciliationSafetyError, match="not legacy pre-screening removed"):
        service.dry_run(bad_targets_req)

    # C. Wrong project
    wrong_proj_req = ReconciliationRequest("non_existent_project", import_id, removed, 3, "actor")
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.dry_run(wrong_proj_req)
    assert failure.value.code == "PROJECT_NOT_FOUND"

    # D. Wrong import
    wrong_import_req = ReconciliationRequest(pid, uuid4(), removed, 3, "actor")
    with pytest.raises(ReconciliationSafetyError, match="different or NULL import_id"):
        service.dry_run(wrong_import_req)

    # E. Duplicate ID in allow-list
    dup_allowlist_req = ReconciliationRequest(pid, import_id, (removed[0], removed[0]), 2, "actor")
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.dry_run(dup_allowlist_req)
    assert failure.value.code == "INVALID_ALLOW_LIST"

    # Count mismatch in allow-list
    count_mismatch_req = ReconciliationRequest(pid, import_id, removed, 999, "actor")
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.dry_run(count_mismatch_req)
    assert failure.value.code == "INVALID_ALLOW_LIST"

    # F. Target has formal screening decision
    env["screening_decisions"].save(
        ScreeningDecision(
            project_id=pid,
            publication_id=removed[0],
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="r",
        )
    )
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.dry_run(dry_req)
    assert failure.value.code == "FORMAL_SCREENING_CONFLICT"

    # Clean up screening conflict to test finalization conflict
    with sqlite3.connect(env["db_path"]) as conn:
        conn.execute("DELETE FROM screening_decisions WHERE project_id = ?", (pid,))

    # G. Target belongs to finalized corpus
    fin_id = uuid4()
    with sqlite3.connect(env["db_path"]) as conn:
        conn.execute(
            """INSERT INTO corpus_finalizations(
                finalization_id, project_id, finalized_by, created_at,
                source_records_count, duplicates_removed_count, prescreening_removed_count, retained_count, status
            ) VALUES (?, ?, 'operator', '2026-09-23T00:00:00Z', 10, 0, 0, 10, 'finalized')""",
            (str(fin_id), pid),
        )
        conn.execute(
            """INSERT INTO corpus_finalization_members(
                finalization_id, record_id, disposition, admitted_to_screening
            ) VALUES (?, ?, 'retained_for_screening', 1)""",
            (str(fin_id), str(removed[0])),
        )
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.dry_run(dry_req)
    assert failure.value.code == "FINALIZATION_CONFLICT"

    # Clean up finalization conflict
    with sqlite3.connect(env["db_path"]) as conn:
        conn.execute("DELETE FROM corpus_finalization_members")
        conn.execute("DELETE FROM corpus_finalizations")

    # H. Unknown logical references exist in auxiliary table
    with sqlite3.connect(env["db_path"]) as conn:
        conn.execute("CREATE TABLE custom_user_tags (project_id TEXT, record_id TEXT)")
        conn.execute("INSERT INTO custom_user_tags VALUES (?, ?)", (pid, str(removed[0])))
    with pytest.raises(ReconciliationSafetyError) as failure:
        service.dry_run(dry_req)
    assert failure.value.code == "UNKNOWN_LOGICAL_REFERENCES"
    with sqlite3.connect(env["db_path"]) as conn:
        conn.execute("DROP TABLE custom_user_tags")

    # Successful execution
    res = service.execute(dry_req, backup_acknowledged=True)
    assert res.status == "complete"

    # K. Second execution is safe and idempotent (already-reconciled)
    replay = service.dry_run(dry_req)
    assert replay.status == "already-reconciled"


def test_rich_metadata_archive_and_history_survival(tmp_path: Path):
    """Verify rich publication metadata, provenance, identifiers, and audit info survive physical removal."""
    env = _build_test_env(tmp_path, "rich_meta_proj")
    pid = env["project_id"]
    import_id = uuid4()

    pub = make_publication(
        1,
        title="Complex Systematic Review of Energy Recovery Systems",
        doi="10.1016/j.energy.2026.01.001",
        year=2026,
        source="Crossref",
        source_id="CR-COMPLEX-1",
    )
    env["pubs"].import_source_publications(pid, [pub], import_id=import_id)
    env["pubs"].update_pre_screening_status(pid, pub.record_id, "removed")

    # Record removal decision with notes and reviewer
    env["review"].archive_pre_screening_removal(
        project_id=pid,
        import_id=import_id,
        record_id=pub.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="High-energy physics paper retrieved due to keyword collision",
        reviewer_id="lead_methodologist",
        physical_delete=True,
    )

    # Physical row deleted from working collection
    assert len([p for p in env["pubs"].get_all_publications(pid) if p.record_id == pub.record_id]) == 0

    # Survives in pre_screening_archive
    archived = env["archive"].get_archived_record(pid, pub.record_id)
    assert archived is not None
    assert archived.title == "Complex Systematic Review of Energy Recovery Systems"
    assert any(ident.value == "10.1016/j.energy.2026.01.001" for ident in archived.identifiers)
    assert archived.removal_reason == PreScreeningRemovalReason.RETRIEVAL_ARTEFACT
    assert archived.removal_notes == "High-energy physics paper retrieved due to keyword collision"
    assert archived.removed_by == "lead_methodologist"
    assert archived.import_id == import_id
    assert archived.document["title"] == pub.title


def test_legacy_compatibility_matrix(tmp_path: Path):
    """Verify legacy project states without archive or import history remain deterministically queryable."""
    env = _build_test_env(tmp_path, "legacy_compat_proj")
    pid = env["project_id"]

    # 1. Project without import history
    pubs = [make_publication(i, title=f"Legacy Pub {i}") for i in range(1, 6)]
    env["pubs"].add_publications(pid, pubs)

    metrics = env["prisma"].get_metrics(pid)
    assert metrics.total_identified == 0
    assert metrics.records_before_dedup == 5
    assert metrics.records_after_technical_merger == 5
    assert metrics.records_removed_prescreening == 0

    # 2. Legacy in-place status='removed' without pre_screening_archive record
    env["pubs"].update_pre_screening_status(pid, pubs[4].record_id, "removed")
    metrics_legacy = env["prisma"].get_metrics(pid)
    assert metrics_legacy.records_before_dedup == 4
    assert metrics_legacy.records_after_technical_merger == 4
    assert metrics_legacy.records_removed_prescreening == 1


def test_end_to_end_adversarial_pipeline(tmp_path: Path):
    """Full integrated lifecycle: multiple providers, cross-provider duplicate, pre-screening removal,

    reconciliation, normalization, deduplication, PRISMA, and formal screening.
    """
    env = _build_test_env(tmp_path, "e2e_adversarial_proj")
    pid = env["project_id"]
    cr_import_id = uuid4()
    oa_import_id = uuid4()
    s2_import_id = uuid4()
    file_import_id = uuid4()

    # 1. Multi-provider imports: 50 total records
    # Crossref: 20 records (pub 1 has shared DOI)
    cr_pubs = [
        make_publication(
            i,
            source="Crossref",
            source_id=f"CR-{i}",
            doi="10.5555/shared-doi" if i == 1 else f"10.1000/cr-{i}",
            title="Shared Paper" if i == 1 else f"Crossref Paper {i}",
        )
        for i in range(1, 21)
    ]
    # OpenAlex: 10 records (pub 1 has shared DOI)
    oa_pubs = [
        make_publication(
            100 + i,
            source="OpenAlex",
            source_id=f"W-{i}",
            doi="10.5555/shared-doi" if i == 1 else f"10.2000/oa-{i}",
            title="Shared Paper" if i == 1 else f"OpenAlex Paper {i}",
        )
        for i in range(1, 11)
    ]
    # Semantic Scholar: 10 records
    s2_pubs = [
        make_publication(200 + i, source="Semantic Scholar", source_id=f"S2-{i}", doi=f"10.3000/s2-{i}")
        for i in range(1, 11)
    ]
    # Scopus RIS file: 10 records
    file_pubs = [
        make_publication(300 + i, source="Scopus", source_id=f"SCP-{i}", doi=f"10.4000/scp-{i}")
        for i in range(1, 11)
    ]

    env["pubs"].import_source_publications(pid, cr_pubs, import_id=cr_import_id)
    env["pubs"].import_source_publications(pid, oa_pubs, import_id=oa_import_id)
    env["pubs"].import_source_publications(pid, s2_pubs, import_id=s2_import_id)
    env["pubs"].import_source_publications(pid, file_pubs, import_id=file_import_id)

    env["history"].create(make_import_history(pid, records_count=20, source_type="provider", provider="crossref", import_id=cr_import_id))
    env["history"].create(make_import_history(pid, records_count=10, source_type="provider", provider="openalex", import_id=oa_import_id))
    env["history"].create(make_import_history(pid, records_count=10, source_type="provider", provider="semantic_scholar", import_id=s2_import_id))
    env["history"].create(make_import_history(pid, records_count=10, source_type="file", source_database="scopus", import_id=file_import_id))

    assert env["pubs"].count_by_project(pid) == 50

    # 2. Pre-screening removals: 5 Crossref records removed (16..20)
    cr_removed = tuple(cr_pubs[i].record_id for i in range(15, 20))
    for rid in cr_removed:
        env["pubs"].update_pre_screening_status(pid, rid, "removed")

    # 3. Physically reconcile the 5 Crossref removals
    req = ReconciliationRequest(
        project_id=pid,
        import_id=cr_import_id,
        record_ids=cr_removed,
        expected_target_count=5,
        actor="e2e_operator",
    )
    env["reconcile"].execute(req, backup_acknowledged=True)
    assert env["pubs"].count_by_project(pid) == 45
    assert env["archive"].count_archived_for_project(pid) == 5

    # 4. Run Normalization via derived state rebuild
    rebuild = env["derived_state"].rebuild(pid)
    assert rebuild.normalization_processed_records == 45
    assert rebuild.normalization_clean_records == 45

    # 5. Deduplication detects cross-provider duplicate (cr_pubs[0] and oa_pubs[0])
    candidate_groups = env["dup_service"].get_candidate_duplicate_groups(pid)
    assert candidate_groups.total_groups_count >= 1
    shared_group = [g for g in candidate_groups.groups if g.records_count == 2][0]
    env["dup_service"].record_decision(pid, shared_group.group_id, DuplicateDecision.APPROVE)
    env["dup_service"].merge_group(pid, shared_group.group_id)

    assert env["pubs"].count_active_by_project(pid) == 44  # 45 - 1 duplicate merge

    # 6. Formal Screening: Screen 3 active records
    active_recs = env["pubs"].get_active_publications(pid)
    env["screening_decisions"].save(
        ScreeningDecision(
            project_id=pid,
            publication_id=active_recs[0].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer_1",
        )
    )
    env["screening_decisions"].save(
        ScreeningDecision(
            project_id=pid,
            publication_id=active_recs[1].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer_1",
        )
    )
    env["screening_decisions"].save(
        ScreeningDecision(
            project_id=pid,
            publication_id=active_recs[2].record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="reviewer_1",
        )
    )

    # 7. PRISMA Metrics Verification
    metrics = env["prisma"].get_metrics(pid, reviewer_id="reviewer_1")
    assert metrics.total_identified == 50
    assert metrics.records_identified_providers == 40
    assert metrics.records_identified_imports == 10
    assert metrics.records_removed_prescreening == 5
    assert metrics.records_before_dedup == 45
    assert metrics.records_after_technical_merger == 44
    assert metrics.records_screened_title_abstract == 3
    assert metrics.records_excluded_title_abstract == 1
    assert metrics.provider_breakdown == {
        "crossref": 20,
        "openalex": 10,
        "semantic_scholar": 10,
    }
    assert metrics.manual_source_breakdown == {"scopus": 10}
