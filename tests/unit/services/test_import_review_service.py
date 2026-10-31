import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.import_review import ImportReviewDecisionType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    SqliteImportHistoryRepository,
)
from app.repositories.import_review_repository import SqliteImportReviewRepository
from app.repositories.import_source_record_repository import (
    ImportSkipAuditRecord,
    ImportSourceRecord,
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.import_review_service import (
    ImportNotFoundError,
    ImportRejectionBlockedError,
    ImportReviewService,
    ImportReviewStateError,
)

PROJECT_ID = "import-review-project"


def _publication(number: int, doi: str = "10.1000/import") -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Imported publication {number}",
        publication_year=2024,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
        provenance=[ProvenanceEntry(source="ris", source_record_id=doi)],
    )


def _environment(tmp_path: Path, publications: list[Publication], *, warnings=("Skipped 2 duplicates.",)):
    database = tmp_path / "import-review.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    publications_repo = SqliteProjectPublicationRepository(database)
    reviews = SqliteImportReviewRepository(database)
    normalizations = SqliteNormalizationExecutionRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    import_id = uuid4()
    history.create(
        ImportHistoryRecord(
            import_id=import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="review.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=len(publications),
            total_available=None,
            status="warning" if warnings else "success",
            warnings=warnings,
            created_at=datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc),
        )
    )
    for index, publication in enumerate(publications):
        sources.create_source_record(
            ImportSourceRecord(
                source_record_id=f"source-{index + 1}",
                project_id=PROJECT_ID,
                import_id=import_id,
                source_filename="review.ris",
                source_file_hash=None,
                source_record_index=index + 1,
                title=publication.title,
                publication_year=publication.publication_year,
                original_doi="10.1000/import",
                normalized_doi="10.1000/import",
                authors=("Reviewer",),
                document_type="journal_article",
                provenance=publication.provenance[0].model_dump(mode="json"),
                canonical_publication_id=str(publication.record_id),
                recovery_status="imported",
            )
        )
    publications_repo.import_source_publications(
        PROJECT_ID, publications, import_id=import_id, preserve_source_occurrences=True
    )
    service = ImportReviewService(
        publication_repository=publications_repo,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
        duplicate_decision_repository=decisions,
        merge_repository=merges,
        normalization_repository=normalizations,
        transaction_manager=SqliteTransactionManager(database),
    )
    return database, service, publications_repo, sources, history, reviews, import_id, decisions, merges


