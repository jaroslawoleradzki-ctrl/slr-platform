"""Integration tests for Research Gap Synthesis API endpoints (Task 10.6)."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

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
from app.domain.quality_assessment import (
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
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
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)
from app.repositories.synthesis_context_repository import (
    SqliteSynthesisContextRepository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
)
from app.services.synthesis_context_service import (
    default_synthesis_context_service,
)
from app.services.synthesis_mechanism_service import (
    default_synthesis_mechanism_service,
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
    db_path = tmp_path / "test_research_gap_api.db"
    _apply_migrations_up_to(db_path, "0025_research_gap_synthesis.sql")
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_path))
    return TestClient(app), db_path


def _seed_evidence(db_path: str, proj_id: str) -> dict:
    """Seeds COMPLETE extraction evidence + analytical relation + pathway + context link."""
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
    pub_repo.add_publications(
        proj_id, [Publication(record_id=pub_id, title="Research Gap API Study", publication_year=2024)]
    )
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
                            field_key="lean_practice", status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED, text_value="Single Minute Exchange of Die",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator", status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED, text_value="Compressed Air",
                        ),
                        ExtractedValueState(
                            field_key="impact_mechanism", status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED, text_value="Reduced idle time in die changeovers.",
                        ),
                        ExtractedValueState(
                            field_key="moderating_conditions", status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED, text_value="High product mix environment.",
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

    default_synthesis_mechanism_service().synchronize_mechanism_pathways(proj_id)
    default_synthesis_context_service().synchronize_context_from_extraction(proj_id)

    pathway = SqliteSynthesisMechanismRepository(db_path).list_pathways(proj_id)[0]
    context_link = SqliteSynthesisContextRepository(db_path).list_links(proj_id)[0]

    return {
        "pub_id": pub_id,
        "group_item_id": group_item_id,
        "rev_id": rev.revision_id,
        "relation_id": rel_id,
        "pathway_id": pathway.pathway_id,
        "context_link_id": UUID(context_link["link_id"]),
    }


def test_empty_workspace(client):
    test_client, db_path = client
    proj_id = "test-api-empty-gap"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Empty", description=""))

    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == proj_id
    assert data["gaps"] == []
    assert data["stats"]["total_gaps"] == 0
    assert data["stats"]["linked_publication_count"] == 0


def test_workspace_missing_project(client):
    test_client, _ = client
    res = test_client.get("/projects/missing/synthesis/research-gaps")
    assert res.status_code == 404


def test_create_and_get_gap(client):
    test_client, db_path = client
    proj_id = "test-api-gap-crud"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="CRUD", description=""))

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={
            "gap_type": "methodological",
            "title": "Recurring measurement limitation",
            "rationale": "Eligible studies rarely report measurement uncertainty for energy baselines.",
            "researcher_id": "researcher-1",
        },
    )
    assert res.status_code == 201
    gap = res.json()
    assert gap["gap_type"] == "methodological"
    assert gap["title"] == "Recurring measurement limitation"
    assert gap["researcher_id"] == "researcher-1"
    assert "gap_strength" not in gap
    assert "gap_score" not in gap

    gap_id = gap["gap_id"]
    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 200
    assert res.json()["gap"]["gap_id"] == gap_id
    assert res.json()["links"] == []


def test_create_gap_validation_errors(client):
    test_client, db_path = client
    proj_id = "test-api-gap-valid"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Valid", description=""))

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "evidence", "title": "T", "rationale": "R", "researcher_id": "r"},
    )
    assert res.status_code == 400
    assert "Invalid research gap type" in res.json()["detail"]

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "T", "rationale": "  ", "researcher_id": "r"},
    )
    assert res.status_code == 400


def test_create_gap_missing_project(client):
    test_client, _ = client
    res = test_client.post(
        "/projects/missing/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "T", "rationale": "R", "researcher_id": "r"},
    )
    assert res.status_code == 404


def test_update_and_delete_gap(client):
    test_client, db_path = client
    proj_id = "test-api-gap-upd"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Upd", description=""))

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "contextual", "title": "Old", "rationale": "Old rationale", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.put(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}",
        json={"gap_type": "mechanism", "title": "New", "rationale": "New rationale"},
    )
    assert res.status_code == 200
    assert res.json()["gap_type"] == "mechanism"
    assert res.json()["title"] == "New"

    res = test_client.delete(f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 204

    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 404


def test_link_evidence_flow(client):
    test_client, db_path = client
    proj_id = "test-api-gap-link"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Link", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "analytical_relation", "target_id": str(seeded["relation_id"])},
    )
    assert res.status_code == 201
    link = res.json()
    assert link["link_type"] == "analytical_relation"
    assert link["target_id"] == str(seeded["relation_id"])
    assert link["group_item_id"] == str(seeded["group_item_id"])
    assert link["latest_revision_id"] == str(seeded["rev_id"])

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "mechanism_pathway", "target_id": str(seeded["pathway_id"])},
    )
    assert res.status_code == 201

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "context_factor_link", "target_id": str(seeded["context_link_id"])},
    )
    assert res.status_code == 201

    # Workspace reflects all three links with linked publication count
    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps")
    assert res.status_code == 200
    data = res.json()
    assert len(data["gaps"]) == 1
    assert len(data["gaps"][0]["links"]) == 3
    assert data["stats"]["linked_publication_count"] == 1

    # Unlink one
    link_id = data["gaps"][0]["links"][0]["link_id"]
    res = test_client.delete(f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links/{link_id}")
    assert res.status_code == 204

    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps")
    assert len(res.json()["gaps"][0]["links"]) == 2


def test_link_evidence_rejects_stale_evidence(client):
    test_client, db_path = client
    proj_id = "test-api-gap-stale"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Stale", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    # New COMPLETE revision that removes the group item -> relation is stale
    ext_repo = SqliteExtractionRepository(db_path)
    rec = ext_repo.list_records(proj_id)[0]
    ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=seeded["pub_id"],
            revision_index=2,
            reviewer_id="reviewer_1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[],
            created_at=datetime.now(timezone.utc),
        )
    )

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "analytical_relation", "target_id": str(seeded["relation_id"])},
    )
    assert res.status_code == 400
    assert "not traceable" in res.json()["detail"]


def test_link_evidence_rejects_missing_gap_and_target(client):
    test_client, db_path = client
    proj_id = "test-api-gap-missing"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Missing", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{uuid4()}/links",
        json={"link_type": "analytical_relation", "target_id": str(seeded["relation_id"])},
    )
    assert res.status_code == 404

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "analytical_relation", "target_id": str(uuid4())},
    )
    assert res.status_code == 400
    assert "not found" in res.json()["detail"]


def test_evidence_candidates_endpoint(client):
    test_client, db_path = client
    proj_id = "test-api-gap-candidates"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Candidates", description=""))
    _seed_evidence(db_path, proj_id)

    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps/evidence-candidates")
    assert res.status_code == 200
    candidates = res.json()
    link_types = {c["link_type"] for c in candidates}
    assert link_types == {"analytical_relation", "mechanism_pathway", "context_factor_link"}
    assert all(c["traceable"] for c in candidates)
    assert all(c["label"] for c in candidates)


def test_delete_gap_preserves_evidence(client):
    test_client, db_path = client
    proj_id = "test-api-gap-preserve"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Preserve", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]
    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "analytical_relation", "target_id": str(seeded["relation_id"])},
    )
    assert res.status_code == 201

    res = test_client.delete(f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 204

    # Underlying mechanism pathway still present in mechanism workspace
    res = test_client.get(f"/projects/{proj_id}/synthesis/mechanisms")
    assert res.status_code == 200
    assert res.json()["stats"]["total_pathways"] == 1


def test_project_isolation(client):
    test_client, db_path = client
    proj_a = "test-api-gap-proj-a"
    proj_b = "test-api-gap-proj-b"
    repo = SqliteProjectRepository(db_path)
    repo.create(Project(project_id=proj_a, title="A", description=""))
    repo.create(Project(project_id=proj_b, title="B", description=""))

    res = test_client.post(
        f"/projects/{proj_a}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.get(f"/projects/{proj_b}/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 404

    res = test_client.get(f"/projects/{proj_b}/synthesis/research-gaps")
    assert res.json()["gaps"] == []


def test_workspace_stats_counts(client):
    test_client, db_path = client
    proj_id = "test-api-gap-stats"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Stats", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    thematic_gap_ids: list[str] = []
    for gap_type in ["thematic", "thematic", "inconsistent_evidence"]:
        res = test_client.post(
            f"/projects/{proj_id}/synthesis/research-gaps",
            json={"gap_type": gap_type, "title": f"Gap {gap_type}", "rationale": "Justification.", "researcher_id": "r"},
        )
        assert res.status_code == 201
        if gap_type == "thematic":
            thematic_gap_ids.append(res.json()["gap_id"])

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{thematic_gap_ids[0]}/links",
        json={"link_type": "analytical_relation", "target_id": str(seeded["relation_id"])},
    )
    assert res.status_code == 201

    data = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps").json()
    assert data["stats"]["total_gaps"] == 3
    assert data["stats"]["thematic_count"] == 2
    assert data["stats"]["inconsistent_evidence_count"] == 1
    assert data["stats"]["linked_publication_count"] == 1


def test_update_preserves_evidence_links_and_metadata(client):
    """Adversarial: editing a gap must never wipe its evidence links or author attribution."""
    test_client, db_path = client
    proj_id = "test-api-gap-upd-preserve"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="Preserve", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "lead"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "analytical_relation", "target_id": str(seeded["relation_id"])},
    )
    assert res.status_code == 201

    res = test_client.put(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}",
        json={"gap_type": "contextual", "title": "Renamed", "rationale": "New rationale"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Renamed"
    assert body["researcher_id"] == "lead"

    res = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 200
    detail = res.json()
    assert len(detail["links"]) == 1
    assert detail["links"][0]["link_type"] == "analytical_relation"
    assert detail["links"][0]["latest_revision_id"] == str(seeded["rev_id"])


def test_wrong_project_update_delete_rejected(client):
    """Adversarial: cannot update or delete another project's gap (project isolation)."""
    test_client, db_path = client
    repo = SqliteProjectRepository(db_path)
    repo.create(Project(project_id="test-api-gap-iso-a", title="A", description=""))
    repo.create(Project(project_id="test-api-gap-iso-b", title="B", description=""))

    res = test_client.post(
        "/projects/test-api-gap-iso-a/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]

    res = test_client.put(
        f"/projects/test-api-gap-iso-b/synthesis/research-gaps/{gap_id}",
        json={"title": "Hijacked"},
    )
    assert res.status_code == 404

    res = test_client.delete(f"/projects/test-api-gap-iso-b/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 404

    res = test_client.get(f"/projects/test-api-gap-iso-a/synthesis/research-gaps/{gap_id}")
    assert res.status_code == 200
    assert res.json()["gap"]["title"] == "Gap"


def test_no_gap_score_fields_in_api_response(client):
    """Adversarial: the API must never expose any gap score/priority/strength field."""
    test_client, db_path = client
    proj_id = "test-api-gap-no-score"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="NoScore", description=""))
    seeded = _seed_evidence(db_path, proj_id)

    res = test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps",
        json={"gap_type": "thematic", "title": "Gap", "rationale": "Justification.", "researcher_id": "r"},
    )
    gap_id = res.json()["gap_id"]
    test_client.post(
        f"/projects/{proj_id}/synthesis/research-gaps/{gap_id}/links",
        json={"link_type": "mechanism_pathway", "target_id": str(seeded["pathway_id"])},
    )

    forbidden = {"gap_strength", "gap_score", "confidence_score", "priority_score", "evidence_quality_score"}

    workspace = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps").json()
    for gap_detail in workspace["gaps"]:
        assert forbidden.isdisjoint(gap_detail["gap"].keys())
        for link in gap_detail["links"]:
            assert forbidden.isdisjoint(link.keys())
    assert forbidden.isdisjoint(workspace["stats"].keys())

    candidates = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps/evidence-candidates").json()
    for candidate in candidates:
        assert forbidden.isdisjoint(candidate.keys())


