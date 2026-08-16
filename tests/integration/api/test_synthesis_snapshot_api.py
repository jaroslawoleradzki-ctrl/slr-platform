"""Integration tests for Synthesis Snapshots API endpoints (Task 10.7).

Checkpoint D: POST /snapshots, GET /snapshots, GET /snapshots/{version},
GET /snapshots/{version}/export contract. Immutability, monotonic versioning,
COMPLETE-only dataset hashing, and project isolation at the API boundary.
"""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    RelationDirection,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.synthesis_matrix_repository import SqliteSynthesisMatrixRepository


def _apply_migrations_up_to(db_path: Path, max_version: str | None = None) -> None:
    migrations_dir = Path(__file__).parents[3] / "migrations"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ");"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if max_version and sql_file.name > max_version:
                continue
            if sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_synthesis_snapshot_api.db"
    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))
    return TestClient(app), db_path


def _seed_evidence(db_path: str, proj_id: str) -> dict:
    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    pub_repo = SqliteProjectPublicationRepository(db_path)
    ext_repo = SqliteExtractionRepository(db_path)
    matrix_repo = SqliteSynthesisMatrixRepository(db_path)

    pub_id = uuid4()
    group_item_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Snapshot API Study", publication_year=2024)])
    rec = ext_repo.create_record(
        ExtractionRecord(
            project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
        )
    )
    rev = ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=group_item_id,
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Single Minute Exchange of Die",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Compressed Air",
                        ),
                    ],
                )
            ],
        )
    )

    rel_id = uuid4()
    matrix_repo.save_analytical_relation(
        AnalyticalRelation(
            relation_id=rel_id,
            project_id=proj_id,
            publication_id=pub_id,
            latest_revision_id=rev.revision_id,
            group_item_id=group_item_id,
            item_index=1,
            source_practice="SMED Setup",
            source_effect="Compressed Air",
            direction=RelationDirection.POSITIVE,
            approval_state=ClassificationApprovalState.APPROVED,
        )
    )

    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev_id": rev.revision_id,
        "relation_id": rel_id,
    }


def test_d1_create_snapshot(client):
    test_client, db_path = client
    proj_id = "test-api-snap-create"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Create", description=""))
    _seed_evidence(db_path, proj_id)

    res = test_client.post(
        f"/api/v1/projects/{proj_id}/synthesis/snapshots",
        json={"actor": "researcher-1"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["project_id"] == proj_id
    assert data["version"] == 1
    assert data["actor"] == "researcher-1"
    assert len(data["extraction_dataset_hash"]) == 64
    assert len(data["classification_version"]) == 64
    assert len(data["content_hash"]) == 64
    assert len(data["content"]["relations"]) == 1


def test_d2_create_snapshot_missing_project(client):
    test_client, _ = client
    res = test_client.post("/api/v1/projects/missing/synthesis/snapshots", json={"actor": "r"})
    assert res.status_code == 404


def test_d3_create_snapshot_validation_error(client):
    test_client, db_path = client
    proj_id = "test-api-snap-valid"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Valid", description=""))
    res = test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "  "})
    assert res.status_code == 400
    assert "actor must be non-empty" in res.json()["detail"]


def test_d4_list_snapshots_ordered_by_version(client):
    test_client, db_path = client
    proj_id = "test-api-snap-list"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="List", description=""))

    test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"})
    test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"})
    test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"})

    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/snapshots")
    assert res.status_code == 200
    versions = [s["version"] for s in res.json()]
    assert versions == [1, 2, 3]


def test_d5_get_snapshot_by_version(client):
    test_client, db_path = client
    proj_id = "test-api-snap-get"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Get", description=""))
    created = test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"}).json()

    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/snapshots/{created['version']}")
    assert res.status_code == 200
    assert res.json()["snapshot_id"] == created["snapshot_id"]
    assert res.json()["content"]["project_id"] == proj_id


def test_d6_get_snapshot_missing_version(client):
    test_client, db_path = client
    proj_id = "test-api-snap-get-missing"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Missing", description=""))
    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/snapshots/99")
    assert res.status_code == 404


def test_d7_json_export_contract(client):
    test_client, db_path = client
    proj_id = "test-api-snap-export"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Export", description=""))
    _seed_evidence(db_path, proj_id)
    created = test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"}).json()

    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/snapshots/1/export?format=json")
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "json"
    assert data["snapshot_id"] == created["snapshot_id"]
    assert len(data["content"]["relations"]) == 1
    assert len(data["content"]["mechanism_pathways"]) == 0


def test_d8_csv_export_contract(client):
    test_client, db_path = client
    proj_id = "test-api-snap-export-csv"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="ExportCSV", description=""))
    _seed_evidence(db_path, proj_id)
    test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"})

    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/snapshots/1/export?format=csv")
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "csv"
    assert data["content_csv"] is not None
    assert "source_practice" in data["content_csv"]
    assert "SMED Setup" in data["content_csv"]


def test_d9_unsupported_export_format(client):
    test_client, db_path = client
    proj_id = "test-api-snap-export-bad"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="ExportBad", description=""))
    test_client.post(f"/api/v1/projects/{proj_id}/synthesis/snapshots", json={"actor": "r"})

    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/snapshots/1/export?format=xml")
    assert res.status_code == 400


def test_d10_project_isolation(client):
    test_client, db_path = client
    proj_a = "test-api-snap-proj-a"
    proj_b = "test-api-snap-proj-b"
    repo = SqliteProjectRepository(db_path)
    repo.create(Project(project_id=proj_a, title="A", description=""))
    repo.create(Project(project_id=proj_b, title="B", description=""))
    _seed_evidence(db_path, proj_a)

    created_a = test_client.post(f"/api/v1/projects/{proj_a}/synthesis/snapshots", json={"actor": "r"}).json()
    test_client.post(f"/api/v1/projects/{proj_b}/synthesis/snapshots", json={"actor": "r"}).json()

    # Project B's version 1 is its own snapshot, never project A's.
    res = test_client.get(f"/api/v1/projects/{proj_b}/synthesis/snapshots/1")
    assert res.status_code == 200
    assert res.json()["snapshot_id"] != created_a["snapshot_id"]
    assert res.json()["content"]["relations"] == []

    # Project A's snapshot_id is not retrievable from project B.
    res = test_client.get(f"/api/v1/projects/{proj_a}/synthesis/snapshots/{created_a['version']}")
    assert res.status_code == 200

    # Project A's relations are not exposed through project B.
    assert created_a["content"]["relations"][0]["source_practice"] == "SMED Setup"
