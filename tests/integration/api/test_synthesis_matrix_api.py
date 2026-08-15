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
    ClassificationApprovalState,
    EnergyEffectCategory,
    LeanPracticeCategory,
    TermMapping,
    TermType,
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
def client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test_matrix_api.db"
    _apply_migrations_up_to(db_path, "0021_analytical_relations.sql")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))

    project_repo = SqliteProjectRepository(db_path)
    class_repo = SqliteSynthesisClassificationRepository(db_path)
    extraction_repo = SqliteExtractionRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    template_repo = SqliteExtractionTemplateRepository(db_path)

    proj_id = "test_matrix_proj"
    project_repo.create(Project(project_id=proj_id, title="Test Matrix Project", description=""))

    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    # Create categories & mappings
    class_repo.create_lean_category(
        LeanPracticeCategory(project_id=proj_id, category_id="cat_5s", name="5S Methodology")
    )
    class_repo.create_energy_category(
        EnergyEffectCategory(project_id=proj_id, category_id="cat_elec", name="Electricity Consumption")
    )

    class_repo.save_term_mapping(
        TermMapping(
            project_id=proj_id,
            term_type=TermType.LEAN_PRACTICE,
            source_value="5S Practice",
            analytical_category_id="cat_5s",
            approval_state=ClassificationApprovalState.APPROVED,
            approved_by="reviewer_1",
        )
    )

    class_repo.save_term_mapping(
        TermMapping(
            project_id=proj_id,
            term_type=TermType.ENERGY_EFFECT,
            source_value="Energy Use",
            analytical_category_id="cat_elec",
            approval_state=ClassificationApprovalState.APPROVED,
            approved_by="reviewer_1",
        )
    )

    # Add publication & extraction revision
    pub_id = uuid4()
    pub_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub_id,
                title="Empirical Analysis of 5S",
                publication_year=2023,
            )
        ],
    )

    rec = extraction_repo.create_record(
        ExtractionRecord(
            project_id=proj_id,
            publication_id=pub_id,
            template_id="lean_energy",
            template_version="1.0.0",
        )
    )

    g_id = uuid4()
    rev = ExtractionRevision(
        record_id=rec.record_id,
        project_id=proj_id,
        publication_id=pub_id,
        revision_index=1,
        reviewer_id="reviewer_1",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        group_items=[
            ExtractedGroupItemState(
                group_item_id=g_id,
                group_key="lean_energy_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="lean_practice",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="5S Practice",
                    ),
                    ExtractedValueState(
                        field_key="energy_effect_indicator",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="Energy Use",
                    ),
                    ExtractedValueState(
                        field_key="effect_magnitude",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        float_value=100.0,
                        unit_value="kWh",
                    ),
                    ExtractedValueState(
                        field_key="evidence_character",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="Empirical",
                    ),
                ],
            )
        ],
    )
    extraction_repo.append_revision(rev)

    with TestClient(app) as test_client:
        yield test_client, proj_id, g_id


def test_get_synthesis_matrix_api(client):
    test_client, proj_id, _ = client

    response = test_client.get(f"/projects/{proj_id}/synthesis/matrix")
    assert response.status_code == 200
    data = response.json()

    assert data["project_id"] == proj_id
    assert len(data["lean_categories"]) == 1
    assert len(data["energy_categories"]) == 1
    assert data["total_relations"] == 1
    assert data["total_publications"] == 1
    assert data["unclassified_relations_count"] == 0

    cell = data["cells"][0]
    assert cell["lean_category_id"] == "cat_5s"
    assert cell["energy_category_id"] == "cat_elec"
    assert cell["relation_count"] == 1
    assert cell["publication_count"] == 1


def test_get_matrix_cell_detail_api(client):
    test_client, proj_id, g_id = client

    response = test_client.get(
        f"/projects/{proj_id}/synthesis/matrix/cell-detail",
        params={"leanCategoryId": "cat_5s", "energyCategoryId": "cat_elec"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["lean_category"]["category_id"] == "cat_5s"
    assert data["energy_category"]["category_id"] == "cat_elec"
    assert data["relation_count"] == 1
    assert data["publication_count"] == 1
    assert len(data["relations"]) == 1

    rel_item = data["relations"][0]
    assert rel_item["publication_title"] == "Empirical Analysis of 5S"
    assert rel_item["relation"]["source_practice"] == "5S Practice"
    assert rel_item["relation"]["source_effect"] == "Energy Use"
    assert rel_item["relation"]["magnitude"] == 100.0
    assert rel_item["relation"]["original_unit"] == "kWh"


def test_unit_conversion_preview_and_save_api(client):
    test_client, proj_id, _ = client

    # Get relation_id from matrix cell detail
    detail_res = test_client.get(
        f"/projects/{proj_id}/synthesis/matrix/cell-detail",
        params={"leanCategoryId": "cat_5s", "energyCategoryId": "cat_elec"},
    )
    assert detail_res.status_code == 200
    relation_id = detail_res.json()["relations"][0]["relation"]["relation_id"]

    # 1. Preview conversion (100 kWh -> MJ = 360 MJ)
    preview_res = test_client.post(
        f"/projects/{proj_id}/synthesis/relations/{relation_id}/convert-unit",
        json={"target_unit": "MJ"},
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert pytest.approx(preview_data["transformed_value"], 1e-6) == 360.0
    assert preview_data["transformed_unit"] == "MJ"
    assert "3.6" in preview_data["conversion_rule"]

    # 2. Save conversion
    save_res = test_client.post(
        f"/projects/{proj_id}/synthesis/relations/{relation_id}/save-converted-unit",
        json={"target_unit": "MJ"},
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["converted_value"] is not None
    assert pytest.approx(save_data["converted_value"]["transformed_value"], 1e-6) == 360.0
    assert save_data["converted_value"]["transformed_unit"] == "MJ"

    # Source magnitude preserved
    assert save_data["magnitude"] == 100.0
    assert save_data["original_unit"] == "kWh"
