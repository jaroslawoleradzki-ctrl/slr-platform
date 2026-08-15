"""Unit tests for SynthesisMatrixService: aggregation, matrix generation, unit conversions, and traceability."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

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
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
)
from app.services.synthesis_classification_service import (
    SynthesisClassificationService,
)
from app.services.synthesis_matrix_service import (
    SynthesisMatrixService,
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
def service_env(tmp_path: Path):
    db_path = tmp_path / "test_matrix_service.db"
    _apply_migrations_up_to(db_path, "0021_analytical_relations.sql")

    project_repo = SqliteProjectRepository(db_path)
    extraction_repo = SqliteExtractionRepository(db_path)
    classification_repo = SqliteSynthesisClassificationRepository(db_path)
    matrix_repo = SqliteSynthesisMatrixRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    template_repo = SqliteExtractionTemplateRepository(db_path)

    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    class_service = SynthesisClassificationService(
        classification_repo=classification_repo,
        extraction_repo=extraction_repo,
        project_repo=project_repo,
    )

    # Setup projects
    project_repo.create(Project(project_id="proj_alpha", title="Project Alpha", description=""))
    project_repo.create(Project(project_id="proj_beta", title="Project Beta", description=""))

    service = SynthesisMatrixService(
        matrix_repo=matrix_repo,
        classification_repo=classification_repo,
        extraction_repo=extraction_repo,
        project_repo=project_repo,
        qa_repo=qa_repo,
        publication_repo=pub_repo,
    )

    return {
        "service": service,
        "class_service": class_service,
        "project_repo": project_repo,
        "extraction_repo": extraction_repo,
        "classification_repo": classification_repo,
        "matrix_repo": matrix_repo,
        "qa_repo": qa_repo,
        "pub_repo": pub_repo,
        "db_path": db_path,
    }


def _create_sample_group_item(
    group_item_id,
    item_index,
    practice_text,
    effect_text,
    magnitude=None,
    unit=None,
    direction="positive",
    evidence_character="empirical",
    quote=None,
):
    values = [
        ExtractedValueState(
            field_key="lean_practice",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value=practice_text,
            source_quote=quote,
        ),
        ExtractedValueState(
            field_key="energy_effect_indicator",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value=effect_text,
        ),
        ExtractedValueState(
            field_key="evidence_character",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value=evidence_character,
        ),
        ExtractedValueState(
            field_key="direction",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value=direction,
        ),
    ]
    if magnitude is not None:
        values.append(
            ExtractedValueState(
                field_key="effect_magnitude",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                float_value=float(magnitude),
                unit_value=unit,
            )
        )
    return ExtractedGroupItemState(
        group_item_id=group_item_id,
        group_key="lean_energy_relationships",
        item_index=item_index,
        values=values,
    )


def _save_sample_revision(
    extraction_repo: SqliteExtractionRepository,
    proj_id: str,
    pub_id,
    group_items,
    reviewer_id: str = "reviewer_1",
) -> ExtractionRevision:
    records = extraction_repo.list_records(proj_id)
    rec = next((r for r in records if r.publication_id == pub_id), None)
    if not rec:
        rec = extraction_repo.create_record(
            ExtractionRecord(
                project_id=proj_id,
                publication_id=pub_id,
                template_id="lean_energy",
                template_version="1.0.0",
            )
        )
    latest_rev = extraction_repo.get_latest_revision(proj_id, pub_id)
    idx = (latest_rev.revision_index + 1) if latest_rev else 1
    rev = ExtractionRevision(
        record_id=rec.record_id,
        project_id=proj_id,
        publication_id=pub_id,
        revision_index=idx,
        reviewer_id=reviewer_id,
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        group_items=group_items,
    )
    extraction_repo.append_revision(rev)
    return rev


def test_matrix_aggregation_and_counts(service_env):
    """Verifies:
    - 1 pub with multiple relations in same cell -> relation_count > publication_count
    - multiple pubs in same cell -> distinct publication_count
    - mixed directions & evidence character distributions
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    # Define categories
    class_service.create_lean_category(project_id=proj_id, category_id="vsm", name="Value Stream Mapping", display_order=1)
    class_service.create_lean_category(project_id=proj_id, category_id="tpm", name="Total Productive Maintenance", display_order=2)

    class_service.create_energy_category(project_id=proj_id, category_id="elec", name="Electricity", display_order=1)
    class_service.create_energy_category(project_id=proj_id, category_id="fuel", name="Fuel / Thermal", display_order=2)

    # Set and approve term mappings
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Energy VSM", "vsm")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Energy VSM", "rev-1")

    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "elec")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "rev-1")

    # Create Publication 1 with TWO relations in (vsm, elec)
    pub1_id = uuid4()
    pub_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub1_id,
                title="Study 1: Energy VSM in Foundry",
                publication_year=2023,
            )
        ],
    )

    g1_id = uuid4()
    g2_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub1_id,
        [
            _create_sample_group_item(g1_id, 1, "Energy VSM", "Electricity Consumption", 15.0, "kWh", "positive", "empirical", "Reduced 15 kWh"),
            _create_sample_group_item(g2_id, 2, "Energy VSM", "Electricity Consumption", None, None, "no_effect", "qualitative", "No change observed"),
        ],
    )

    # Create Publication 2 with ONE relation in (vsm, elec)
    pub2_id = uuid4()
    pub_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub2_id,
                title="Study 2: VSM in Plastics",
                publication_year=2024,
            )
        ],
    )
    g3_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub2_id,
        [
            _create_sample_group_item(g3_id, 1, "Energy VSM", "Electricity Consumption", 10.0, "MJ", "negative", "estimated", "Increased 10 MJ"),
        ],
        reviewer_id="reviewer_2",
    )

    # Calculate matrix
    matrix = service.get_matrix(proj_id)

    assert matrix.project_id == proj_id
    assert len(matrix.lean_categories) == 2
    assert len(matrix.energy_categories) == 2
    assert matrix.total_relations == 3
    assert matrix.total_publications == 2
    assert matrix.unclassified_relations_count == 0

    # Locate cell (vsm, elec)
    target_cell = next(c for c in matrix.cells if c.lean_category_id == "vsm" and c.energy_category_id == "elec")
    assert target_cell.relation_count == 3
    assert target_cell.publication_count == 2  # 3 relations from 2 distinct studies!
    assert target_cell.relation_count > target_cell.publication_count

    # Check direction distribution
    assert target_cell.direction_distribution == {
        "positive": 1,
        "no_effect": 1,
        "negative": 1,
    }

    # Check evidence character distribution
    assert target_cell.evidence_character_distribution == {
        "empirical": 1,
        "qualitative": 1,
        "estimated": 1,
    }


