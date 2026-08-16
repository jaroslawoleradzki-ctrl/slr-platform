"""Task 10.8 E2E verification suite (E2E-1 .. E2E-20).

End-to-end API journeys that drive the complete Phase 10 synthesis pipeline —
classification, matrix, mechanism, context, research gaps, and snapshots —
through the public HTTP API, plus adversarial integration guards for project
isolation, immutability, COMPLETE-only semantics, deletion cleanup, and the
no-AI / no-aggregate-score contract.
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
    db_path = tmp_path / "test_synthesis_e2e.db"
    _apply_migrations_up_to(db_path)
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))
    return TestClient(app), db_path


def _create_project(db_path: str, proj_id: str, title: str = "E2E Project") -> None:
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title=title, description=""))


def _seed_evidence(
    db_path: str,
    proj_id: str,
    *,
    practice: str = "Single Minute Exchange of Die",
    effect: str = "Compressed Air",
    magnitude: float | None = None,
    direction: str | None = None,
    mechanism: str | None = None,
    moderating: str | None = None,
    completeness: ExtractionCompletenessStatus = ExtractionCompletenessStatus.COMPLETE,
    extra_items: int = 0,
    reuse_pub_id=None,
    group_item_id=None,
) -> dict:
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

    if reuse_pub_id is not None:
        pub_id = reuse_pub_id
    else:
        pub_id = uuid4()
        pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="E2E Study", publication_year=2024)])

    existing_records = ext_repo.list_records(proj_id)
    rec = next((r for r in existing_records if r.publication_id == pub_id), None)
    revision_index = 1
    if rec is None:
        rec = ext_repo.create_record(
            ExtractionRecord(
                project_id=proj_id, publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
            )
        )
    else:
        history = ext_repo.list_revision_history(proj_id, pub_id)
        revision_index = len(history) + 1

    group_item_id = group_item_id or uuid4()
    values = [
        ExtractedValueState(
            field_key="lean_practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value=practice
        ),
        ExtractedValueState(
            field_key="energy_effect_indicator", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value=effect
        ),
    ]
    if magnitude is not None:
        values.append(
            ExtractedValueState(
                field_key="effect_magnitude",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value=str(magnitude),
                float_value=magnitude,
            )
        )
    if direction is not None:
        values.append(
            ExtractedValueState(
                field_key="direction", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value=direction
            )
        )
    if mechanism is not None:
        values.append(
            ExtractedValueState(
                field_key="impact_mechanism", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value=mechanism
            )
        )
    if moderating is not None:
        values.append(
            ExtractedValueState(
                field_key="moderating_conditions",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value=moderating,
            )
        )

    group_items = [
        ExtractedGroupItemState(
            group_item_id=group_item_id,
            group_key="lean_energy_relationships",
            item_index=1,
            values=values,
        )
    ]
    for idx in range(2, 2 + extra_items):
        group_items.append(
            ExtractedGroupItemState(
                group_item_id=uuid4(),
                group_key="lean_energy_relationships",
                item_index=idx,
                values=[
                    ExtractedValueState(
                        field_key="lean_practice",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value=f"{practice} v{idx}",
                    ),
                    ExtractedValueState(
                        field_key="energy_effect_indicator",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value=f"{effect} v{idx}",
                    ),
                ],
            )
        )

    rev = ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=revision_index,
            reviewer_id="reviewer_1",
            completeness_status=completeness,
            group_items=group_items,
        )
    )

    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev_id": rev.revision_id,
        "practice": practice,
        "effect": effect,
    }


def _synth_url(proj_id: str, *parts: str) -> str:
    return f"/projects/{proj_id}/synthesis/{'/'.join(parts)}"


def _seed_qa_profile(db_path: str, proj_id: str, pub_id) -> None:
    from app.domain.quality_assessment import (
        QualityAssessment,
        QualityAssessmentResponse,
        QualityAssessmentResponseValue,
        QualityAssessmentTemplate,
        QualityAssessmentTemplateCriterion,
        QualityAssessmentTool,
    )
    from app.repositories.sqlite_quality_assessment_repository import (
        SqliteQualityAssessmentCatalogRepository,
        SqliteQualityAssessmentRepository,
    )

    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    try:
        catalog_repo.create_tool(QualityAssessmentTool(tool_id="casp_tool", name="CASP Tool"))
    except Exception:
        pass
    tid = uuid4()
    crit1 = uuid4()
    crit2 = uuid4()
    ass_id = uuid4()
    catalog_repo.create_template_version(
        QualityAssessmentTemplate(
            template_id=tid,
            tool_id="casp_tool",
            template_key="lean_qa",
            name="Lean QA Template",
            version=1,
            is_active=True,
            criteria=[
                QualityAssessmentTemplateCriterion(
                    criterion_id=crit1,
                    template_id=tid,
                    display_order=1,
                    question="Is the study design clearly described?",
                ),
                QualityAssessmentTemplateCriterion(
                    criterion_id=crit2,
                    template_id=tid,
                    display_order=2,
                    question="Are energy measurements metered directly?",
                ),
            ],
        )
    )
    qa_repo = SqliteQualityAssessmentRepository(db_path)
    qa_repo.save_assessment(
        QualityAssessment(
            assessment_id=ass_id,
            project_id=proj_id,
            publication_id=pub_id,
            template_id=tid,
            reviewer_id="lead_reviewer",
            responses=[
                QualityAssessmentResponse(
                    assessment_id=ass_id,
                    criterion_id=crit1,
                    question_snapshot="Is the study design clearly described?",
                    response_value=QualityAssessmentResponseValue.YES,
                    justification="Detailed methodology provided in section 3.",
                ),
                QualityAssessmentResponse(
                    assessment_id=ass_id,
                    criterion_id=crit2,
                    question_snapshot="Are energy measurements metered directly?",
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="Values estimated from machine specifications.",
                ),
            ],
        )
    )


# ---------------------------------------------------------------------------
# E2E-1: Classification pipeline
# ---------------------------------------------------------------------------


def test_e2e_01_classification_pipeline(client):
    test_client, db_path = client
    proj_id = "e2e-01"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id)

    ws = test_client.get(_synth_url(proj_id, "classifications"))
    assert ws.status_code == 200
    data = ws.json()
    assert {t["source_value"] for t in data["lean_terms"]} == {"Single Minute Exchange of Die"}
    assert {t["source_value"] for t in data["energy_terms"]} == {"Compressed Air"}
    assert data["stats"]["mapped_count"] == 0

    assert test_client.post(
        _synth_url(proj_id, "categories", "lean"),
        json={"category_id": "smed", "name": "SMED & Quick Changeover"},
    ).status_code == 201
    assert test_client.post(
        _synth_url(proj_id, "categories", "energy"),
        json={"category_id": "compressed_air", "name": "Compressed Air"},
    ).status_code == 201

    mapping = test_client.put(
        _synth_url(proj_id, "classifications"),
        json={
            "term_type": "lean_practice",
            "source_value": "Single Minute Exchange of Die",
            "analytical_category_id": "smed",
        },
    )
    assert mapping.status_code == 200
    assert mapping.json()["approval_state"] == "pending"

    approved = test_client.post(
        _synth_url(proj_id, "classifications", "approve"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "reviewer_id": "r1"},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_state"] == "approved"

    ws2 = test_client.get(_synth_url(proj_id, "classifications")).json()
    assert ws2["stats"]["mapped_count"] == 1
    assert ws2["stats"]["approved_count"] == 1


# ---------------------------------------------------------------------------
# E2E-2: Matrix aggregation
# ---------------------------------------------------------------------------


def test_e2e_02_matrix_aggregation(client):
    test_client, db_path = client
    proj_id = "e2e-02"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, direction="positive", magnitude=12.5)

    for body in (
        {"category_id": "smed", "name": "SMED"},
        {"category_id": "compressed_air", "name": "Compressed Air"},
    ):
        kind = "lean" if body["category_id"] == "smed" else "energy"
        assert test_client.post(_synth_url(proj_id, "categories", kind), json=body).status_code == 201
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "analytical_category_id": "smed"},
    )
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "energy_effect", "source_value": "Compressed Air", "analytical_category_id": "compressed_air"},
    )
    test_client.post(
        _synth_url(proj_id, "classifications", "approve"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "reviewer_id": "r1"},
    )
    test_client.post(
        _synth_url(proj_id, "classifications", "approve"),
        json={"term_type": "energy_effect", "source_value": "Compressed Air", "reviewer_id": "r1"},
    )

    matrix = test_client.get(_synth_url(proj_id, "matrix"))
    assert matrix.status_code == 200
    data = matrix.json()
    assert data["total_relations"] == 1
    assert data["total_publications"] == 1
    assert len(data["cells"]) == 1
    cell = data["cells"][0]
    assert cell["lean_category_id"] == "smed"
    assert cell["energy_category_id"] == "compressed_air"
    assert cell["relation_count"] == 1
    assert cell["publication_count"] == 1
    assert cell["direction_distribution"].get("positive") == 1

    detail = test_client.get(
        _synth_url(proj_id, "matrix", "cell-detail"),
        params={"leanCategoryId": "smed", "energyCategoryId": "compressed_air"},
    )
    assert detail.status_code == 200
    assert detail.json()["relation_count"] == 1


# ---------------------------------------------------------------------------
# E2E-3: Mechanism synthesis pipeline
# ---------------------------------------------------------------------------


def test_e2e_03_mechanism_synthesis_pipeline(client):
    test_client, db_path = client
    proj_id = "e2e-03"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, mechanism="Reduced idle time in die changeovers.")

    for body in (
        {"category_id": "smed", "name": "SMED"},
        {"category_id": "compressed_air", "name": "Compressed Air"},
    ):
        kind = "lean" if body["category_id"] == "smed" else "energy"
        assert test_client.post(_synth_url(proj_id, "categories", kind), json=body).status_code == 201
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "analytical_category_id": "smed"},
    )
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "energy_effect", "source_value": "Compressed Air", "analytical_category_id": "compressed_air"},
    )
    test_client.get(_synth_url(proj_id, "matrix"))

    ws = test_client.get(_synth_url(proj_id, "mechanisms"))
    assert ws.status_code == 200
    data = ws.json()
    assert data["stats"]["total_pathways"] == 1
    pathway_id = data["pathways"][0]["pathway"]["pathway_id"]

    assert test_client.post(
        _synth_url(proj_id, "mechanisms", "categories"),
        json={"category_id": "idle_reduction", "name": "Idle-Time Reduction"},
    ).status_code == 201

    assigned = test_client.post(
        _synth_url(proj_id, "mechanisms", "pathways", pathway_id, "assign"),
        json={"category_id": "idle_reduction", "is_review_synthesized": False},
    )
    assert assigned.status_code == 200
    assert assigned.json()["analytical_mechanism_category_id"] == "idle_reduction"

    approved = test_client.post(
        _synth_url(proj_id, "mechanisms", "pathways", pathway_id, "approve"),
        json={"reviewer_id": "r1"},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_state"] == "approved"

    chains = test_client.get(_synth_url(proj_id, "mechanisms", "synthesis"))
    assert chains.status_code == 200
    assert chains.json()[0]["mechanism_category_id"] == "idle_reduction"


# ---------------------------------------------------------------------------
# E2E-4: Context synthesis pipeline
# ---------------------------------------------------------------------------


def test_e2e_04_context_synthesis_pipeline(client):
    test_client, db_path = client
    proj_id = "e2e-04"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id, moderating="High product mix environment.")
    test_client.get(_synth_url(proj_id, "matrix"))

    assert test_client.post(
        _synth_url(proj_id, "context", "categories"),
        json={"category_id": "product_mix", "name": "Product Mix"},
    ).status_code == 201

    ws = test_client.post(_synth_url(proj_id, "context", "synthesize"))
    assert ws.status_code == 200
    data = ws.json()
    assert len(data["assignments"]) == 1
    assert data["assignments"][0]["source_context_text"] == "High product mix environment."

    assigned = test_client.post(
        _synth_url(proj_id, "context", "assign-by-group-item"),
        data={
            "categoryId": "product_mix",
            "contextImpact": "STRENGTHEN",
            "groupItemId": str(seeded["group_item_id"]),
            "publicationId": str(seeded["pub_id"]),
            "latestRevisionId": str(seeded["rev_id"]),
            "sourceContextText": "High product mix environment.",
        },
    )
    assert assigned.status_code == 201
    assert assigned.json()["analytical_context_category_id"] == "product_mix"
    assert assigned.json()["context_impact"] == "STRENGTHEN"
    link_id = assigned.json()["assignment_id"]

    remapped = test_client.put(
        _synth_url(proj_id, "context", "remap"),
        params={"linkId": link_id, "projectId": proj_id},
        json={"category_id": "product_mix", "context_impact": "WEAKEN"},
    )
    assert remapped.status_code == 200
    assert remapped.json()["analytical_context_category_id"] == "product_mix"
    assert remapped.json()["context_impact"] == "WEAKEN"

    summary = test_client.get(_synth_url(proj_id, "context", "summary"))
    assert summary.status_code == 200
    assert summary.json()["context_evidence_count"] >= 1
    assert summary.json()["distinct_analytical_relation_count"] >= 1

    unassigned = test_client.put(
        _synth_url(proj_id, "context", "unassign", link_id),
        params={"projectId": proj_id},
    )
    assert unassigned.status_code == 200

    summary_after = test_client.get(_synth_url(proj_id, "context", "summary"))
    assert summary_after.json()["context_evidence_count"] == 0


# ---------------------------------------------------------------------------
# E2E-5: Research gap pipeline
# ---------------------------------------------------------------------------


def test_e2e_05_research_gap_pipeline(client):
    test_client, db_path = client
    proj_id = "e2e-05"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, mechanism="Mechanism text for gap linking.")

    test_client.get(_synth_url(proj_id, "matrix"))
    pathway_id = test_client.get(_synth_url(proj_id, "mechanisms")).json()["pathways"][0]["pathway"]["pathway_id"]

    created = test_client.post(
        _synth_url(proj_id, "research-gaps"),
        json={
            "gap_type": "mechanism",
            "title": "Missing mechanism detail",
            "rationale": "Studies rarely report intermediate mechanism steps.",
            "researcher_id": "r1",
        },
    )
    assert created.status_code == 201
    gap_id = created.json()["gap_id"]

    candidates = test_client.get(_synth_url(proj_id, "research-gaps", "evidence-candidates"))
    assert candidates.status_code == 200
    assert any(c["target_id"] == pathway_id for c in candidates.json())

    linked = test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "mechanism_pathway", "target_id": pathway_id},
    )
    assert linked.status_code == 201

    detail = test_client.get(_synth_url(proj_id, "research-gaps", gap_id)).json()
    assert len(detail["links"]) == 1
    assert detail["links"][0]["target_id"] == pathway_id


# ---------------------------------------------------------------------------
# E2E-6: Full end-to-end journey into an immutable snapshot
# ---------------------------------------------------------------------------


def test_e2e_06_full_journey_snapshot(client):
    test_client, db_path = client
    proj_id = "e2e-06"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(
        db_path,
        proj_id,
        mechanism="Reduced idle time in die changeovers.",
        moderating="High product mix environment.",
        direction="positive",
        magnitude=9.5,
    )
    _seed_qa_profile(db_path, proj_id, seeded["pub_id"])

    for path_parts, body in (
        (("categories", "lean"), {"category_id": "smed", "name": "SMED"}),
        (("categories", "energy"), {"category_id": "compressed_air", "name": "Compressed Air"}),
        (("mechanisms", "categories"), {"category_id": "idle_reduction", "name": "Idle-Time Reduction"}),
        (("context", "categories"), {"category_id": "product_mix", "name": "Product Mix"}),
    ):
        assert test_client.post(_synth_url(proj_id, *path_parts), json=body).status_code in (201, 400)

    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "analytical_category_id": "smed"},
    )
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "energy_effect", "source_value": "Compressed Air", "analytical_category_id": "compressed_air"},
    )

    test_client.get(_synth_url(proj_id, "matrix"))
    test_client.get(_synth_url(proj_id, "mechanisms"))
    test_client.post(_synth_url(proj_id, "context", "synthesize"))

    pathway_id = test_client.get(_synth_url(proj_id, "mechanisms")).json()["pathways"][0]["pathway"]["pathway_id"]

    gap_id = test_client.post(
        _synth_url(proj_id, "research-gaps"),
        json={"gap_type": "thematic", "title": "Contextual gap", "rationale": "Rationale.", "researcher_id": "r1"},
    ).json()["gap_id"]
    test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "mechanism_pathway", "target_id": pathway_id},
    )

    snap = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"})
    assert snap.status_code == 201
    content = snap.json()["content"]
    assert content["project_id"] == proj_id
    assert len(content["relations"]) == 1
    assert len(content["mechanism_pathways"]) == 1
    assert len(content["context_assignments"]) == 1
    assert len(content["research_gaps"]) == 1
    assert len(content["research_gap_links"]) == 1
    assert len(content["term_mappings"]) == 2
    assert {c["category_id"] for c in content["lean_categories"]} == {"smed"}
    assert {c["category_id"] for c in content["energy_categories"]} == {"compressed_air"}
    assert {c["category_id"] for c in content["mechanism_categories"]} == {"idle_reduction"}
    assert {c["category_id"] for c in content["context_categories"]} == {"product_mix"}
    assert len(content["qa_profiles"]) == 1

    export = test_client.get(_synth_url(proj_id, "snapshots", "1", "export"), params={"format": "json"})
    assert export.status_code == 200
    assert export.json()["content"]["relations"][0]["group_item_id"] == str(seeded["group_item_id"])


# ---------------------------------------------------------------------------
# E2E-7: DRAFT (IN_PROGRESS) revisions are excluded from synthesis
# ---------------------------------------------------------------------------


def test_e2e_07_draft_revision_excluded(client):
    test_client, db_path = client
    proj_id = "e2e-07"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, completeness=ExtractionCompletenessStatus.IN_PROGRESS)

    ws = test_client.get(_synth_url(proj_id, "classifications")).json()
    assert ws["stats"]["total_terms"] == 0

    matrix = test_client.get(_synth_url(proj_id, "matrix")).json()
    assert matrix["total_relations"] == 0

    mechanisms = test_client.get(_synth_url(proj_id, "mechanisms")).json()
    assert mechanisms["stats"]["total_pathways"] == 0


# ---------------------------------------------------------------------------
# E2E-8: COMPLETE-only dataset hash
# ---------------------------------------------------------------------------


def test_e2e_08_complete_only_dataset_hash(client):
    test_client, db_path = client
    proj_id = "e2e-08"
    _create_project(db_path, proj_id)

    _seed_evidence(db_path, proj_id, completeness=ExtractionCompletenessStatus.IN_PROGRESS, practice="Draft practice")
    snap_draft = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"})
    assert snap_draft.status_code == 201
    hash_draft = snap_draft.json()["extraction_dataset_hash"]

    _seed_evidence(db_path, proj_id, completeness=ExtractionCompletenessStatus.COMPLETE, practice="Complete practice")
    snap_complete = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"})
    assert snap_complete.status_code == 201
    hash_complete = snap_complete.json()["extraction_dataset_hash"]

    assert hash_draft != hash_complete
    assert len(hash_draft) == 64
    assert len(hash_complete) == 64


# ---------------------------------------------------------------------------
# E2E-9: Post-snapshot immutability and monotonic versioning
# ---------------------------------------------------------------------------


def test_e2e_09_post_snapshot_immutability(client):
    test_client, db_path = client
    proj_id = "e2e-09"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id, practice="Original practice")
    test_client.get(_synth_url(proj_id, "matrix"))

    v1 = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    assert v1["version"] == 1
    v1_content_hash = v1["content_hash"]
    v1_dataset_hash = v1["extraction_dataset_hash"]
    v1_content = v1["content"]

    # Re-extraction supersedes with a new COMPLETE revision on the same publication.
    _seed_evidence(db_path, proj_id, practice="Changed practice", reuse_pub_id=seeded["pub_id"])

    stored = test_client.get(_synth_url(proj_id, "snapshots", "1")).json()
    assert stored["content_hash"] == v1_content_hash
    assert stored["extraction_dataset_hash"] == v1_dataset_hash
    assert stored["content"] == v1_content

    # Re-synchronize the matrix so the superseding revision's evidence materializes.
    test_client.get(_synth_url(proj_id, "matrix"))

    v2 = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    assert v2["version"] == 2
    assert v2["content_hash"] != v1_content_hash
    assert v2["extraction_dataset_hash"] != v1_dataset_hash

    listed = test_client.get(_synth_url(proj_id, "snapshots")).json()
    assert [s["version"] for s in listed] == [1, 2]


# ---------------------------------------------------------------------------
# E2E-10: Missing QA profile is tolerated
# ---------------------------------------------------------------------------


def test_e2e_10_missing_qa_tolerated(client):
    test_client, db_path = client
    proj_id = "e2e-10"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "analytical_category_id": "c1"},
    )
    test_client.post(_synth_url(proj_id, "categories", "lean"), json={"category_id": "c1", "name": "C1"})
    test_client.post(_synth_url(proj_id, "categories", "energy"), json={"category_id": "c2", "name": "C2"})
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "energy_effect", "source_value": "Compressed Air", "analytical_category_id": "c2"},
    )
    test_client.get(_synth_url(proj_id, "matrix"))

    snap = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    assert snap["content"]["qa_profiles"] == []
    assert snap["content"]["relations"][0]["publication_id"] == str(seeded["pub_id"])


# ---------------------------------------------------------------------------
# E2E-11: Criterion-level QA preserved (no aggregate scores)
# ---------------------------------------------------------------------------


def test_e2e_11_criterion_level_qa_preserved(client):
    test_client, db_path = client
    proj_id = "e2e-11"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)
    _seed_qa_profile(db_path, proj_id, seeded["pub_id"])
    test_client.post(_synth_url(proj_id, "categories", "lean"), json={"category_id": "c1", "name": "C1"})
    test_client.post(_synth_url(proj_id, "categories", "energy"), json={"category_id": "c2", "name": "C2"})
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "lean_practice", "source_value": "Single Minute Exchange of Die", "analytical_category_id": "c1"},
    )
    test_client.put(
        _synth_url(proj_id, "classifications"),
        json={"term_type": "energy_effect", "source_value": "Compressed Air", "analytical_category_id": "c2"},
    )
    test_client.get(_synth_url(proj_id, "matrix"))

    snap = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    qa_profiles = snap["content"]["qa_profiles"]
    assert len(qa_profiles) == 1
    profile = qa_profiles[0]
    assert profile["reviewer_id"] == "lead_reviewer"
    questions = {c["question_text"]: c["response_value"] for c in profile["criteria_assessments"]}
    assert questions["Is the study design clearly described?"] == "YES"
    assert questions["Are energy measurements metered directly?"] == "NO"
    assert all("justification" in c for c in profile["criteria_assessments"])

    forbidden = {"score", "aggregate_score", "quality_tier", "confidence", "weighting"}
    assert forbidden.isdisjoint(profile.keys())
    for criterion in profile["criteria_assessments"]:
        assert forbidden.isdisjoint(criterion.keys())


# ---------------------------------------------------------------------------
# E2E-12: Multiple relations per publication
# ---------------------------------------------------------------------------


def test_e2e_12_multiple_relations_per_publication(client):
    test_client, db_path = client
    proj_id = "e2e-12"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, extra_items=2)
    test_client.post(_synth_url(proj_id, "categories", "lean"), json={"category_id": "c1", "name": "C1"})
    test_client.post(_synth_url(proj_id, "categories", "energy"), json={"category_id": "c2", "name": "C2"})
    for ttype in ("lean_practice", "energy_effect"):
        test_client.put(
            _synth_url(proj_id, "classifications"),
            json={"term_type": ttype, "source_value": f"{'Single Minute Exchange of Die' if ttype == 'lean_practice' else 'Compressed Air'} v2", "analytical_category_id": "c1" if ttype == "lean_practice" else "c2"},
        )
    matrix = test_client.get(_synth_url(proj_id, "matrix")).json()
    assert matrix["total_relations"] == 3
    assert matrix["total_publications"] == 1

    test_client.post(_synth_url(proj_id, "context", "synthesize"))
    context = test_client.post(_synth_url(proj_id, "context", "synthesize")).json()
    assert len(context["assignments"]) == 3

    snap = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    assert len(snap["content"]["relations"]) == 3


# ---------------------------------------------------------------------------
# E2E-13: Cross-project isolation
# ---------------------------------------------------------------------------


def test_e2e_13_cross_project_isolation(client):
    test_client, db_path = client
    proj_a = "e2e-13a"
    proj_b = "e2e-13b"
    _create_project(db_path, proj_a)
    _create_project(db_path, proj_b)
    _seed_evidence(db_path, proj_a, practice="Project A practice")

    ws_a = test_client.get(_synth_url(proj_a, "classifications")).json()
    ws_b = test_client.get(_synth_url(proj_b, "classifications")).json()
    assert len(ws_a["lean_terms"]) == 1
    assert ws_b["stats"]["total_terms"] == 0
    assert ws_b["lean_terms"] == []

    matrix_b = test_client.get(_synth_url(proj_b, "matrix")).json()
    assert matrix_b["total_relations"] == 0

    missing = test_client.get(_synth_url("missing-project", "classifications"))
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# E2E-14: Superseded revision drives latest synthesis state
# ---------------------------------------------------------------------------


def test_e2e_14_superseded_revision_excluded(client):
    test_client, db_path = client
    proj_id = "e2e-14"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id, practice="Version one practice")
    assert test_client.get(_synth_url(proj_id, "classifications")).json()["stats"]["total_terms"] == 2

    # Same group item superseded by a newer COMPLETE revision on the same publication.
    _seed_evidence(
        db_path,
        proj_id,
        practice="Version two practice",
        reuse_pub_id=seeded["pub_id"],
        group_item_id=seeded["group_item_id"],
    )
    ws = test_client.get(_synth_url(proj_id, "classifications")).json()
    assert {t["source_value"] for t in ws["lean_terms"]} == {"Version two practice"}

    # Latest COMPLETE revision is the only one that drives synthesis state.
    test_client.get(_synth_url(proj_id, "matrix"))
    snap = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    assert {r["source_practice"] for r in snap["content"]["relations"]} == {"Version two practice"}


# ---------------------------------------------------------------------------
# E2E-15: Project deletion removes all synthesis data
# ---------------------------------------------------------------------------


def test_e2e_15_project_deletion_removes_synthesis(client):
    test_client, db_path = client
    proj_id = "e2e-15"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, mechanism="Mechanism.", moderating="Condition.")
    test_client.get(_synth_url(proj_id, "matrix"))
    test_client.get(_synth_url(proj_id, "mechanisms"))
    test_client.post(_synth_url(proj_id, "context", "synthesize"))
    test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"})
    pathway_id = test_client.get(_synth_url(proj_id, "mechanisms")).json()["pathways"][0]["pathway"]["pathway_id"]
    gap_id = test_client.post(
        _synth_url(proj_id, "research-gaps"),
        json={"gap_type": "thematic", "title": "G", "rationale": "R.", "researcher_id": "r1"},
    ).json()["gap_id"]
    test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "mechanism_pathway", "target_id": pathway_id},
    )

    tables = [
        "synthesis_snapshots",
        "synthesis_research_gaps",
        "synthesis_research_gap_links",
        "synthesis_context_links",
        "synthesis_context_categories",
        "synthesis_mechanism_pathways",
        "synthesis_mechanism_categories",
        "synthesis_classification_categories",
        "synthesis_classification_term_mappings",
        "synthesis_matrix_relations",
    ]

    def _count_all() -> int:
        conn = sqlite3.connect(db_path)
        try:
            total = 0
            for table in tables:
                try:
                    total += conn.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (proj_id,)).fetchone()[0]
                except sqlite3.OperationalError:
                    continue
            return total
        finally:
            conn.close()

    assert _count_all() > 0

    res = test_client.delete(f"/projects/{proj_id}")
    assert res.status_code == 204

    assert _count_all() == 0

    conn = sqlite3.connect(db_path)
    try:
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert fk_violations == []
        conn.execute("PRAGMA foreign_keys = ON;")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# E2E-16: Failure and 404 states
# ---------------------------------------------------------------------------


def test_e2e_16_failure_and_404_states(client):
    test_client, db_path = client
    proj_id = "e2e-16"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id)

    assert test_client.get(_synth_url("no-such-project", "classifications")).status_code == 404
    assert test_client.get(_synth_url("no-such-project", "matrix")).status_code == 404
    assert test_client.get(_synth_url("no-such-project", "mechanisms")).status_code == 404
    assert test_client.post(_synth_url("no-such-project", "context", "synthesize")).status_code == 404
    assert test_client.post(_synth_url("no-such-project", "snapshots"), json={"actor": "r"}).status_code == 404

    assert test_client.put(
        _synth_url(proj_id, "context", "remap"),
        params={"linkId": "no-such-link", "projectId": proj_id},
        json={"category_id": "c", "context_impact": "ENABLE"},
    ).status_code == 404

    assert test_client.put(
        _synth_url(proj_id, "context", "unassign", "no-such-link"),
        params={"projectId": proj_id},
    ).status_code == 404

    assert test_client.post(
        _synth_url(proj_id, "classifications", "approve"),
        json={"term_type": "lean_practice", "source_value": "Unmapped term", "reviewer_id": "r"},
    ).status_code == 404

    assert test_client.post(
        _synth_url(proj_id, "context", "assign-by-group-item"),
        data={
            "categoryId": "c",
            "contextImpact": "ENABLE",
            "groupItemId": str(seeded["group_item_id"]),
            "publicationId": str(seeded["pub_id"]),
            "latestRevisionId": str(seeded["rev_id"]),
            "sourceContextText": "text",
        },
    ).status_code == 400

    assert test_client.get(_synth_url(proj_id, "snapshots", "99")).status_code == 404


# ---------------------------------------------------------------------------
# E2E-17: Context assignment upsert is idempotent
# ---------------------------------------------------------------------------


def test_e2e_17_context_assign_idempotent(client):
    test_client, db_path = client
    proj_id = "e2e-17"
    _create_project(db_path, proj_id)
    seeded = _seed_evidence(db_path, proj_id, moderating="Condition text.")
    test_client.get(_synth_url(proj_id, "matrix"))
    assert test_client.post(
        _synth_url(proj_id, "context", "categories"), json={"category_id": "c", "name": "C"}
    ).status_code == 201

    payload = {
        "categoryId": "c",
        "contextImpact": "ENABLE",
        "groupItemId": str(seeded["group_item_id"]),
        "publicationId": str(seeded["pub_id"]),
        "latestRevisionId": str(seeded["rev_id"]),
        "sourceContextText": "Condition text.",
    }
    first = test_client.post(_synth_url(proj_id, "context", "assign-by-group-item"), data=payload)
    assert first.status_code == 201
    link_id = first.json()["assignment_id"]

    second = test_client.post(_synth_url(proj_id, "context", "assign-by-group-item"), data=payload)
    assert second.status_code == 201
    assert second.json()["assignment_id"] == link_id

    workspace = test_client.post(_synth_url(proj_id, "context", "synthesize")).json()
    assert len(workspace["assignments"]) == 1
    assert workspace["stats"]["distinct_analytical_relation_count"] == 1


# ---------------------------------------------------------------------------
# E2E-18: Matrix direction default (regression guard for Checkpoint C)
# ---------------------------------------------------------------------------


def test_e2e_18_matrix_direction_default(client):
    test_client, db_path = client
    proj_id = "e2e-18"
    _create_project(db_path, proj_id)

    _seed_evidence(db_path, proj_id, practice="No magnitude practice", effect="No magnitude effect")
    _seed_evidence(db_path, proj_id, practice="With magnitude practice", effect="With magnitude effect", magnitude=7.0)

    relations = test_client.get(_synth_url(proj_id, "matrix")).json()
    # get_matrix exposes relations only indirectly via cells; query repository directly.
    from app.repositories.synthesis_matrix_repository import SqliteSynthesisMatrixRepository

    stored = SqliteSynthesisMatrixRepository(db_path).list_analytical_relations(proj_id)
    directions = {r.source_practice: r.direction.value for r in stored}
    assert directions["No magnitude practice"] == "cannot_determine"
    assert directions["With magnitude practice"] == "positive"
    assert relations["total_relations"] == 2


# ---------------------------------------------------------------------------
# E2E-19: Gap evidence preserved after unlink and gap deletion
# ---------------------------------------------------------------------------


def test_e2e_19_gap_evidence_preserved(client):
    test_client, db_path = client
    proj_id = "e2e-19"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, mechanism="Mechanism evidence text.")
    test_client.get(_synth_url(proj_id, "matrix"))
    pathway_id = test_client.get(_synth_url(proj_id, "mechanisms")).json()["pathways"][0]["pathway"]["pathway_id"]

    gap_id = test_client.post(
        _synth_url(proj_id, "research-gaps"),
        json={"gap_type": "mechanism", "title": "T", "rationale": "R.", "researcher_id": "r1"},
    ).json()["gap_id"]
    link_id = test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "mechanism_pathway", "target_id": pathway_id},
    ).json()["link_id"]

    unlink = test_client.delete(_synth_url(proj_id, "research-gaps", gap_id, "links", link_id))
    assert unlink.status_code == 204

    candidates = test_client.get(_synth_url(proj_id, "research-gaps", "evidence-candidates")).json()
    assert any(c["target_id"] == pathway_id for c in candidates)

    test_client.post(
        _synth_url(proj_id, "research-gaps", gap_id, "links"),
        json={"link_type": "mechanism_pathway", "target_id": pathway_id},
    )
    deleted = test_client.delete(_synth_url(proj_id, "research-gaps", gap_id))
    assert deleted.status_code == 204

    mechanisms = test_client.get(_synth_url(proj_id, "mechanisms")).json()
    assert mechanisms["stats"]["total_pathways"] == 1


# ---------------------------------------------------------------------------
# E2E-20: No-AI contract + deterministic content hash
# ---------------------------------------------------------------------------

FORBIDDEN_SYNTHESIS_KEYS = {
    "score",
    "aggregate_score",
    "quality_tier",
    "confidence",
    "confidence_score",
    "priority_score",
    "evidence_quality_score",
    "gap_strength",
    "gap_score",
    "ai",
    "llm",
    "gpt",
    "openai",
    "anthropic",
}


def _walk_and_assert_no_forbidden_keys(obj) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert key.lower() not in FORBIDDEN_SYNTHESIS_KEYS, f"forbidden key exposed: {key}"
            _walk_and_assert_no_forbidden_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            _walk_and_assert_no_forbidden_keys(item)


def test_e2e_20_no_ai_contract_and_deterministic_hash(client):
    test_client, db_path = client
    proj_id = "e2e-20"
    _create_project(db_path, proj_id)
    _seed_evidence(db_path, proj_id, direction="positive", magnitude=3.5, mechanism="M", moderating="C")

    test_client.get(_synth_url(proj_id, "matrix"))
    test_client.get(_synth_url(proj_id, "mechanisms"))
    test_client.post(_synth_url(proj_id, "context", "synthesize"))
    test_client.post(
        _synth_url(proj_id, "research-gaps"),
        json={"gap_type": "thematic", "title": "T", "rationale": "R.", "researcher_id": "r1"},
    )

    v1 = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    v2 = test_client.post(_synth_url(proj_id, "snapshots"), json={"actor": "r1"}).json()
    assert v1["version"] == 1
    assert v2["version"] == 2
    assert v1["content_hash"] == v2["content_hash"]

    export = test_client.get(_synth_url(proj_id, "snapshots", "2", "export"), params={"format": "json"}).json()
    _walk_and_assert_no_forbidden_keys(export)
    _walk_and_assert_no_forbidden_keys(v1)
    _walk_and_assert_no_forbidden_keys(v2)