def test_candidate_exposes_criterion_level_qa_via_api(client):
    """API must expose criterion-level QA on candidates, and only that (no aggregate score/tier/confidence)."""
    test_client, db_path = client
    proj_id = "test-api-qa-profile"
    SqliteProjectRepository(db_path).create(Project(project_id=proj_id, title="QA", description=""))
    seeded = _seed_evidence(db_path, proj_id)

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
                    criterion_id=crit1, template_id=tid, display_order=1,
                    question="Is the study design clearly described?",
                ),
                QualityAssessmentTemplateCriterion(
                    criterion_id=crit2, template_id=tid, display_order=2,
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
            publication_id=seeded["pub_id"],
            template_id=tid,
            reviewer_id="lead_reviewer",
            responses=[
                QualityAssessmentResponse(
                    assessment_id=ass_id, criterion_id=crit1,
                    question_snapshot="Is the study design clearly described?",
                    response_value=QualityAssessmentResponseValue.YES,
                    justification="Detailed methodology provided in section 3.",
                ),
                QualityAssessmentResponse(
                    assessment_id=ass_id, criterion_id=crit2,
                    question_snapshot="Are energy measurements metered directly?",
                    response_value=QualityAssessmentResponseValue.NO,
                    justification="Values estimated from machine specifications.",
                ),
            ],
        )
    )

    candidates = test_client.get(f"/projects/{proj_id}/synthesis/research-gaps/evidence-candidates").json()
    with_qa = [c for c in candidates if c["publication_id"] == str(seeded["pub_id"])]
    assert with_qa
    qa = with_qa[0]["qa_profile"]
    assert qa is not None
    assert qa["reviewer_id"] == "lead_reviewer"
    assert {c["question_text"] for c in qa["criteria_assessments"]} == {
        "Is the study design clearly described?",
        "Are energy measurements metered directly?",
    }
    responses = {c["question_text"]: c["response_value"] for c in qa["criteria_assessments"]}
    assert responses["Is the study design clearly described?"] == "YES"
    assert responses["Are energy measurements metered directly?"] == "NO"
    assert all("justification" in c for c in qa["criteria_assessments"])

    forbidden_qa = {"score", "aggregate_score", "quality_tier", "confidence", "confidence_score", "weighting"}
    assert forbidden_qa.isdisjoint(qa.keys())
    for criterion in qa["criteria_assessments"]:
        assert forbidden_qa.isdisjoint(criterion.keys())