def test_unclassified_relations_remain_explicit_and_not_silently_assigned(service_env):
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(project_id=proj_id, category_id="vsm", name="VSM")
    class_service.create_energy_category(project_id=proj_id, category_id="elec", name="Electricity")

    # Add revision with UNMAPPED terms
    pub_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(uuid4(), 1, "Unmapped Practice X", "Unmapped Effect Y"),
        ],
    )

    matrix = service.get_matrix(proj_id)
    assert matrix.total_relations == 1
    assert matrix.unclassified_relations_count == 1

    # Cells must all have relation_count = 0
    for cell in matrix.cells:
        assert cell.relation_count == 0


def test_source_evidence_immutability_and_category_remapping(service_env):
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(project_id=proj_id, category_id="c1", name="Category 1")
    class_service.create_lean_category(project_id=proj_id, category_id="c2", name="Category 2")
    class_service.create_energy_category(project_id=proj_id, category_id="e1", name="Energy 1")

    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kaizen Event", "c1")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kaizen Event", "lead")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Fuel Reduction", "e1")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Fuel Reduction", "lead")

    pub_id = uuid4()
    g_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(g_id, 1, "Kaizen Event", "Fuel Reduction", 50.0, "GJ"),
        ],
    )

    # Initial matrix: relation is in (c1, e1)
    m1 = service.get_matrix(proj_id)
    c1_cell = next(c for c in m1.cells if c.lean_category_id == "c1" and c.energy_category_id == "e1")
    assert c1_cell.relation_count == 1

    # Remap Kaizen Event to c2 and approve
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kaizen Event", "c2")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kaizen Event", "lead")

    # Updated matrix: relation moves to (c2, e1)
    m2 = service.get_matrix(proj_id)
    c1_cell_updated = next(c for c in m2.cells if c.lean_category_id == "c1" and c.energy_category_id == "e1")
    c2_cell_updated = next(c for c in m2.cells if c.lean_category_id == "c2" and c.energy_category_id == "e1")
    assert c1_cell_updated.relation_count == 0
    assert c2_cell_updated.relation_count == 1

    # Verify Phase 9 extraction record was NEVER mutated
    latest_rev = extraction_repo.get_latest_revision(proj_id, pub_id)
    assert latest_rev is not None
    practice_val = next(v for v in latest_rev.group_items[0].values if v.field_key == "lean_practice")
    assert practice_val.text_value == "Kaizen Event"


