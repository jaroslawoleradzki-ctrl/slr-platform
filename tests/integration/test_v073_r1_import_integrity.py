from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.services.import_identity import fingerprint_raw_record


def _ris(title: str, year: int | None = None, authors: list[str] | None = None, doi: str | None = None) -> str:
    lines = ["TY  - JOUR", f"TI  - {title}"]
    if year is not None:
        lines.append(f"PY  - {year}")
    for author in authors or []:
        lines.append(f"AU  - {author}")
    if doi is not None:
        lines.append(f"DO  - {doi}")
    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "v073_r1.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db))
    pub = SqliteProjectPublicationRepository(db)
    history = SqliteImportHistoryRepository(db)
    SqliteNormalizationExecutionRepository(db)
    source = SqliteImportSourceRecordRepository(db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','Project 1')")
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p2','Project 2')")
    con.commit()
    con.close()
    client = TestClient(app)
    yield client, pub, history, source, db


def _upload(client: TestClient, filename: str, content: str, source_database: str = "google_scholar_pop"):
    return client.post(
        "/api/v1/projects/p1/imports",
        files={"file": (filename, content, "application/x-research-info-systems")},
        data={"source_database": source_database},
    )


def _assert_all_canonical_links_exist(source_repo, pub_repo, project_id: str = "p1") -> None:
    ids = {str(item.record_id) for item in pub_repo.get_publications(project_id)}
    for record in source_repo.list_source_records(project_id):
        if record.canonical_publication_id is not None:
            assert record.canonical_publication_id in ids, record


def test_real_google_scholar_path_preserves_title_variants_by_year(environment) -> None:
    client, pub, _, source, _ = environment
    first = _upload(client, "GS01.ris", _ris("Shared No DOI", year=2021))
    second = _upload(client, "GS2.ris", _ris("Shared No DOI", year=2022))
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["records_count"] == 1
    assert second.json()["records_count"] == 1
    assert len(pub.get_publications("p1")) == 2
    assert len(source.list_source_records("p1")) == 2
    assert {item.publication_year for item in pub.get_publications("p1")} == {2021, 2022}
    _assert_all_canonical_links_exist(source, pub)


def test_real_google_scholar_path_preserves_title_variants_by_author(environment) -> None:
    client, pub, _, source, _ = environment
    _upload(client, "GS01.ris", _ris("Shared Author Title", authors=["Smith, A."]))
    _upload(client, "GS2.ris", _ris("Shared Author Title", authors=["Jones, B."]))
    assert len(pub.get_publications("p1")) == 2
    assert len({tuple(a.display_name for a in p.authors) for p in pub.get_publications("p1")}) == 2
    _assert_all_canonical_links_exist(source, pub)


def test_two_identical_titles_in_one_file_are_both_preserved(environment) -> None:
    client, pub, _, source, _ = environment
    content = _ris("Same File Same Title", year=2020) + "\n" + _ris("Same File Same Title", year=2020)
    response = _upload(client, "GS.ris", content)
    assert response.status_code == 201, response.text
    assert response.json()["records_count"] == 2
    assert len(pub.get_publications("p1")) == 2
    records = source.list_source_records("p1")
    assert len(records) == 2
    assert len({record.source_record_id for record in records}) == 2
    _assert_all_canonical_links_exist(source, pub)


def test_no_doi_record_with_same_title_as_doi_publication_is_preserved(environment) -> None:
    client, pub, _, source, _ = environment
    _upload(client, "crossref.ris", _ris("Shared DOI Title", year=2020, doi="10.1000/shared"))
    response = _upload(client, "GS.ris", _ris("Shared DOI Title", year=2020))
    assert response.json()["records_count"] == 1
    assert len(pub.get_publications("p1")) == 2
    _assert_all_canonical_links_exist(source, pub)


def test_duplicate_doi_within_single_file_links_to_first_canonical(environment) -> None:
    client, pub, _, source, _ = environment
    content = _ris("First Duplicate", year=2020, doi="10.1000/same-file") + "\n" + _ris(
        "Second Duplicate", year=2020, doi="https://doi.org/10.1000/SAME-FILE"
    )
    response = _upload(client, "GS.ris", content)
    assert response.status_code == 201, response.text
    assert response.json()["records_count"] == 1
    publications = pub.get_publications("p1")
    assert len(publications) == 1
    records = source.list_source_records("p1")
    assert len(records) == 2
    assert {record.canonical_publication_id for record in records} == {
        str(publications[0].record_id)
    }
    assert all(record.recovery_status in {"imported", "linked"} for record in records)
    assert any(item.match_type == "exact_doi" for item in source.list_skip_audit("p1"))
    _assert_all_canonical_links_exist(source, pub)


def test_changed_file_is_idempotent_for_unchanged_records(environment) -> None:
    client, pub, _, source, _ = environment
    first_content = _ris("Unchanged Record", year=2020)
    second_content = first_content + "\n" + _ris("New Record", year=2021)
    first = _upload(client, "GS.ris", first_content)
    second = _upload(client, "GS.ris", second_content)
    assert first.json()["records_count"] == 1
    assert second.json()["records_count"] == 1
    assert len(pub.get_publications("p1")) == 2
    assert len(source.list_source_records("p1")) == 2
    assert sum(
        1 for item in source.list_skip_audit("p1") if item.match_type == "repeated_occurrence"
    ) == 1
    _assert_all_canonical_links_exist(source, pub)


def test_same_content_different_source_database_preserves_provenance(environment) -> None:
    client, pub, _, source, _ = environment
    content = _ris("Cross Source Record", year=2020)
    first = _upload(client, "export.ris", content, source_database="google_scholar_pop")
    second = _upload(client, "export.ris", content, source_database="scopus")
    assert first.json()["records_count"] == 1
    assert second.json()["records_count"] == 1
    publications = pub.get_publications("p1")
    assert len(publications) == 2
    assert {record.provenance.get("source") for record in source.list_source_records("p1")} == {
        "google_scholar_pop",
        "scopus",
    }
    assert len(publications) == 2
    _assert_all_canonical_links_exist(source, pub)


def test_repeated_identical_file_is_idempotent_and_audited(environment) -> None:
    client, pub, _, source, _ = environment
    content = _ris("Repeat Record", year=2020)
    _upload(client, "GS.ris", content)
    response = _upload(client, "GS.ris", content)
    assert response.json()["records_count"] == 0
    assert len(pub.get_publications("p1")) == 1
    assert len(source.list_source_records("p1")) == 1
    repeated = [
        item for item in source.list_skip_audit("p1") if item.match_type == "repeated_occurrence"
    ]
    assert len(repeated) == 1
    assert repeated[0].source_record_id is not None


def test_invalid_doi_never_links_distinct_records(environment) -> None:
    client, pub, _, source, _ = environment
    _upload(client, "GS01.ris", _ris("Invalid A", year=2020, doi="not-a-doi"))
    response = _upload(client, "GS2.ris", _ris("Invalid B", year=2021, doi="not-a-doi"))
    assert response.json()["records_count"] == 1
    assert len(pub.get_publications("p1")) == 2
    records = source.list_source_records("p1")
    assert all(record.doi_status == "invalid" for record in records)
    assert not any(item.match_type == "exact_doi" for item in source.list_skip_audit("p1"))
    _assert_all_canonical_links_exist(source, pub)


def test_doi_url_prefix_matches_canonical_doi(environment) -> None:
    client, pub, _, source, _ = environment
    _upload(client, "GS01.ris", _ris("DOI Prefix", year=2020, doi="10.1000/prefix"))
    response = _upload(
        client,
        "GS2.ris",
        _ris("DOI Prefix Again", year=2020, doi="https://doi.org/10.1000/PREFIX"),
    )
    assert response.json()["records_count"] == 0
    assert len(pub.get_publications("p1")) == 1
    assert any(item.match_type == "exact_doi" for item in source.list_skip_audit("p1"))
    _assert_all_canonical_links_exist(source, pub)


def test_provider_import_persists_source_provenance(environment) -> None:
    _, pub, history, source, db = environment
    from app.api.dto.search_strategy import SearchResultRecordResponse
    from app.repositories.normalization_execution_repository import (
        SqliteNormalizationExecutionRepository,
    )
    from app.repositories.transaction_manager import SqliteTransactionManager
    from app.services.project_import_service import ProjectImportService

    service = ProjectImportService(
        publication_repository=pub,
        import_history_repository=history,
        normalization_repository=SqliteNormalizationExecutionRepository(db),
        transaction_manager=SqliteTransactionManager(db),
        source_record_repository=source,
    )
    record = SearchResultRecordResponse(
        id="00000000-0000-0000-0000-000000000911",
        title="Provider Provenance Record",
        authors=["Ada Author"],
        year=2024,
        provider="openalex",
        source_id="https://openalex.org/W911",
        doi="10.1000/provider",
    )
    first = service.import_provider_results_group(
        "p1", "openalex", [record], "provider provenance", 1
    )
    assert first.imported_count == 1
    records = source.list_source_records("p1")
    assert len(records) == 1
    assert records[0].import_format == "provider:openalex"
    assert records[0].provenance.get("source") == "openalex"
    assert records[0].canonical_publication_id is not None

    second = service.import_provider_results_group(
        "p1", "openalex", [record], "provider provenance", 1
    )
    assert second.imported_count == 0
    assert len(source.list_source_records("p1")) == 1
    assert any(
        item.match_type == "repeated_occurrence"
        for item in source.list_skip_audit("p1")
    )
    assert len(pub.get_publications("p1")) == 1


def test_raw_fingerprint_is_stable_across_record_order() -> None:
    one = {"TI": ["A"], "PY": ["2020"]}
    two = {"TI": ["B"], "PY": ["2021"]}
    assert fingerprint_raw_record(one) == fingerprint_raw_record(one)
    assert fingerprint_raw_record(one) != fingerprint_raw_record(two)
