from pathlib import Path
from uuid import UUID

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.synthesis import AnalyticalRelation
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.synthesis_matrix_repository import SqliteSynthesisMatrixRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.integrity_audit_service import ProjectIntegrityAuditService
from app.services.normalization_service import normalize_project
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.screening_input_service import ScreeningInputService
from app.services.synthesis_matrix_service import SynthesisMatrixService


def _publication(number: int, *, abstract: str, source: str) -> Publication:
    return Publication(record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"), title="Duplicate study" if number == 1 else "Duplicate study with richer metadata", abstract=abstract, identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/canonical")], urls=[f"https://example.test/{number}"], provenance=[ProvenanceEntry(source=source, source_record_id=str(number))])


def _service(database: Path, repository: SqliteProjectPublicationRepository | None = None):
    publications = repository or SqliteProjectPublicationRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    return ProjectDuplicateService(publications, decisions, merge_repository=merges, transaction_manager=SqliteTransactionManager(database)), publications, decisions, merges


def test_explicit_merge_persists_canonical_state_and_survives_reload(tmp_path: Path) -> None:
    database = tmp_path / "merge.db"
    service, publications, decisions, merges = _service(database)
    first, second = _publication(1, abstract="short", source="openalex"), _publication(2, abstract="a richer abstract", source="crossref")
    publications.add_publications("lean_energy", [second, first])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE")
    assert len(publications.get_active_publications("lean_energy")) == 2
    response = service.merge_group("lean_energy", group_id)
    assert response.canonical_record_id == str(first.record_id)
    assert len(publications.get_all_publications("lean_energy")) == 2
    active = publications.get_active_publications("lean_energy")
    assert len(active) == 1 and active[0].record_id == first.record_id
    assert active[0].abstract == "a richer abstract"
    assert set(active[0].urls) == {"https://example.test/1", "https://example.test/2"}
    assert len(active[0].provenance) == 2
    assert publications.get_superseded_by_map("lean_energy")[second.record_id] == first.record_id
    merge = merges.get_merge("lean_energy", group_id)
    assert merge is not None and set(merge.merged_publication_ids) == {first.record_id, second.record_id}
    assert len(merge.pre_merge_snapshots) == 2
    reloaded, reloaded_pubs, _, reloaded_merges = _service(database)
    historical_group = reloaded.get_candidate_duplicate_groups("lean_energy").groups[0]
    assert historical_group.group_id == group_id
    assert historical_group.status.value == "MERGED"
    assert historical_group.canonical_record_id == str(first.record_id)
    assert set(historical_group.merged_publication_ids or []) == {str(first.record_id), str(second.record_id)}
    assert historical_group.merged_at
    assert reloaded_merges.get_merge("lean_energy", group_id) == merge
    screening = ScreeningInputService(reloaded_pubs, decisions, merge_repository=reloaded_merges)
    assert screening.get_input_set("lean_energy").publications == tuple(active)


class _FailingPublicationRepository(SqliteProjectPublicationRepository):
    def mark_superseded(self, *args, **kwargs):
        raise RuntimeError("injected write failure")


def test_merge_transaction_rolls_back_every_mutation(tmp_path: Path) -> None:
    database = tmp_path / "rollback.db"
    repository = _FailingPublicationRepository(database)
    service, _, _, merges = _service(database, repository)
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    repository.add_publications("lean_energy", [first, second])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE")
    with pytest.raises(RuntimeError, match="injected"):
        service.merge_group("lean_energy", group_id)
    # Assert through fresh repository instances, not the connection that raised.
    reopened = SqliteProjectPublicationRepository(database)
    reopened_merges = SqliteDuplicateMergeRepository(database)
    assert reopened_merges.get_merge("lean_energy", group_id) is None
    assert reopened.get_active_publications("lean_energy") == [first, second]
    assert reopened.get_superseded_by_map("lean_energy") == {first.record_id: None, second.record_id: None}


def test_merge_rolls_back_when_saving_merge_record_fails(tmp_path: Path) -> None:
    class FailingMergeRepository(SqliteDuplicateMergeRepository):
        def save_merge(self, *args, **kwargs):
            raise RuntimeError("injected merge-record failure")

    database = tmp_path / "rollback-save.db"
    publications = SqliteProjectPublicationRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = FailingMergeRepository(database)
    service = ProjectDuplicateService(
        publications, decisions, merge_repository=merges, transaction_manager=SqliteTransactionManager(database)
    )
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    publications.add_publications("lean_energy", [first, second])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE")

    with pytest.raises(RuntimeError, match="merge-record"):
        service.merge_group("lean_energy", group_id)

    reopened = SqliteProjectPublicationRepository(database)
    assert reopened.get_superseded_by_map("lean_energy") == {first.record_id: None, second.record_id: None}
    assert SqliteDuplicateMergeRepository(database).get_merge("lean_energy", group_id) is None


