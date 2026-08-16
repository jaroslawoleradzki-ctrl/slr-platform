"""Integration tests for Mechanism Synthesis API endpoints (Task 10.4)."""

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
    EnergyEffectCategory,
    LeanPracticeCategory,
    RelationDirection,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import (
    SqliteExtractionTemplateRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
)


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
    db_path = tmp_path / "test_mechanism_api.db"
    _apply_migrations_up_to(db_path, "0022_mechanism_synthesis.sql")
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))

    return TestClient(app), db_path


def test_mechanism_category_api_crud(client):
    test_client, db_path = client
    proj_repo = SqliteProjectRepository(db_path)
    proj_id = "test-api-mech-cat"
    proj_repo.create(Project(project_id=proj_id, title="API Project", description=""))

    # 1. List empty
    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories")
    assert res.status_code == 200
    assert res.json() == []

    # 2. Create
    create_payload = {
        "category_id": "idle_reduction",
        "name": "Idle-Time Reduction",
        "description": "Mitigating standby consumption.",
        "display_order": 1,
    }
    res = test_client.post(f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories", json=create_payload)
    assert res.status_code == 201
    assert res.json()["name"] == "Idle-Time Reduction"

    # 3. Duplicate creation fails
    res = test_client.post(f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories", json=create_payload)
    assert res.status_code == 400

    # 4. Update
    update_payload = {
        "name": "Standby and Idle-Time Reduction",
        "description": "Updated description",
        "display_order": 2,
    }
    res = test_client.put(
        f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories/idle_reduction",
        json=update_payload,
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Standby and Idle-Time Reduction"

    # 5. Delete
    res = test_client.delete(f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories/idle_reduction")
    assert res.status_code == 204

    # 6. Verify deleted
    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories")
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_mechanism_workspace_and_synthesis_flow(client):
    test_client, db_path = client
    proj_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    ext_repo = SqliteExtractionRepository(db_path)
    class_repo = SqliteSynthesisClassificationRepository(db_path)
    matrix_repo = SqliteSynthesisMatrixRepository(db_path)

    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    proj_id = "test-api-mech-flow"
    proj_repo.create(Project(project_id=proj_id, title="Flow Project", description=""))

    # Seed Lean & Energy taxonomies
    class_repo.create_lean_category(
        LeanPracticeCategory(category_id="5s", name="5S & Visual Management", project_id=proj_id)
    )
    class_repo.create_energy_category(
        EnergyEffectCategory(category_id="elec", name="Electricity Demand", project_id=proj_id)
    )

    # Seed publication and Phase 9 extraction revision
    pub_id = uuid4()
    pub_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub_id,
                title="Lean Factory Study",
                publication_year=2024,
            )
        ],
    )

    rec = ext_repo.create_record(
        ExtractionRecord(
            project_id=proj_id,
            publication_id=pub_id,
            template_id="lean_energy",
            template_version="1.0.0",
        )
    )

    group_item_id = uuid4()
    item = ExtractedGroupItemState(
        group_item_id=group_item_id,
        group_key="lean_energy_relationships",
        item_index=1,
        values=[
            ExtractedValueState(
                field_key="impact_mechanism",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Turning off idle hydraulic pumps during batch changeover reduced peak kW.",
                source_locator="Table 1",
            ),
        ],
    )
    rev = ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[item],
        )
    )

    # Create Task 10.3 Analytical Relation
    rel_id = uuid4()
    rel = AnalyticalRelation(
        relation_id=rel_id,
        project_id=proj_id,
        publication_id=pub_id,
        latest_revision_id=rev.revision_id,
        group_item_id=group_item_id,
        item_index=1,
        source_practice="5S Controls",
        analytical_lean_category_id="5s",
        source_effect="Peak kW",
        analytical_energy_category_id="elec",
        direction=RelationDirection.POSITIVE,
        approval_state=ClassificationApprovalState.APPROVED,
    )
    matrix_repo.save_analytical_relation(rel)

    # 1. Create Mechanism Category
    res = test_client.post(
        f"/api/v1/projects/{proj_id}/synthesis/mechanisms/categories",
        json={
            "category_id": "idle_reduction",
            "name": "Idle-Time Reduction",
            "description": "Turning off equipment when unused.",
        },
    )
    assert res.status_code == 201

    # 2. Get Workspace
    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/mechanisms")
    assert res.status_code == 200
    workspace = res.json()
    assert workspace["stats"]["total_pathways"] == 1
    assert workspace["stats"]["unmapped_count"] == 1
    pathway = workspace["pathways"][0]["pathway"]
    pathway_id = pathway["pathway_id"]
    assert (
        pathway["source_mechanism_text"] == "Turning off idle hydraulic pumps during batch changeover reduced peak kW."
    )
    assert pathway["approval_state"] == "pending"

    # 3. Assign Mechanism Category
    assign_payload = {
        "category_id": "idle_reduction",
        "is_review_synthesized": False,
        "notes": "Direct quote from empirical results.",
    }
    res = test_client.post(
        f"/api/v1/projects/{proj_id}/synthesis/mechanisms/pathways/{pathway_id}/assign",
        json=assign_payload,
    )
    assert res.status_code == 200
    assert res.json()["analytical_mechanism_category_id"] == "idle_reduction"

    # 4. Approve Pathway
    res = test_client.post(
        f"/api/v1/projects/{proj_id}/synthesis/mechanisms/pathways/{pathway_id}/approve",
        json={"reviewer_id": "lead_researcher"},
    )
    assert res.status_code == 200
    assert res.json()["approval_state"] == "approved"
    assert res.json()["approved_by"] == "lead_researcher"

    # 5. Get Synthesis Chains
    res = test_client.get(f"/api/v1/projects/{proj_id}/synthesis/mechanisms/synthesis")
    assert res.status_code == 200
    chains = res.json()
    assert len(chains) == 1
    assert chains[0]["lean_category_id"] == "5s"
    assert chains[0]["mechanism_category_id"] == "idle_reduction"
    assert chains[0]["energy_category_id"] == "elec"
    assert chains[0]["pathway_count"] == 1
    assert chains[0]["publication_count"] == 1
    assert chains[0]["relation_count"] == 1