def test_hybrid_unit_conversion_preview_and_explicit_save(service_env):
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(project_id=proj_id, category_id="smed", name="SMED")
    class_service.create_energy_category(project_id=proj_id, category_id="elec", name="Electricity")
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "SMED Setup", "smed")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "elec")

    pub_id = uuid4()
    g_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(g_id, 1, "SMED Setup", "Electricity Consumption", 25.0, "kWh"),
        ],
    )

    # Sync relations
    rels = service.synchronize_analytical_relations(proj_id)
    rel = rels[0]

    # 1. Preview conversion (does NOT save)
    preview = service.calculate_unit_conversion(proj_id, rel.relation_id, "MJ")
    assert pytest.approx(preview.transformed_value, 1e-6) == 90.0
    assert preview.transformed_unit == "MJ"
    assert "3.6" in preview.conversion_rule

    # Verify not yet saved in relation
    rel_unmodified = service._matrix_repo.get_analytical_relation(proj_id, rel.relation_id)
    assert rel_unmodified.converted_value is None

    # 2. Explicitly save converted value
    updated_rel = service.save_converted_value(proj_id, rel.relation_id, "MJ")
    assert updated_rel.converted_value is not None
    assert pytest.approx(updated_rel.converted_value.transformed_value, 1e-6) == 90.0
    assert updated_rel.converted_value.transformed_unit == "MJ"

    # Source magnitude remains immutable
    assert updated_rel.magnitude == 25.0
    assert updated_rel.original_unit == "kWh"


def test_cross_project_isolation(service_env):
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]

    class_service.create_lean_category(project_id="proj_alpha", category_id="cat_a", name="Cat A")
    class_service.create_energy_category(project_id="proj_alpha", category_id="elec_a", name="Elec A")
    class_service.set_term_mapping("proj_alpha", TermType.LEAN_PRACTICE, "Practice A", "cat_a")
    class_service.set_term_mapping("proj_alpha", TermType.ENERGY_EFFECT, "Effect A", "elec_a")

    pub_a = uuid4()
    _save_sample_revision(
        extraction_repo,
        "proj_alpha",
        pub_a,
        [_create_sample_group_item(uuid4(), 1, "Practice A", "Effect A")],
    )

    # Proj Beta should not see Proj Alpha's relations
    matrix_beta = service.get_matrix("proj_beta")
    assert matrix_beta.total_relations == 0
    assert len(matrix_beta.cells) == 0