def test_merge_rolls_back_when_canonical_update_fails(tmp_path: Path) -> None:
    class FailingUpdateRepository(SqliteProjectPublicationRepository):
        def update_publication(self, *args, **kwargs):
            raise RuntimeError("injected canonical-update failure")

    database = tmp_path / "rollback-update.db"
    publications = FailingUpdateRepository(database)
    service, _, _, _ = _service(database, publications)
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    publications.add_publications("lean_energy", [first, second])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE")

    with pytest.raises(RuntimeError, match="canonical-update"):
        service.merge_group("lean_energy", group_id)

    reopened = SqliteProjectPublicationRepository(database)
    assert reopened.get_superseded_by_map("lean_energy") == {first.record_id: None, second.record_id: None}
    assert SqliteDuplicateMergeRepository(database).get_merge("lean_energy", group_id) is None


def test_integrity_audit_detects_broken_merge_supersession(tmp_path: Path) -> None:
    database = tmp_path / "audit.db"
    service, repository, decisions, merges = _service(database)
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    repository.add_publications("lean_energy", [first, second])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE")
    service.merge_group("lean_energy", group_id)
    audit = ProjectIntegrityAuditService(publication_repository=repository, decision_repository=decisions, merge_repository=merges)
    assert not {check.code for check in audit.audit_project("lean_energy").checks if check.code.startswith("DEDUP_MERGE")}
    import sqlite3
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE project_publications SET superseded_by = ? WHERE project_id = ? AND record_id = ?", (str(second.record_id), "lean_energy", str(second.record_id)))
    assert "DEDUP_SUPERSESSION_SELF" in {check.code for check in audit.audit_project("lean_energy").checks}


def test_normalization_and_metadata_update_preserve_supersession_and_active_input(tmp_path: Path) -> None:
    database = tmp_path / "normalization-after-merge.db"
    service, repository, _, _ = _service(database)
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    repository.add_publications("lean_energy", [first, second])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE")
    service.merge_group("lean_energy", group_id)

    normalize_project(repository, "lean_energy")
    enriched_second = second.model_copy(update={"abstract": "enriched source metadata"})
    repository.update_publication("lean_energy", enriched_second)

    reopened = SqliteProjectPublicationRepository(database)
    assert reopened.get_superseded_by_map("lean_energy")[second.record_id] == first.record_id
    assert reopened.count_active_by_project("lean_energy") == 1
    screening = ScreeningInputService(reopened, SqliteDuplicateReviewDecisionRepository(database), merge_repository=SqliteDuplicateMergeRepository(database))
    assert [publication.record_id for publication in screening.get_input_set("lean_energy").publications] == [first.record_id]


def test_merged_group_history_survives_later_source_metadata_divergence(tmp_path: Path) -> None:
    """Historical group lookup must not depend on the live duplicate builder."""
    database = tmp_path / "historical-group.db"
    service, repository, _, _ = _service(database)
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    repository.add_publications("lean_energy", [first, second])
    group_id = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", group_id, "APPROVE", rationale="same study")
    service.merge_group("lean_energy", group_id)

    # A later permitted enrichment can change the source's strong identifier.
    # It must not erase the durable audit group from a fresh service instance.
    repository.update_publication(
        "lean_energy",
        second.model_copy(
            update={"identifiers": [Identifier(type=IdentifierType.DOI, value="10.1000/new-source-id")]}
        ),
    )
    reloaded, _, _, _ = _service(database)
    groups = reloaded.get_candidate_duplicate_groups("lean_energy").groups
    historical = next(group for group in groups if group.group_id == group_id)
    assert historical.status.value == "MERGED"
    assert historical.canonical_record_id == str(first.record_id)
    assert set(historical.merged_publication_ids or []) == {str(first.record_id), str(second.record_id)}
    assert historical.rationale == "same study"


