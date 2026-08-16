"""Task 10.8 regression tests for synthesis context router/service fixes.

Covers the three integration defects surfaced by the E2E suite:
1. remap_context_assignment now persists researcher-provided context_impact.
2. PUT /context/unassign returns the pre-deletion assignment (was always 404).
3. remap of a missing link returns 404 (not 500/400); remap with a missing
   category returns 400.
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
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository


def _apply_migrations_up_to(db_path: Path) -> None:
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
            if sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_synthesis_context_fixes.db"
    _apply_migrations_up_to(db_path)
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))
    return TestClient(app), db_path


def _create_project(db_path: str, proj_id: str) -> None:
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Regression", description=""))


def _seed_evidence(db_path: str, proj_id: str) -> dict:
    template_repo = SqliteExtractionTemplateRepository(db_path)
    try:
        template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
        template_repo.register_version(
            ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
        )
    except Exception:
        pass
    pub_repo = SqliteProjectPublicationRepository(db_path)
    ext_repo = SqliteExtractionRepository(db_path)

    pub_id = uuid4()
    group_item_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Regression Study", publication_year=2024)])
    rec = ext_repo.create_record(
        ExtractionRecord(project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0")
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
                            text_value="SMED",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Compressed Air",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="moderating_conditions",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Context text.",
                            source_locator="Table 1",
                        ),
                    ],
                )
            ],
        )
    )
    return {"pub_id": pub_id, "group_item_id": group_item_id, "rev_id": rev.revision_id}


def _synth_url(proj_id: str, *parts: str) -> str:
    return f"/api/v1/projects/{proj_id}/synthesis/{'/'.join(parts)}"


def test_regression_unassign_returns_pre_deletion_assignment(client):
    test_client, db_path = client
    proj_id = "ctx-fix-unassign"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)
    test_client.get(_synth_url(proj_id, "matrix"))
    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "c1", "name": "C1"}
    ).status_code == 201

    created = test_client.post(
        _synth_url(proj_id, "context", "assign-by-group-item"),
        data={
            "categoryId": "c1",
            "contextImpact": "ENABLE",
            "groupItemId": str(seeded["group_item_id"]),
            "publicationId": str(seeded["pub_id"]),
            "latestRevisionId": str(seeded["rev_id"]),
            "sourceContextText": "Context text.",
        },
    )
    assert created.status_code == 201
    link_id = created.json()["assignment_id"]

    deleted = test_client.put(
        _synth_url(proj_id, "context", "unassign", link_id),
        params={"projectId": proj_id},
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["assignment_id"] == link_id
    assert body["project_id"] == proj_id
    assert body["analytical_context_category_id"] == "c1"
    assert body["context_impact"] == "ENABLE"

    assert test_client.put(
        _synth_url(proj_id, "context", "unassign", link_id),
        params={"projectId": proj_id},
    ).status_code == 404


def test_regression_remap_persists_context_impact(client):
    test_client, db_path = client
    proj_id = "ctx-fix-remap-impact"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)
    test_client.get(_synth_url(proj_id, "matrix"))
    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "c1", "name": "C1"}
    ).status_code == 201
    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "c2", "name": "C2"}
    ).status_code == 201

    created = test_client.post(
        _synth_url(proj_id, "context", "assign-by-group-item"),
        data={
            "categoryId": "c1",
            "contextImpact": "ENABLE",
            "groupItemId": str(seeded["group_item_id"]),
            "publicationId": str(seeded["pub_id"]),
            "latestRevisionId": str(seeded["rev_id"]),
            "sourceContextText": "Context text.",
        },
    ).json()
    link_id = created["assignment_id"]

    remapped = test_client.put(
        _synth_url(proj_id, "context", "remap"),
        params={"linkId": link_id, "projectId": proj_id},
        json={"category_id": "c2", "context_impact": "WEAKEN"},
    )
    assert remapped.status_code == 200
    body = remapped.json()
    assert body["analytical_context_category_id"] == "c2"
    assert body["context_impact"] == "WEAKEN"

    workspace = test_client.post(_synth_url(proj_id, "context", "synthesize")).json()
    persisted = next(a for a in workspace["assignments"] if a["assignment_id"] == link_id)
    assert persisted["analytical_context_category_id"] == "c2"
    assert persisted["context_impact"] == "WEAKEN"


def test_regression_remap_missing_link_404_and_bad_category_400(client):
    test_client, db_path = client
    proj_id = "ctx-fix-remap-errors"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)
    test_client.get(_synth_url(proj_id, "matrix"))
    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "c1", "name": "C1"}
    ).status_code == 201

    # Missing link must be 404 even when the category is also invalid.
    missing = test_client.put(
        _synth_url(proj_id, "context", "remap"),
        params={"linkId": str(uuid4()), "projectId": proj_id},
        json={"category_id": "no-such", "context_impact": "ENABLE"},
    )
    assert missing.status_code == 404

    created = test_client.post(
        _synth_url(proj_id, "context", "assign-by-group-item"),
        data={
            "categoryId": "c1",
            "contextImpact": "ENABLE",
            "groupItemId": str(seeded["group_item_id"]),
            "publicationId": str(seeded["pub_id"]),
            "latestRevisionId": str(seeded["rev_id"]),
            "sourceContextText": "Context text.",
        },
    ).json()
    link_id = created["assignment_id"]

    # Existing link but missing target category must be 400.
    bad_category = test_client.put(
        _synth_url(proj_id, "context", "remap"),
        params={"linkId": link_id, "projectId": proj_id},
        json={"category_id": "no-such", "context_impact": "ENABLE"},
    )
    assert bad_category.status_code == 400