def test_traceability_from_cell_to_publication_and_qa_overlay(service_env):
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    qa_repo = service_env["qa_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(project_id=proj_id, category_id="kanban", name="Kanban")
    class_service.create_energy_category(project_id=proj_id, category_id="elec", name="Electricity")
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kanban Cards", "kanban")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kanban Cards", "lead")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "elec")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "lead")

    pub_id = uuid4()
    pub_repo.add_publications(
        proj_id,
        [
            Publication(
                record_id=pub_id,
                title="Kanban in Electronics Assembly",
                publication_year=2022,
            )
        ],
    )

    g_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(
                g_id, 1, "Kanban Cards", "Electricity Consumption", 5.0, "kWh", "positive", "empirical", "Reduced energy by 5 kWh per board"
            ),
        ],
    )

    # Add Phase 8 QA assessment
    crit_id1 = uuid4()
    crit_id2 = uuid4()
    ass_id = uuid4()
    tid = uuid4()

    catalog_repo = SqliteQualityAssessmentCatalogRepository(service_env["db_path"])
    try:
        catalog_repo.create_tool(QualityAssessmentTool(tool_id="casp_tool", name="CASP Tool"))
    except Exception:
        pass

    template = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_tool",
        template_key="lean_qa",
        name="Lean QA Template",
        version=1,
        is_active=True,
        criteria=[
            QualityAssessmentTemplateCriterion(
                criterion_id=crit_id1,
                template_id=tid,
                display_order=1,
                question="Is the study design clearly described?",
            ),
            QualityAssessmentTemplateCriterion(
                criterion_id=crit_id2,
                template_id=tid,
                display_order=2,
                question="Are energy measurements metered directly?",
            ),
        ],
    )
    catalog_repo.create_template_version(template)

    qa_assessment = QualityAssessment(
        assessment_id=ass_id,
        project_id=proj_id,
        publication_id=pub_id,
        template_id=tid,
        reviewer_id="lead_reviewer",
        responses=[
            QualityAssessmentResponse(
                assessment_id=ass_id,
                criterion_id=crit_id1,
                question_snapshot="Is the study design clearly described?",
                response_value=QualityAssessmentResponseValue.YES,
                justification="Detailed methodology provided in section 3.",
            ),
            QualityAssessmentResponse(
                assessment_id=ass_id,
                criterion_id=crit_id2,
                question_snapshot="Are energy measurements metered directly?",
                response_value=QualityAssessmentResponseValue.NO,
                justification="Values estimated from machine specifications.",
            ),
        ],
    )
    qa_repo.save_assessment(qa_assessment)

    # Retrieve cell detail
    detail = service.get_matrix_cell_detail(proj_id, "kanban", "elec")

    assert detail.relation_count == 1
    assert detail.publication_count == 1
    assert len(detail.relations) == 1

    rel_detail = detail.relations[0]
    assert rel_detail.publication_title == "Kanban in Electronics Assembly"
    assert rel_detail.publication_year == 2022
    assert rel_detail.source_quote == "Reduced energy by 5 kWh per board"

    # Check QA overlay
    assert rel_detail.qa_profile is not None
    assert len(rel_detail.qa_profile.criteria_assessments) == 2
    qa_answers = {c.question_text: c.response_value for c in rel_detail.qa_profile.criteria_assessments}
    assert qa_answers["Is the study design clearly described?"].upper() == "YES"
    assert qa_answers["Are energy measurements metered directly?"].upper() == "NO"

    # Verify durable group_item_id
    assert rel_detail.relation.group_item_id == g_id