def test_merge_rejects_a_superseded_noncanonical_member_without_writes(tmp_path: Path) -> None:
    database = tmp_path / "reject-superseded-member.db"
    service, repository, decisions, merges = _service(database)
    first = _publication(1, abstract="first", source="a")
    superseded = _publication(3, abstract="second", source="b")
    repository.add_publications("lean_energy", [first, superseded])
    original_group = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", original_group, "APPROVE")
    service.merge_group("lean_energy", original_group)

    updated_superseded = superseded.model_copy(
        update={"identifiers": [Identifier(type=IdentifierType.DOI, value="10.1000/new-source-id")]}
    )
    active_member = _publication(2, abstract="third", source="c").model_copy(
        update={"identifiers": [Identifier(type=IdentifierType.DOI, value="10.1000/new-source-id")]}
    )
    repository.update_publication("lean_energy", updated_superseded)
    repository.add_publications("lean_energy", [active_member])
    rejected_group = next(
        group
        for group in service.get_candidate_duplicate_groups("lean_energy").groups
        if set(record.id for record in group.records) == {str(superseded.record_id), str(active_member.record_id)}
    )
    service.record_decision("lean_energy", rejected_group.group_id, "APPROVE")

    with pytest.raises(ValueError, match="must all be active"):
        service.merge_group("lean_energy", rejected_group.group_id)

    reopened = SqliteProjectPublicationRepository(database)
    assert SqliteDuplicateMergeRepository(database).get_merge("lean_energy", rejected_group.group_id) is None
    assert reopened.get_superseded_by_map("lean_energy") == {
        first.record_id: None,
        active_member.record_id: None,
        superseded.record_id: first.record_id,
    }
    assert next(p for p in reopened.get_all_publications("lean_energy") if p.record_id == superseded.record_id).identifiers == updated_superseded.identifiers
    assert decisions.get_decision("lean_energy", rejected_group.group_id) is not None
    assert merges.get_merge("lean_energy", original_group) is not None


def test_merge_rejects_a_superseded_canonical_candidate_without_writes(tmp_path: Path) -> None:
    database = tmp_path / "reject-superseded-canonical.db"
    service, repository, _, _ = _service(database)
    first = _publication(1, abstract="first", source="a")
    superseded_canonical = _publication(2, abstract="second", source="b")
    repository.add_publications("lean_energy", [first, superseded_canonical])
    original_group = service.get_candidate_duplicate_groups("lean_energy").groups[0].group_id
    service.record_decision("lean_energy", original_group, "APPROVE")
    service.merge_group("lean_energy", original_group)

    updated_superseded = superseded_canonical.model_copy(
        update={"identifiers": [Identifier(type=IdentifierType.DOI, value="10.1000/new-source-id")]}
    )
    active_member = _publication(3, abstract="third", source="c").model_copy(
        update={"identifiers": [Identifier(type=IdentifierType.DOI, value="10.1000/new-source-id")]}
    )
    repository.update_publication("lean_energy", updated_superseded)
    repository.add_publications("lean_energy", [active_member])
    rejected_group = next(
        group
        for group in service.get_candidate_duplicate_groups("lean_energy").groups
        if set(record.id for record in group.records) == {str(superseded_canonical.record_id), str(active_member.record_id)}
    )
    service.record_decision("lean_energy", rejected_group.group_id, "APPROVE")

    with pytest.raises(ValueError, match="must all be active"):
        service.merge_group("lean_energy", rejected_group.group_id)

    reopened = SqliteProjectPublicationRepository(database)
    assert SqliteDuplicateMergeRepository(database).get_merge("lean_energy", rejected_group.group_id) is None
    assert reopened.get_superseded_by_map("lean_energy") == {
        first.record_id: None,
        superseded_canonical.record_id: first.record_id,
        active_member.record_id: None,
    }
    assert next(
        p for p in reopened.get_all_publications("lean_energy") if p.record_id == superseded_canonical.record_id
    ).identifiers == updated_superseded.identifiers


def test_synthesis_excludes_stale_materialized_evidence_for_superseded_records(tmp_path: Path) -> None:
    database = tmp_path / "synthesis-active-only.db"
    service, publications, _, _ = _service(database)
    project_repository = SqliteProjectRepository(database)
    project_repository.create(Project(project_id="dedup-project", title="Dedup", description=""))
    first, second = _publication(1, abstract="first", source="a"), _publication(2, abstract="second", source="b")
    publications.add_publications("dedup-project", [first, second])
    group_id = service.get_candidate_duplicate_groups("dedup-project").groups[0].group_id
    service.record_decision("dedup-project", group_id, "APPROVE")
    service.merge_group("dedup-project", group_id)

    matrix_repository = SqliteSynthesisMatrixRepository(database)
    matrix_repository.save_analytical_relations(
        [
            AnalyticalRelation(
                project_id="dedup-project", publication_id=publication.record_id, latest_revision_id=UUID(int=publication_number + 10),
                group_item_id=UUID(int=publication_number + 20), item_index=1,
                source_practice="Kaizen", source_effect="Electricity reduction",
            )
            for publication_number, publication in ((1, first), (2, second))
        ]
    )
    matrix = SynthesisMatrixService(
        matrix_repo=matrix_repository,
        project_repo=project_repository,
        publication_repo=publications,
    ).get_matrix("dedup-project")
    assert matrix.total_relations == 1
    assert matrix.total_publications == 1

    reloaded_matrix = SynthesisMatrixService(
        matrix_repo=SqliteSynthesisMatrixRepository(database),
        project_repo=SqliteProjectRepository(database),
        publication_repo=SqliteProjectPublicationRepository(database),
    ).get_matrix("dedup-project")
    assert reloaded_matrix.total_relations == 1
    assert reloaded_matrix.total_publications == 1
