"""Unit tests for Task 10.3 Matrix and Unit Conversion Domain logic."""

from uuid import uuid4

import pytest

from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    EvidenceCharacter,
    MatrixCell,
    RelationDirection,
    SynthesisMatrix,
    convert_physical_energy_unit,
)


def test_convert_physical_energy_unit_valid_conversions():
    # 1 kWh to MJ: 1 kWh = 3.6 MJ
    val, unit, rule = convert_physical_energy_unit(10.0, "kWh", "MJ")
    assert pytest.approx(val, 1e-6) == 36.0
    assert unit == "MJ"
    assert "3.6" in rule

    # 3.6 MJ to kWh: 3.6 MJ = 1.0 kWh
    val2, unit2, rule2 = convert_physical_energy_unit(36.0, "MJ", "kWh")
    assert pytest.approx(val2, 1e-6) == 10.0
    assert unit2 == "kWh"

    # 1 MWh to GJ: 1 MWh = 3.6 GJ
    val3, unit3, _ = convert_physical_energy_unit(2.5, "MWh", "GJ")
    assert pytest.approx(val3, 1e-6) == 9.0
    assert unit3 == "GJ"

    # 1000 J to kJ
    val4, unit4, _ = convert_physical_energy_unit(5000.0, "J", "kJ")
    assert pytest.approx(val4, 1e-6) == 5.0
    assert unit4 == "kJ"


def test_convert_physical_energy_unit_invalid_and_cross_metric_rejection():
    # Unsupported units
    with pytest.raises(ValueError, match="Unsupported physical energy unit conversion"):
        convert_physical_energy_unit(10.0, "kg", "kWh")

    with pytest.raises(ValueError, match="Unsupported physical energy unit conversion"):
        convert_physical_energy_unit(10.0, "kWh", "percent")

    with pytest.raises(ValueError, match="Unsupported physical energy unit conversion"):
        convert_physical_energy_unit(10.0, "kWh", "kW")  # Power vs Energy without time context


def test_matrix_cell_and_synthesis_matrix_domain_models():
    cell = MatrixCell(
        lean_category_id="5s",
        lean_category_name="5S & Visual Management",
        energy_category_id="elec",
        energy_category_name="Direct Electricity",
        relation_count=5,
        publication_count=2,
        direction_distribution={"positive": 4, "negative": 1},
        evidence_character_distribution={"empirical": 3, "qualitative": 2},
    )
    assert cell.relation_count == 5
    assert cell.publication_count == 2
    assert cell.direction_distribution["positive"] == 4

    matrix = SynthesisMatrix(
        project_id="proj-1",
        cells=[cell],
        total_relations=5,
        total_publications=2,
        unclassified_relations_count=1,
    )
    assert matrix.total_relations == 5
    assert matrix.unclassified_relations_count == 1


def test_analytical_relation_domain_model():
    rel = AnalyticalRelation(
        project_id="proj-1",
        publication_id=uuid4(),
        latest_revision_id=uuid4(),
        group_item_id=uuid4(),
        item_index=1,
        source_practice="5S Visuals",
        analytical_lean_category_id="5s",
        source_effect="12% kWh reduction",
        analytical_energy_category_id="elec",
        direction=RelationDirection.POSITIVE,
        magnitude=12.0,
        original_unit="%",
        converted_value=None,
        evidence_character=EvidenceCharacter.EMPIRICAL,
        approval_state=ClassificationApprovalState.APPROVED,
    )
    assert rel.source_practice == "5S Visuals"
    assert rel.direction == RelationDirection.POSITIVE
    assert rel.approval_state == ClassificationApprovalState.APPROVED
