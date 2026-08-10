import pytest

from app.domain.project import Project, ProjectStatus


def test_project_instantiation_valid() -> None:
    proj = Project(
        project_id="lean_energy",
        title="Lean Management Review",
        description="Review of lean management",
        protocol_version="0.6",
    )
    assert proj.project_id == "lean_energy"
    assert proj.title == "Lean Management Review"
    assert proj.status is ProjectStatus.ACTIVE
    assert proj.created_at.tzinfo is not None


def test_project_rejects_blank_fields() -> None:
    with pytest.raises(ValueError, match="text fields must not be blank"):
        Project(project_id="  ", title="Valid Title")

    with pytest.raises(ValueError, match="text fields must not be blank"):
        Project(project_id="p1", title="   ")


def test_project_normalizes_description() -> None:
    proj = Project(project_id="p1", title="T1", description="  Some desc  ")
    assert proj.description == "Some desc"

    proj_empty = Project(project_id="p1", title="T1", description="   ")
    assert proj_empty.description is None