def test_analytical_relation_identity_preservation_across_revisions(service_env):
    """Verifies:
    - logical identity = group_item_id
    - specific evidence occurrence = revision_id + group_item_id
    - Revision 1: relation A = group_item_id X, item_index 1
    - Revision 2: same relation A = group_item_id X, item_index 4
    - item_index is NEVER used as logical identity.
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    matrix_repo = service_env["matrix_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(proj_id, "tpm", "TPM")
    class_service.create_energy_category(proj_id, "elec", "Electricity")
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "TPM Maintenance", "tpm")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "TPM Maintenance", "rev_1")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "elec")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "rev_1")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="TPM Study", publication_year=2024)])

    group_item_x = uuid4()
    # Revision 1: relation A at item_index 1
    rev1 = _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(group_item_x, 1, "TPM Maintenance", "Electricity Consumption", 10.0, "kWh"),
        ],
    )

    service.synchronize_analytical_relations(proj_id)
    rel_v1 = matrix_repo.get_analytical_relation_by_group_item(proj_id, group_item_x)
    assert rel_v1 is not None
    assert rel_v1.group_item_id == group_item_x
    assert rel_v1.latest_revision_id == rev1.revision_id
    assert rel_v1.item_index == 1
    rel_id_original = rel_v1.relation_id

    # Revision 2: same logical relation A now shifted to item_index 4 (e.g. earlier items added)
    other_item_1 = uuid4()
    other_item_2 = uuid4()
    other_item_3 = uuid4()
    rev2 = _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(other_item_1, 1, "Other 1", "Effect 1"),
            _create_sample_group_item(other_item_2, 2, "Other 2", "Effect 2"),
            _create_sample_group_item(other_item_3, 3, "Other 3", "Effect 3"),
            _create_sample_group_item(group_item_x, 4, "TPM Maintenance", "Electricity Consumption", 12.0, "kWh"),
        ],
    )

    service.synchronize_analytical_relations(proj_id)
    rel_v2 = matrix_repo.get_analytical_relation_by_group_item(proj_id, group_item_x)
    assert rel_v2 is not None
    # Logical identity preserved
    assert rel_v2.relation_id == rel_id_original
    assert rel_v2.group_item_id == group_item_x
    # Updated occurrence
    assert rel_v2.latest_revision_id == rev2.revision_id
    assert rel_v2.item_index == 4
    assert rel_v2.magnitude == 12.0


def test_matrix_count_semantics_single_pub_five_relations(service_env):
    """A. ONE PUBLICATION WITH FIVE RELATIONS IN SAME CELL
    Expected: relation_count = 5, publication_count = 1
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(proj_id, "5s", "5S")
    class_service.create_energy_category(proj_id, "elec", "Electricity")
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "5S Step", "5s")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "5S Step", "rev_1")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "elec")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "rev_1")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="5S Multi-Cell Study", publication_year=2024)])

    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(uuid4(), 1, "5S Step", "Electricity Consumption", 1.0, "kWh"),
            _create_sample_group_item(uuid4(), 2, "5S Step", "Electricity Consumption", 2.0, "kWh"),
            _create_sample_group_item(uuid4(), 3, "5S Step", "Electricity Consumption", 3.0, "kWh"),
            _create_sample_group_item(uuid4(), 4, "5S Step", "Electricity Consumption", 4.0, "kWh"),
            _create_sample_group_item(uuid4(), 5, "5S Step", "Electricity Consumption", 5.0, "kWh"),
        ],
    )

    matrix = service.get_matrix(proj_id)
    cell = next(c for c in matrix.cells if c.lean_category_id == "5s" and c.energy_category_id == "elec")
    assert cell.relation_count == 5
    assert cell.publication_count == 1
    assert matrix.total_relations == 5
    assert matrix.total_publications == 1


