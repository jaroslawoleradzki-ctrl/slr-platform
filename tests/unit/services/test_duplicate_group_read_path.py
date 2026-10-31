from uuid import UUID

import pytest

from app.domain.author import Author
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_source_record_repository import (
    ImportSourceRecord,
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.normalization_service import normalize_project
from app.services.project_duplicate_service import ProjectDuplicateService


def test_duplicate_group_get_does_not_change_projection_or_snapshots(tmp_path, caplog):
    caplog.set_level("INFO")
    database = tmp_path / "duplicate-read.db"
    publications = SqliteProjectPublicationRepository(database)
    source_records = SqliteImportSourceRecordRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    ids = (
        UUID("11111111-1111-1111-1111-111111111111"),
        UUID("22222222-2222-2222-2222-222222222222"),
    )
    records = [
        Publication(
            record_id=record_id,
            title="A sufficiently long synthetic publication title for duplicate testing",
            authors=[Author(display_name="Synthetic Author")],
            publication_year=2020,
            language="eng",
            identifiers=[],
            provenance=[ProvenanceEntry(source="ris", source_record_id=f"src-{index}")],
        )
        for index, record_id in enumerate(ids)
    ]
    publications.add_publications("lean_energy", records)
    for index, record_id in enumerate(ids):
        source_records.create_source_record(
            ImportSourceRecord(
                source_record_id=f"source-{index}",
                project_id="lean_energy",
                import_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                source_filename="synthetic",
                source_file_hash=None,
                source_record_index=index + 1,
                    title="A sufficiently long synthetic publication title for duplicate testing",
                publication_year=None,
                original_doi=None,
                normalized_doi=None,
                authors=("Synthetic Author",),
                document_type=None,
                provenance={"source": "test"},
                canonical_publication_id=str(record_id),
            )
        )

    service = ProjectDuplicateService(
        repository=publications,
        decision_repository=decisions,
        merge_repository=merges,
        transaction_manager=SqliteTransactionManager(database),
        source_record_repository=source_records,
    )
    before_ids = [record.duplicate_candidate_group_id for record in source_records.list_source_records("lean_energy")]
    before_snapshots = source_records.list_candidate_group_snapshots("lean_energy")

    result = service.get_candidate_duplicate_groups("lean_energy")

    assert result.total_groups_count == 1
    diagnostic = " ".join(record.getMessage() for record in caplog.records)
    assert "duration_ms=" in diagnostic
    assert "response_bytes=" in diagnostic
    assert "synthetic publication title" not in diagnostic
    assert [record.duplicate_candidate_group_id for record in source_records.list_source_records("lean_energy")] == before_ids
    assert source_records.list_candidate_group_snapshots("lean_energy") == before_snapshots

    group_id = result.groups[0].group_id
    executions = SqliteNormalizationExecutionRepository(database)
    with pytest.raises(RuntimeError, match="injected shared-transaction failure"):
        with SqliteTransactionManager(database).transaction() as connection:
            execution = normalize_project(publications, "lean_energy", connection=connection)
            service.materialize_candidate_group_projection("lean_energy", connection=connection)
            executions.save(execution, connection=connection)
            raise RuntimeError("injected shared-transaction failure")
    assert [publication.language for publication in publications.get_publications("lean_energy")] == ["eng", "eng"]
    assert [record.duplicate_candidate_group_id for record in source_records.list_source_records("lean_energy")] == before_ids
    assert source_records.list_candidate_group_snapshots("lean_energy") == before_snapshots
    assert executions.get_for_project("lean_energy") is None

    with SqliteTransactionManager(database).transaction() as connection:
        execution = normalize_project(publications, "lean_energy", connection=connection)
        service.materialize_candidate_group_projection("lean_energy", connection=connection)
        executions.save(execution, connection=connection)
    materialized_ids = [record.duplicate_candidate_group_id for record in source_records.list_source_records("lean_energy")]
    materialized_snapshots = source_records.list_candidate_group_snapshots("lean_energy")
    assert set(materialized_ids) == {group_id}
    assert len(materialized_snapshots) == 1

    with pytest.raises(RuntimeError, match="injected projection failure"):
        with SqliteTransactionManager(database).transaction() as connection:
            source_records.clear_candidate_groups("lean_energy", connection=connection)
            source_records.update_candidate_group(
                "lean_energy", [str(ids[0])], "non-committed-group", connection=connection
            )
            source_records.record_candidate_group_snapshot(
                "lean_energy",
                "non-committed-group",
                [str(ids[0])],
                match_type=None,
                match_reason=None,
                status="PENDING",
                connection=connection,
            )
            raise RuntimeError("injected projection failure")

    assert [record.duplicate_candidate_group_id for record in source_records.list_source_records("lean_energy")] == materialized_ids
    assert source_records.list_candidate_group_snapshots("lean_energy") == materialized_snapshots


@pytest.mark.parametrize("failure_stage", ["projection", "snapshot", "summary"])
def test_normalization_projection_snapshot_and_summary_rollback_at_each_write(
    tmp_path, monkeypatch, failure_stage
):
    database = tmp_path / f"normalization-{failure_stage}-rollback.db"
    publications = SqliteProjectPublicationRepository(database)
    source_records = SqliteImportSourceRecordRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    executions = SqliteNormalizationExecutionRepository(database)
    transaction_manager = SqliteTransactionManager(database)
    project_id = "lean_energy"
    import_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    records = [
        Publication(
            record_id=record_id,
            title="A sufficiently long shared title for transactional rollback testing",
            authors=[Author(display_name="Synthetic Author")],
            publication_year=2020,
            language="ENG",
            identifiers=[],
            provenance=[ProvenanceEntry(source="ris", source_record_id=f"rollback-{index}")],
        )
        for index, record_id in enumerate(
            (
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            )
        )
    ]
    publications.add_publications(project_id, records)
    for index, publication in enumerate(records):
        source_records.create_source_record(
            ImportSourceRecord(
                source_record_id=f"rollback-source-{index}",
                project_id=project_id,
                import_id=import_id,
                source_filename="rollback.ris",
                source_file_hash=None,
                source_record_index=index + 1,
                title=publication.title,
                publication_year=publication.publication_year,
                original_doi=None,
                normalized_doi=None,
                authors=("Synthetic Author",),
                document_type=None,
                provenance={"source": "test"},
                canonical_publication_id=str(publication.record_id),
            )
        )
    service = ProjectDuplicateService(
        repository=publications,
        decision_repository=decisions,
        merge_repository=merges,
        transaction_manager=transaction_manager,
        source_record_repository=source_records,
    )

    if failure_stage == "projection":
        original = source_records.update_candidate_group

        def fail_projection(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected projection write failure")

        monkeypatch.setattr(source_records, "update_candidate_group", fail_projection)
    elif failure_stage == "snapshot":
        original = source_records.record_candidate_group_snapshot

        def fail_snapshot(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected snapshot write failure")

        monkeypatch.setattr(source_records, "record_candidate_group_snapshot", fail_snapshot)
    else:
        original = executions.save

        def fail_summary(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected summary write failure")

        monkeypatch.setattr(executions, "save", fail_summary)

    before_ids = [record.duplicate_candidate_group_id for record in source_records.list_source_records(project_id)]
    before_snapshots = source_records.list_candidate_group_snapshots(project_id)
    with pytest.raises(RuntimeError, match=f"injected {failure_stage}.*failure"):
        with transaction_manager.transaction() as connection:
            execution = normalize_project(publications, project_id, connection=connection)
            service.materialize_candidate_group_projection(project_id, connection=connection)
            executions.save(execution, connection=connection)

    assert [publication.language for publication in publications.get_publications(project_id)] == ["ENG", "ENG"]
    assert [record.duplicate_candidate_group_id for record in source_records.list_source_records(project_id)] == before_ids
    assert source_records.list_candidate_group_snapshots(project_id) == before_snapshots
    assert executions.get_for_project(project_id) is None


def test_merge_projection_failure_rolls_back_merge_decision_and_publications(tmp_path, monkeypatch):
    database = tmp_path / "merge-projection-rollback.db"
    publications = SqliteProjectPublicationRepository(database)
    source_records = SqliteImportSourceRecordRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    transaction_manager = SqliteTransactionManager(database)
    project_id = "lean_energy"
    records = [
        Publication(
            record_id=record_id,
            title="Synthetic merge rollback candidate title",
            authors=[Author(display_name="Synthetic Author")],
            publication_year=2020,
            identifiers=[],
            provenance=[ProvenanceEntry(source="ris", source_record_id=f"merge-{index}")],
        )
        for index, record_id in enumerate(
            (
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            )
        )
    ]
    publications.add_publications(project_id, records)
    service = ProjectDuplicateService(
        repository=publications,
        decision_repository=decisions,
        merge_repository=merges,
        transaction_manager=transaction_manager,
        source_record_repository=source_records,
    )
    group_id = str(service.get_candidate_duplicate_groups(project_id).groups[0].group_id)
    original = service.materialize_candidate_group_projection

    def fail_after_projection(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected merge projection failure")

    monkeypatch.setattr(service, "materialize_candidate_group_projection", fail_after_projection)
    with pytest.raises(RuntimeError, match="merge projection failure"):
        service.merge_group(project_id, group_id)

    assert decisions.get_decision(project_id, group_id) is None
    assert merges.get_merge(project_id, group_id) is None
    assert publications.get_publications(project_id) == records
    assert source_records.list_candidate_group_snapshots(project_id) == []
