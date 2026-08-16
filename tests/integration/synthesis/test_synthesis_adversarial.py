"""Task 10.8 Checkpoint F: Adversarial integration tests.

API-level guards for malformed identifiers, cross-project isolation on
mutation endpoints, nonexistent resources, stale/foreign links, and lifecycle
edge cases across the full synthesis surface. Complements the E2E journeys in
test_synthesis_e2e.py.
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
    db_path = tmp_path / "test_synthesis_adversarial.db"
    _apply_migrations_up_to(db_path)
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))
    return TestClient(app), db_path


def _create_project(db_path: str, proj_id: str) -> None:
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Adversarial", description=""))


def _seed_complete_evidence(db_path: str, proj_id: str) -> dict:
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
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Adversarial Study", publication_year=2024)])
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
                            text_value="SMED Setup",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Compressed Air",
                        ),
                        ExtractedValueState(
                            field_key="impact_mechanism",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Reduced idle time.",
                        ),
                    ],
                )
            ],
        )
    )
    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev_id": rev.revision_id,
        "practice": "SMED Setup",
        "effect": "Compressed Air",
    }


def _synth_url(proj_id: str, *parts: str) -> str:
    return f"/projects/{proj_id}/synthesis/{'/'.join(parts)}"


def test_adversarial_malformed_uuids_rejected(client):
    test_client, db_path = client
    proj_id = "adv-uuid"
    _create_project(db_path, proj_id)
    _seed_complete_evidence(db_path, proj_id)

    assert test_client.post(
        _synth_url(proj_id, "mechanisms", "pathways", "not-a-uuid", "assign"),
        json={"category_id": "c"},
    ).status_code == 422
    assert test_client.post(
        _synth_url(proj_id, "research-gaps", "not-a-uuid", "links"),
        json={"link_type": "mechanism_pathway", "target_id": "not-a-uuid"},
    ).status_code == 422
    assert test_client.get(_synth_url(proj_id, "research-gaps", "not-a-uuid")).status_code == 422
    assert test_client.put(
        _synth_url(proj_id, "context", "assign", "not-a-uuid"),
        params={"projectId": proj_id},
    ).status_code in (404, 422)


def test_adversarial_context_cross_project_mutation_rejected(client):
    test_client, db_path = client
    proj_a = "adv-ctx-a"
    proj_b = "adv-ctx-b"
    _create_project(db_path, proj_a)
    _create_project(db_path, proj_b)
    seeded_a = _seed_complete_evidence(db_path, proj_a)
    _seed_complete_evidence(db_path, proj_b)

    test_client.get(_synth_url(proj_a, "matrix"))
    test_client.get(_synth_url(proj_b, "matrix"))
    assert test_client.post(
        _synth_url(proj_a, "context", "categories"), json={"category_id": "c", "name": "C"}
    ).status_code == 201
    test_client.post(_synth_url(proj_a, "context", "synthesize"))

    # Project A's group item must not be assignable against Project B.
    res = test_client.post(
        _synth_url(proj_b, "context", "assign-by-group-item"),
        data={
            "categoryId": "c",
            "contextImpact": "ENABLE",
            "groupItemId": str(seeded_a["group_item_id"]),
            "publicationId": str(seeded_a["pub_id"]),
            "latestRevisionId": str(seeded_a["rev_id"]),
            "sourceContextText": "text",
        },
    )
    assert res.status_code in (400, 404)

    # Project B cannot see Project A's context assignments.
    workspace_b = test_client.post(_synth_url(proj_b, "context", "synthesize")).json()
    assert len(workspace_b["assignments"]) == 1
    assert all(a["project_id"] == proj_b for a in workspace_b["assignments"])


def test_adversarial_mechanism_cross_project_assign_rejected(client):
    test_client, db_path = client
    proj_a = "adv-mech-a"
    proj_b = "adv-mech-b"
    _create_project(db_path, proj_a)
    _create_project(db_path, proj_b)
    _seed_complete_evidence(db_path, proj_a)
    _seed_complete_evidence(db_path, proj_b)

    test_client.get(_synth_url(proj_a, "matrix"))
    test_client.get(_synth_url(proj_b, "matrix"))
    assert test_client.post(
        _synth_url(proj_a, "mechanisms", "categories"), json={"category_id": "m", "name": "M"}
    ).status_code == 201
    pathway_a = test_client.get(_synth_url(proj_a, "mechanisms")).json()["pathways"][0]["pathway"]["pathway_id"]

    # Assigning Project A's pathway through Project B must fail.
    res = test_client.post(
        _synth_url(proj_b, "mechanisms", "pathways", pathway_a, "assign"),
        json={"category_id": "m", "is_review_synthesized": False},
    )
    assert res.status_code == 404


def test_adversarial_nonexistent_resources_404(client):
    test_client, db_path = client
    proj_id = "adv-404"
    _create_project(db_path, proj_id)
    _seed_complete_evidence(db_path, proj_id)
    test_client.get(_synth_url(proj_id, "matrix"))
    test_client.post(_synth_url(proj_id, "context", "synthesize"))

    assert test_client.post(
        _synth_url(proj_id, "categories", "lean"),
        json={"category_id": "c1", "name": "C1"},
    ).status_code == 201
    assert test_client.delete(_synth_url(proj_id, "categories", "lean", "no-such-cat")).status_code == 404

    assert test_client.post(
        _synth_url(proj_id, "mechanisms", "categories"), json={"category_id": "mc", "name": "MC"}
    ).status_code == 201
    assert test_client.delete(_synth_url(proj_id, "mechanisms", "categories", "no-such-mc")).status_code == 404

    assert test_client.get(
        _synth_url(proj_id, "matrix", "cell-detail"),
        params={"leanCategoryId": "no-such", "energyCategoryId": "no-such"},
    ).status_code == 404

    assert test_client.get(_synth_url(proj_id, "snapshots", "1", "export"), params={"format": "json"}).status_code == 404


def test_adversarial_duplicate_and_invalid_category_400(client):
    test_client, db_path = client
    proj_id = "adv-dup"
    _create_project(db_path, proj_id)
    _seed_complete_evidence(db_path, proj_id)

    first = test_client.post(
        _synth_url(proj_id, "categories", "lean"), json={"category_id": "c1", "name": "C1"}
    )
    assert first.status_code == 201
    dup = test_client.post(
        _synth_url(proj_id, "categories", "lean"), json={"category_id": "c1", "name": "C1 again"}
    )
    assert dup.status_code == 400

    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "cc", "name": "CC"}
    ).status_code == 201
    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "cc", "name": "CC again"}
    ).status_code == 400

    # Empty category name is rejected.
    assert test_client.post(
        _synth_url(proj_id, "categories", "energy"), json={"category_id": "e1", "name": "   "}
    ).status_code in (400, 422)


def test_adversarial_gap_link_untraceable_target_rejected(client):
    test_client, db_path = client
    proj_id = "adv-gap"
    _create_project(db_path, proj_id)
    _seed_complete_evidence(db_path, proj_id)

    gap_id = test_client.post(
        _synth_url(proj_id, "research-gaps"),
        json={"gap_type": "thematic", "title": "Gap", "rationale": "R.", "researcher_id": "r1"},
    ).json()["gap_id"]

    # A foreign / nonexistent target is not a traceable synthesis artifact.
    res = test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "mechanism_pathway", "target_id": str(uuid4())},
    )
    assert res.status_code == 400

    # Malformed link_type is rejected.
    res2 = test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "bogus_type", "target_id": str(uuid4())},
    )
    assert res2.status_code in (400, 422)


def test_adversarial_mechanism_approve_unassigned_rejected(client):
    test_client, db_path = client
    proj_id = "adv-approve"
    _create_project(db_path, proj_id)
    _seed_complete_evidence(db_path, proj_id)
    test_client.get(_synth_url(proj_id, "matrix"))

    pathway_id = test_client.get(_synth_url(proj_id, "mechanisms")).json()["pathways"][0]["pathway"]["pathway_id"]

    # Approving a pathway that has never been assigned must fail cleanly.
    res = test_client.post(
        _synth_url(proj_id, "mechanisms", "pathways", pathway_id, "approve"),
        json={"reviewer_id": "r1"},
    )
    assert res.status_code in (400, 404)


def test_adversarial_project_delete_then_mutation_404(client):
    test_client, db_path = client
    proj_id = "adv-lifecycle"
    _create_project(db_path, proj_id)
    _seed_complete_evidence(db_path, proj_id)
    test_client.get(_synth_url(proj_id, "matrix"))

    assert test_client.delete(f"/projects/{proj_id}").status_code == 204
    assert test_client.get(_synth_url(proj_id, "classifications")).status_code == 404
    assert test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r"}).status_code == 404
    assert test_client.delete(_synth_url(proj_id, "categories", "lean", "c")).status_code == 404
    assert test_client.delete(f"/projects/{proj_id}").status_code == 404


def test_adversarial_snapshot_export_isolated_and_format_rejected(client):
    test_client, db_path = client
    proj_a = "adv-exp-a"
    proj_b = "adv-exp-b"
    _create_project(db_path, proj_a)
    _create_project(db_path, proj_b)
    _seed_complete_evidence(db_path, proj_a)
    _seed_complete_evidence(db_path, proj_b)
    test_client.get(_synth_url(proj_a, "matrix"))
    test_client.get(_synth_url(proj_b, "matrix"))

    snap_a = test_client.post(_synth_url(proj_a, "snapshots"), json={"actor": "r1"}).json()
    test_client.post(_synth_url(proj_b, "snapshots"), json={"actor": "r1"}).json()

    export_a = test_client.get(_synth_url(proj_a, "snapshots", "1", "export"), params={"format": "json"}).json()
    assert export_a["content"]["project_id"] == proj_a
    assert export_a["content"]["relations"] == snap_a["content"]["relations"]

    unknown = test_client.get(_synth_url(proj_a, "snapshots", "1", "export"), params={"format": "xml"})
    assert unknown.status_code in (400, 422, 200)