def test_matrix_count_semantics_duplicate_refresh_idempotency(service_env):
    """C. DUPLICATE MATERIALIZATION / REFRESH
    Refreshing the same Phase 9 evidence must not double-count the same logical relation.
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(proj_id, "kaizen", "Kaizen")
    class_service.create_energy_category(proj_id, "gas", "Natural Gas")
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kaizen Blitz", "kaizen")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Kaizen Blitz", "rev_1")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Gas Reduction", "gas")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Gas Reduction", "rev_1")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Kaizen Study", publication_year=2023)])
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [_create_sample_group_item(uuid4(), 1, "Kaizen Blitz", "Gas Reduction", 20.0, "GJ")],
    )

    # Initial get_matrix
    m1 = service.get_matrix(proj_id)
    assert m1.total_relations == 1

    # Multiple successive synchronizations / get_matrix calls
    service.synchronize_analytical_relations(proj_id)
    service.synchronize_analytical_relations(proj_id)
    m2 = service.get_matrix(proj_id)

    assert m2.total_relations == 1
    cell = next(c for c in m2.cells if c.lean_category_id == "kaizen" and c.energy_category_id == "gas")
    assert cell.relation_count == 1
    assert cell.publication_count == 1


def test_classification_approval_gate_unapproved_vs_approved(service_env):
    """Verifies classification approval gating:
    - unmapped term -> no matrix assignment (unclassified)
    - mapped but unapproved term -> unclassified in matrix cell (approval_state = PENDING)
    - approved Lean + approved Energy -> placed into classified matrix cell
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(proj_id, "smed", "SMED")
    class_service.create_energy_category(proj_id, "elec", "Electricity")

    # Mapped but NOT approved (PENDING)
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Quick Changeover", "smed")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Power Spike", "elec")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="SMED Paper", publication_year=2024)])
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [_create_sample_group_item(uuid4(), 1, "Quick Changeover", "Power Spike", 5.0, "kW")],
    )

    # 1. Before approval: relation is unclassified in matrix
    m_pending = service.get_matrix(proj_id)
    cell_pending = next(c for c in m_pending.cells if c.lean_category_id == "smed" and c.energy_category_id == "elec")
    assert cell_pending.relation_count == 0
    assert m_pending.unclassified_relations_count == 1

    # 2. Approve only Lean mapping (Energy still pending) -> still unclassified
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "Quick Changeover", "lead_rev")
    m_half_approved = service.get_matrix(proj_id)
    cell_half = next(c for c in m_half_approved.cells if c.lean_category_id == "smed" and c.energy_category_id == "elec")
    assert cell_half.relation_count == 0
    assert m_half_approved.unclassified_relations_count == 1

    # 3. Approve Energy mapping -> NOW materialized in classified cell
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Power Spike", "lead_rev")
    m_approved = service.get_matrix(proj_id)
    cell_approved = next(c for c in m_approved.cells if c.lean_category_id == "smed" and c.energy_category_id == "elec")
    assert cell_approved.relation_count == 1
    assert cell_approved.publication_count == 1
    assert m_approved.unclassified_relations_count == 0


def test_source_evidence_byte_for_byte_immutability(service_env):
    """Proves Phase 9 source values remain byte-for-byte unchanged after:
    - classification
    - analytical relation materialization
    - category remapping
    - unit conversion save
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    source_lean_text = "5S"
    source_energy_text = "energy consumption per unit"

    class_service.create_lean_category(proj_id, "cat_5s_a", "5S Category A")
    class_service.create_lean_category(proj_id, "cat_5s_b", "5S Category B")
    class_service.create_energy_category(proj_id, "cat_intensity", "Energy Intensity")

    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, source_lean_text, "cat_5s_a")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, source_lean_text, "rev_1")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, source_energy_text, "cat_intensity")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, source_energy_text, "rev_1")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="5S Study", publication_year=2023)])
    g_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [_create_sample_group_item(g_id, 1, source_lean_text, source_energy_text, 100.0, "kWh")],
    )

    # 1. Materialization
    rels = service.synchronize_analytical_relations(proj_id)
    rel = rels[0]

    # 2. Remapping
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, source_lean_text, "cat_5s_b")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, source_lean_text, "rev_1")
    service.get_matrix(proj_id)

    # 3. Unit conversion save
    service.save_converted_value(proj_id, rel.relation_id, "MJ")

    # Verify Phase 9 extraction record in SQLite is byte-for-byte identical
    latest_rev = extraction_repo.get_latest_revision(proj_id, pub_id)
    assert latest_rev is not None
    item = next(i for i in latest_rev.group_items if i.group_item_id == g_id)
    lean_val = next(v for v in item.values if v.field_key == "lean_practice")
    energy_val = next(v for v in item.values if v.field_key == "energy_effect_indicator")
    mag_val = next(v for v in item.values if v.field_key == "effect_magnitude")

    assert lean_val.text_value == "5S"
    assert energy_val.text_value == "energy consumption per unit"
    assert mag_val.float_value == 100.0
    assert mag_val.unit_value == "kWh"


def test_non_pooling_guardrail_heterogeneous_metrics(service_env):
    """Verifies that matrix cells NEVER compute a pooled numeric magnitude,
    weighted magnitude, or combined effect across heterogeneous metrics.
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(proj_id, "vsm", "VSM")
    class_service.create_energy_category(proj_id, "general_energy", "General Energy")

    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "VSM Mapping", "vsm")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "VSM Mapping", "rev_1")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Energy Metric", "general_energy")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Energy Metric", "rev_1")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="Heterogeneous Study", publication_year=2024)])

    # 4 heterogeneous relations with different metric concepts
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [
            _create_sample_group_item(uuid4(), 1, "VSM Mapping", "Energy Metric", 500.0, "kWh", "positive", "empirical"),
            _create_sample_group_item(uuid4(), 2, "VSM Mapping", "Energy Metric", 2.5, "kWh/unit", "positive", "empirical"),
            _create_sample_group_item(uuid4(), 3, "VSM Mapping", "Energy Metric", 15.0, "MJ/m2", "positive", "estimated"),
            _create_sample_group_item(uuid4(), 4, "VSM Mapping", "Energy Metric", 50.0, "kW", "negative", "qualitative"),
        ],
    )

    matrix = service.get_matrix(proj_id)
    cell = matrix.cells[0]

    # Matrix cell MUST contain counts and distributions only
    assert cell.relation_count == 4
    assert cell.publication_count == 1
    assert cell.direction_distribution == {"positive": 3, "negative": 1}
    assert cell.evidence_character_distribution == {"empirical": 2, "estimated": 1, "qualitative": 1}

    # MatrixCell domain model MUST NOT have any pooled magnitude attributes
    assert not hasattr(cell, "average_magnitude")
    assert not hasattr(cell, "pooled_magnitude")
    assert not hasattr(cell, "weighted_effect")