def _research_table_snapshot(database: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(database) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {
            table: sorted(
                connection.execute(f'SELECT * FROM "{table}"').fetchall(),
                key=repr,
            )
            for table in table_names
            if table not in {"import_review_decisions", "schema_migrations"}
        }


def test_acceptance_preserves_publications_source_records_and_research_tables(
    tmp_path: Path,
) -> None:
    publication = _publication(1)
    database, service, publications, sources, history, _, import_id, decisions, _ = _environment(
        tmp_path, [publication]
    )
    decisions.save_decision(
        PROJECT_ID,
        "group-1",
        DuplicateGroupReviewDecision(
            decision=DuplicateDecision.APPROVE,
            rationale="Keep both records.",
        ),
    )
    sources.create_skip_audit(
        ImportSkipAuditRecord(
            skip_audit_id="skip-1",
            project_id=PROJECT_ID,
            import_id=import_id,
            source_filename="review.ris",
            source_file_hash=None,
            source_record_index=99,
            source_title="Duplicate record",
            source_doi="10.1000/import",
            matched_publication_id=str(publication.record_id),
            match_type="exact_doi",
            match_reason="Duplicate DOI.",
            proposed_action="skip",
            review_required=False,
            created_at=datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc),
        )
    )
    # Non-empty downstream research records: acceptance must not touch them.
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO screening_decisions (decision_id, project_id, publication_id, stage, outcome, reviewer_id, rationale, decided_at) VALUES ('sd-1', ?, ?, 'title_abstract', 'include', 'alice', 'Included.', '2026-10-27T10:00:00Z')",
            (PROJECT_ID, str(publication.record_id)),
        )
        connection.execute(
            "INSERT INTO quality_assessment_tools (tool_id, name, created_at) VALUES ('tool-1', 'CASP', '2026-10-27T10:00:00Z')"
        )
        connection.execute(
            "INSERT INTO quality_assessment_templates (template_id, tool_id, template_key, name, version, is_active, created_at) VALUES ('tpl-1', 'tool-1', 'casp', 'CASP v1', 1, 1, '2026-10-27T10:00:00Z')"
        )
        connection.execute(
            "INSERT INTO quality_assessments (assessment_id, project_id, publication_id, reviewer_id, template_id, assessed_at) VALUES ('qa-1', ?, ?, 'alice', 'tpl-1', '2026-10-27T10:00:00Z')",
            (PROJECT_ID, str(publication.record_id)),
        )
        connection.execute(
            "INSERT INTO extraction_templates (template_id, name, created_at) VALUES ('et-1', 'Extraction', '2026-10-27T10:00:00Z')"
        )
        connection.execute(
            "INSERT INTO extraction_template_versions (template_id, version, schema_json, created_at) VALUES ('et-1', '1.0', '{}', '2026-10-27T10:00:00Z')"
        )
        connection.execute(
            "INSERT INTO extraction_records (record_id, project_id, publication_id, template_id, template_version, current_status, created_at, updated_at) VALUES ('er-1', ?, ?, 'et-1', '1.0', 'in_progress', '2026-10-27T10:00:00Z', '2026-10-27T10:00:00Z')",
            (PROJECT_ID, str(publication.record_id)),
        )
        connection.execute(
            "INSERT INTO synthesis_analytical_relations (relation_id, project_id, publication_id, latest_revision_id, group_item_id, source_practice, source_effect, direction, evidence_character, approval_state) VALUES ('syn-1', ?, ?, 'rev1', 'item1', 'Kaizen', 'Energy', 'positive', 'empirical', 'approved')",
            (PROJECT_ID, str(publication.record_id)),
        )
        connection.commit()
    before = _research_table_snapshot(database)

    service.accept(PROJECT_ID, import_id, reviewer_id="alice")

    after = _research_table_snapshot(database)
    assert after == before
    assert publications.get_publications(PROJECT_ID) == [publication]
    assert len(sources.list_source_records_for_import(PROJECT_ID, import_id)) == 1
    assert len(sources.list_skip_audit_for_import(PROJECT_ID, import_id)) == 1
    assert decisions.get_decision(PROJECT_ID, "group-1") is not None
    assert history.get(PROJECT_ID, import_id).status == "warning"
    assert service.get_review(PROJECT_ID, import_id).effective_status == "success"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM screening_decisions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM quality_assessments").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM extraction_records").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM synthesis_analytical_relations").fetchone()[0] == 1


def test_accept_records_one_decision_without_changing_publications(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, sources, history, reviews, import_id, _, _ = _environment(
        tmp_path, [publication]
    )

    decision = service.accept(
        PROJECT_ID, import_id, reviewer_id="alice", rationale="Verified warning."
    )
    repeated = service.accept(PROJECT_ID, import_id, reviewer_id="alice")

    assert decision.decision == ImportReviewDecisionType.ACCEPTED.value
    assert repeated == decision
    assert publications.get_publications(PROJECT_ID) == [publication]
    assert len(sources.list_source_records_for_import(PROJECT_ID, import_id)) == 1
    assert history.get(PROJECT_ID, import_id).status == "warning"
    detail = service.get_review(PROJECT_ID, import_id)
    assert detail.effective_status == "success"
    assert detail.review_status == "accepted"
    assert detail.can_accept is False
    assert reviews.get(PROJECT_ID, import_id) == decision


def test_rejection_deletes_only_owned_publications_and_retains_audit(tmp_path: Path) -> None:
    first = _publication(1, "10.1000/first")
    second = _publication(2, "10.1000/second")
    database, service, publications, sources, history, _, import_id, _, _ = _environment(
        tmp_path, [first, second]
    )

    decision = service.reject(
        PROJECT_ID,
        import_id,
        reviewer_id="alice",
        rationale="Wrong file.",
        confirm_rejection=True,
    )

    assert decision.decision == ImportReviewDecisionType.REJECTED.value
    assert publications.get_publications(PROJECT_ID) == []
    assert len(sources.list_source_records_for_import(PROJECT_ID, import_id)) == 2
    assert history.get(PROJECT_ID, import_id) is not None
    assert decision.deleted_publication_count == 2
    assert decision.retained_source_record_count == 2
    assert decision.removed_publication_snapshots


def test_rejection_requires_confirmation(tmp_path: Path) -> None:
    _, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [_publication(1)]
    )
    from app.services.import_review_service import ImportRejectionConfirmationRequired

    with pytest.raises(ImportRejectionConfirmationRequired):
        service.reject(PROJECT_ID, import_id, reviewer_id="alice")
    assert publications.get_publications(PROJECT_ID)