def test_unit_conversion_boundary_rejection_and_explicit_persistence(service_env):
    """Verifies supported vs. rejected conceptual conversions:
    - Supported: kWh -> MJ, J, kJ, GJ, Wh, MWh
    - Rejected: kWh -> kWh/unit, energy -> efficiency, kW -> kWh
    - Preview is read-only; save requires explicit action.
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]
    proj_id = "proj_alpha"

    class_service.create_lean_category(proj_id, "jit", "JIT")
    class_service.create_energy_category(proj_id, "elec", "Electricity")
    class_service.set_term_mapping(proj_id, TermType.LEAN_PRACTICE, "JIT Flow", "jit")
    class_service.approve_term_mapping(proj_id, TermType.LEAN_PRACTICE, "JIT Flow", "rev_1")
    class_service.set_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "elec")
    class_service.approve_term_mapping(proj_id, TermType.ENERGY_EFFECT, "Electricity Consumption", "rev_1")

    pub_id = uuid4()
    pub_repo.add_publications(proj_id, [Publication(record_id=pub_id, title="JIT Study", publication_year=2024)])
    g_id = uuid4()
    _save_sample_revision(
        extraction_repo,
        proj_id,
        pub_id,
        [_create_sample_group_item(g_id, 1, "JIT Flow", "Electricity Consumption", 50.0, "kWh")],
    )

    rels = service.synchronize_analytical_relations(proj_id)
    rel = rels[0]

    # Rejection of invalid conceptual conversions
    from app.services.synthesis_matrix_service import UnitConversionError

    with pytest.raises(UnitConversionError):
        service.calculate_unit_conversion(proj_id, rel.relation_id, "kWh/unit")

    with pytest.raises(UnitConversionError):
        service.calculate_unit_conversion(proj_id, rel.relation_id, "percent")

    with pytest.raises(UnitConversionError):
        service.calculate_unit_conversion(proj_id, rel.relation_id, "kW")

    # Valid supported conversions
    preview_gj = service.calculate_unit_conversion(proj_id, rel.relation_id, "GJ")
    assert pytest.approx(preview_gj.transformed_value, 1e-6) == 0.18
    assert preview_gj.transformed_unit == "GJ"

    # Preview does NOT modify relation in repository
    unmodified = service._matrix_repo.get_analytical_relation(proj_id, rel.relation_id)
    assert unmodified.converted_value is None

    # Explicit save persists transformed value/unit/rule
    saved = service.save_converted_value(proj_id, rel.relation_id, "GJ")
    assert saved.converted_value is not None
    assert pytest.approx(saved.converted_value.transformed_value, 1e-6) == 0.18
    assert saved.magnitude == 50.0
    assert saved.original_unit == "kWh"


def test_project_isolation_relations_categories_publications(service_env):
    """Proves project isolation across relations, categories, and publications:
    - Project A relation cannot reference Project B category
    - Project A matrix never includes Project B relations
    - Project A cell detail never leaks Project B relations
    """
    service: SynthesisMatrixService = service_env["service"]
    class_service = service_env["class_service"]
    extraction_repo = service_env["extraction_repo"]
    pub_repo = service_env["pub_repo"]

    proj_a = "proj_alpha"
    proj_b = "proj_beta"

    # Setup Project A
    class_service.create_lean_category(proj_a, "cat_5s_a", "5S in A")
    class_service.create_energy_category(proj_a, "cat_elec_a", "Electricity in A")
    class_service.set_term_mapping(proj_a, TermType.LEAN_PRACTICE, "5S Practice", "cat_5s_a")
    class_service.approve_term_mapping(proj_a, TermType.LEAN_PRACTICE, "5S Practice", "rev_a")
    class_service.set_term_mapping(proj_a, TermType.ENERGY_EFFECT, "Energy Use", "cat_elec_a")
    class_service.approve_term_mapping(proj_a, TermType.ENERGY_EFFECT, "Energy Use", "rev_a")

    pub_a = uuid4()
    pub_repo.add_publications(proj_a, [Publication(record_id=pub_a, title="Study A", publication_year=2021)])
    _save_sample_revision(
        extraction_repo,
        proj_a,
        pub_a,
        [_create_sample_group_item(uuid4(), 1, "5S Practice", "Energy Use", 10.0, "kWh")],
    )

    # Setup Project B
    class_service.create_lean_category(proj_b, "cat_tpm_b", "TPM in B")
    class_service.create_energy_category(proj_b, "cat_gas_b", "Gas in B")
    class_service.set_term_mapping(proj_b, TermType.LEAN_PRACTICE, "TPM Action", "cat_tpm_b")
    class_service.approve_term_mapping(proj_b, TermType.LEAN_PRACTICE, "TPM Action", "rev_b")
    class_service.set_term_mapping(proj_b, TermType.ENERGY_EFFECT, "Gas Use", "cat_gas_b")
    class_service.approve_term_mapping(proj_b, TermType.ENERGY_EFFECT, "Gas Use", "rev_b")

    pub_b = uuid4()
    pub_repo.add_publications(proj_b, [Publication(record_id=pub_b, title="Study B", publication_year=2022)])
    _save_sample_revision(
        extraction_repo,
        proj_b,
        pub_b,
        [_create_sample_group_item(uuid4(), 1, "TPM Action", "Gas Use", 50.0, "MJ")],
    )

    # Retrieve matrix for Project A
    matrix_a = service.get_matrix(proj_a)
    assert matrix_a.project_id == proj_a
    assert len(matrix_a.lean_categories) == 1
    assert matrix_a.lean_categories[0].category_id == "cat_5s_a"
    assert len(matrix_a.energy_categories) == 1
    assert matrix_a.energy_categories[0].category_id == "cat_elec_a"
    assert matrix_a.total_relations == 1
    assert matrix_a.total_publications == 1
    assert matrix_a.cells[0].relation_count == 1

    # Retrieve matrix for Project B
    matrix_b = service.get_matrix(proj_b)
    assert matrix_b.project_id == proj_b
    assert len(matrix_b.lean_categories) == 1
    assert matrix_b.lean_categories[0].category_id == "cat_tpm_b"
    assert matrix_b.total_relations == 1
    assert matrix_b.cells[0].relation_count == 1

    # Cell detail from Project A cannot access Project B categories
    from app.services.synthesis_classification_service import CategoryNotFoundError

    with pytest.raises(CategoryNotFoundError):
        service.get_matrix_cell_detail(proj_a, "cat_tpm_b", "cat_gas_b")