def test_shared_publication_blocks_rejection(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, sources, history, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    other_import_id = uuid4()
    history.create(
        ImportHistoryRecord(
            import_id=other_import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="other.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=0,
            total_available=None,
            status="success",
            warnings=(),
            created_at=datetime(2026, 10, 27, 11, 0, tzinfo=timezone.utc),
        )
    )
    sources.create_source_record(
        ImportSourceRecord(
            source_record_id="other-source",
            project_id=PROJECT_ID,
            import_id=other_import_id,
            source_filename="other.ris",
            source_file_hash=None,
            source_record_index=1,
            title=publication.title,
            publication_year=publication.publication_year,
            original_doi="10.1000/import",
            normalized_doi="10.1000/import",
            authors=("Reviewer",),
            document_type="journal_article",
            provenance=publication.provenance[0].model_dump(mode="json"),
            canonical_publication_id=str(publication.record_id),
            recovery_status="linked",
        )
    )

    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(
            PROJECT_ID,
            import_id,
            reviewer_id="alice",
            confirm_rejection=True,
        )
    assert "shared_publication" in {blocker.code for blocker in blocked.value.blockers}
    assert publications.get_publications(PROJECT_ID) == [publication]


def test_screening_decision_blocks_rejection(tmp_path: Path) -> None:
    import sqlite3

    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO screening_decisions
                (decision_id, project_id, publication_id, stage, outcome, reviewer_id, rationale, decided_at)
            VALUES (?, ?, ?, 'title_abstract', 'include', 'alice', NULL, ?)
            """,
            ("decision-1", PROJECT_ID, str(publication.record_id), datetime.now(timezone.utc).isoformat()),
        )

    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(
            PROJECT_ID,
            import_id,
            reviewer_id="alice",
            confirm_rejection=True,
        )
    assert "screening_decision" in {blocker.code for blocker in blocked.value.blockers}
    assert publications.get_publications(PROJECT_ID) == [publication]


def test_success_import_cannot_receive_warning_decision(tmp_path: Path) -> None:
    _, service, _, _, _, _, import_id, _, _ = _environment(
        tmp_path, [_publication(1)], warnings=()
    )
    with pytest.raises(ImportReviewStateError):
        service.accept(PROJECT_ID, import_id, reviewer_id="alice")


def test_missing_import_is_not_found(tmp_path: Path) -> None:
    _, service, _, _, _, _, _, _, _ = _environment(tmp_path, [_publication(1)])
    with pytest.raises(ImportNotFoundError):
        service.get_review(PROJECT_ID, uuid4())


def test_merged_publication_blocks_rejection(tmp_path: Path) -> None:
    from app.services.project_duplicate_service import ProjectDuplicateService

    first = _publication(1, "10.1000/merged")
    second = _publication(2, "10.1000/merged")
    database, service, publications, _, _, _, import_id, decisions, merges = _environment(
        tmp_path, [first, second]
    )
    duplicate_service = ProjectDuplicateService(
        publications,
        decisions,
        merge_repository=merges,
        transaction_manager=SqliteTransactionManager(database),
    )
    group_id = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups[0].group_id
    duplicate_service.merge_group(PROJECT_ID, group_id)

    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)
    assert "merged_publication" in {blocker.code for blocker in blocked.value.blockers}
    assert len(publications.get_all_publications(PROJECT_ID)) == 2


def test_duplicate_review_decision_blocks_rejection(tmp_path: Path) -> None:
    first = _publication(1, "10.1000/decided")
    second = _publication(2, "10.1000/decided")
    database, service, publications, sources, _, _, import_id, decisions, _ = _environment(
        tmp_path, [first, second]
    )
    group = DuplicateGroupBuilder().build(
        publications.get_publications(PROJECT_ID), include_title_candidates=True
    )[0]
    decisions.save_decision(
        PROJECT_ID,
        str(group.group_id),
        DuplicateGroupReviewDecision(decision=DuplicateDecision.REJECT),
    )
    # The first observation stays immutable as PENDING even after a reviewer
    # decision exists. Remove one live member so this decision is discoverable
    # only through snapshot membership during the rejection safety check.
    sources.record_candidate_group_snapshot(
        PROJECT_ID,
        str(group.group_id),
        [str(first.record_id), str(second.record_id)],
        match_type=group.match_type,
        match_reason=group.match_reason,
        status="PENDING",
    )
    publications.delete_publication(PROJECT_ID, second.record_id)
    before_snapshot = sources.list_candidate_group_snapshots(PROJECT_ID)
    assert before_snapshot[0]["status"] == "PENDING"

    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)
    assert "duplicate_decision" in {blocker.code for blocker in blocked.value.blockers}
    assert publications.get_all_publications(PROJECT_ID) == [first]
    assert sources.list_candidate_group_snapshots(PROJECT_ID) == before_snapshot
    assert decisions.get_decision(PROJECT_ID, str(group.group_id)).decision is DuplicateDecision.REJECT


def test_import_rejection_projection_failure_rolls_back_corpus_and_projection(tmp_path: Path, monkeypatch) -> None:
    first = _publication(1, "10.1000/reject-projection")
    second = _publication(2, "10.1000/reject-projection")
    database, service, publications, sources, history, _, import_id, _, _ = _environment(
        tmp_path, [first, second]
    )
    projection = service._duplicate_projection
    assert projection is not None
    transaction_manager = SqliteTransactionManager(database)
    with transaction_manager.transaction() as connection:
        projection.materialize_candidate_group_projection(PROJECT_ID, connection=connection)
    before_ids = [item.duplicate_candidate_group_id for item in sources.list_source_records(PROJECT_ID)]
    before_snapshots = sources.list_candidate_group_snapshots(PROJECT_ID)
    original = projection.materialize_candidate_group_projection

    def fail_after_projection(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected import-rejection projection failure")

    monkeypatch.setattr(projection, "materialize_candidate_group_projection", fail_after_projection)
    with pytest.raises(RuntimeError, match="import-rejection projection failure"):
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)

    assert publications.get_all_publications(PROJECT_ID) == [first, second]
    assert history.get(PROJECT_ID, import_id).status == "warning"
    assert [item.duplicate_candidate_group_id for item in sources.list_source_records(PROJECT_ID)] == before_ids
    assert sources.list_candidate_group_snapshots(PROJECT_ID) == before_snapshots


def _assert_blocker(database, service, publications, import_id, sql, params, code):
    import sqlite3

    with sqlite3.connect(database) as connection:
        connection.execute(sql, params)
    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)
    assert code in {blocker.code for blocker in blocked.value.blockers}
    assert publications.get_publications(PROJECT_ID)


def test_pre_screening_decision_blocks_rejection(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    _assert_blocker(
        database,
        service,
        publications,
        import_id,
        "INSERT INTO pre_screening_decisions (decision_id, project_id, record_id, status, reviewer_id, decided_at) VALUES ('d1', ?, ?, 'removed', 'alice', ?)",
        (PROJECT_ID, str(publication.record_id), datetime.now(timezone.utc).isoformat()),
        "pre_screening_decision",
    )


def test_full_text_metadata_blocks_rejection(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    _assert_blocker(
        database,
        service,
        publications,
        import_id,
        "INSERT INTO full_text_availability (project_id, publication_id, status) VALUES (?, ?, 'available')",
        (PROJECT_ID, str(publication.record_id)),
        "full_text_metadata",
    )


def test_quality_assessment_blocks_rejection(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    _assert_blocker(
        database,
        service,
        publications,
        import_id,
        "INSERT INTO quality_assessments (assessment_id, project_id, publication_id, reviewer_id, template_id, assessed_at) VALUES ('qa1', ?, ?, 'alice', 'template-1', ?)",
        (PROJECT_ID, str(publication.record_id), datetime.now(timezone.utc).isoformat()),
        "quality_assessment",
    )


def test_extraction_record_blocks_rejection(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    _assert_blocker(
        database,
        service,
        publications,
        import_id,
        "INSERT INTO extraction_records (record_id, project_id, publication_id, template_id, template_version, current_status) VALUES ('ex1', ?, ?, 'template-1', 'v1', 'complete')",
        (PROJECT_ID, str(publication.record_id)),
        "extraction",
    )


def test_synthesis_relation_blocks_rejection(tmp_path: Path) -> None:
    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    _assert_blocker(
        database,
        service,
        publications,
        import_id,
        "INSERT INTO synthesis_analytical_relations (relation_id, project_id, publication_id, latest_revision_id, group_item_id, source_practice, source_effect, direction, evidence_character, approval_state) VALUES ('s1', ?, ?, 'rev1', 'item1', 'Kaizen', 'Energy', 'positive', 'empirical', 'approved')",
        (PROJECT_ID, str(publication.record_id)),
        "synthesis",
    )


def test_corpus_finalization_blocks_rejection(tmp_path: Path) -> None:
    import sqlite3

    publication = _publication(1)
    database, service, publications, _, _, _, import_id, _, _ = _environment(
        tmp_path, [publication]
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO corpus_finalizations (finalization_id, project_id, source_records_count, duplicates_removed_count, prescreening_removed_count, retained_count) VALUES ('f1', ?, 1, 0, 0, 1)",
            (PROJECT_ID,),
        )
        connection.execute(
            "INSERT INTO corpus_finalization_members (finalization_id, record_id, disposition, admitted_to_screening) VALUES ('f1', ?, 'retained', 1)",
            (str(publication.record_id),),
        )

    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)
    assert "corpus_finalized" in {blocker.code for blocker in blocked.value.blockers}
    assert publications.get_publications(PROJECT_ID)


def test_transaction_rolls_back_publication_deletion_when_derived_cleanup_fails(tmp_path: Path) -> None:
    class FailingNormalizationRepository(SqliteNormalizationExecutionRepository):
        def delete_for_project(self, project_id: str, **kwargs) -> None:
            raise RuntimeError("injected normalization failure")

    publication = _publication(1)
    database = tmp_path / "rollback-review.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    publications = SqliteProjectPublicationRepository(database)
    reviews = SqliteImportReviewRepository(database)
    import_id = uuid4()
    history.create(
        ImportHistoryRecord(
            import_id=import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="rollback.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=1,
            total_available=None,
            status="warning",
            warnings=("warning",),
            created_at=datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc),
        )
    )
    publications.import_source_publications(
        PROJECT_ID, [publication], import_id=import_id, preserve_source_occurrences=True
    )
    service = ImportReviewService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
        normalization_repository=FailingNormalizationRepository(database),
        transaction_manager=SqliteTransactionManager(database),
    )

    with pytest.raises(RuntimeError, match="injected"):
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)

    reopened = SqliteProjectPublicationRepository(database)
    assert reopened.get_publications(PROJECT_ID) == [publication]
    assert SqliteImportReviewRepository(database).get(PROJECT_ID, import_id) is None


def test_legacy_import_without_ownership_evidence_blocks_rejection(tmp_path: Path) -> None:
    database = tmp_path / "legacy-review.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    publications = SqliteProjectPublicationRepository(database)
    reviews = SqliteImportReviewRepository(database)
    import_id = uuid4()
    history.create(
        ImportHistoryRecord(
            import_id=import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="legacy.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=10,
            total_available=None,
            status="warning",
            warnings=("legacy warning",),
            created_at=datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc),
        )
    )
    service = ImportReviewService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
        transaction_manager=SqliteTransactionManager(database),
    )

    with pytest.raises(ImportRejectionBlockedError) as blocked:
        service.reject(PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True)
    assert "unverifiable_ownership" in {blocker.code for blocker in blocked.value.blockers}
    assert service.accept(PROJECT_ID, import_id, reviewer_id="alice").decision == "accepted"
