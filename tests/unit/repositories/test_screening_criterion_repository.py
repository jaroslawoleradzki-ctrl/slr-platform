from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.screening import (
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
)
from app.repositories.screening_criterion_repository import (
    CriterionNotFoundError,
    SqliteScreeningCriterionRepository,
)


@pytest.fixture
def repo(tmp_path: Path) -> SqliteScreeningCriterionRepository:
    db_path = tmp_path / "test_screening.db"
    return SqliteScreeningCriterionRepository(db_path)


def test_create_and_get_criterion(repo: SqliteScreeningCriterionRepository) -> None:
    criterion = ScreeningCriterion(
        project_id="proj-100",
        name="Study Design",
        description="Must be empirical.",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        display_order=1,
        is_active=True,
        is_required=True,
    )
    created = repo.create(criterion)
    assert created.criterion_id == criterion.criterion_id

    fetched = repo.get(criterion.project_id, criterion.criterion_id)
    assert fetched == criterion


def test_persistence_after_reopen(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test_reopen.db"
    repo1 = SqliteScreeningCriterionRepository(db_path)
    criterion = ScreeningCriterion(
        project_id="proj-reopen",
        name="Persistent Criterion",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
    )
    repo1.create(criterion)

    # Re-instantiate repository pointing to the same SQLite DB file
    repo2 = SqliteScreeningCriterionRepository(db_path)
    fetched = repo2.get("proj-reopen", criterion.criterion_id)
    assert fetched.name == "Persistent Criterion"
    assert fetched.criterion_type == ScreeningCriterionType.EXCLUSION


def test_list_project_criteria(repo: SqliteScreeningCriterionRepository) -> None:
    c1 = ScreeningCriterion(
        project_id="proj-1",
        name="C1",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        display_order=1,
    )
    c2 = ScreeningCriterion(
        project_id="proj-1",
        name="C2",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
        display_order=2,
    )
    repo.create(c1)
    repo.create(c2)

    results = repo.list_by_project("proj-1")
    assert len(results) == 2
    assert [c.criterion_id for c in results] == [c1.criterion_id, c2.criterion_id]


def test_deterministic_ordering_and_tie_break(
    repo: SqliteScreeningCriterionRepository,
) -> None:
    id1 = uuid4()
    id2 = uuid4()

    # Ensure id_low < id_high for tie break testing
    id_low, id_high = (id1, id2) if id1 < id2 else (id2, id1)

    c_high = ScreeningCriterion(
        criterion_id=id_high,
        project_id="proj-order",
        name="High ID Same Order",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        display_order=5,
    )
    c_low = ScreeningCriterion(
        criterion_id=id_low,
        project_id="proj-order",
        name="Low ID Same Order",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        display_order=5,
    )
    c_first = ScreeningCriterion(
        project_id="proj-order",
        name="First Order",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        display_order=1,
    )

    repo.create(c_high)
    repo.create(c_low)
    repo.create(c_first)

    results = repo.list_by_project("proj-order")
    assert [c.criterion_id for c in results] == [
        c_first.criterion_id,
        id_low,
        id_high,
    ]


def test_update_all_editable_attributes(
    repo: SqliteScreeningCriterionRepository,
) -> None:
    original = ScreeningCriterion(
        project_id="proj-update",
        name="Original Name",
        description="Original Desc",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        display_order=0,
        is_active=True,
        is_required=True,
    )
    repo.create(original)

    updated = ScreeningCriterion(
        criterion_id=original.criterion_id,
        project_id=original.project_id,
        name="Updated Name",
        description="Updated Desc",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
        display_order=10,
        is_active=False,
        is_required=False,
    )
    repo.update(updated)

    fetched = repo.get(original.project_id, original.criterion_id)
    assert fetched.name == "Updated Name"
    assert fetched.description == "Updated Desc"
    assert fetched.criterion_type == ScreeningCriterionType.EXCLUSION
    assert fetched.screening_stage == ScreeningCriterionStage.FULL_TEXT
    assert fetched.display_order == 10
    assert fetched.is_active is False
    assert fetched.is_required is False
    assert fetched.criterion_id == original.criterion_id
    assert fetched.project_id == original.project_id


def test_deactivate_criterion(repo: SqliteScreeningCriterionRepository) -> None:
    criterion = ScreeningCriterion(
        project_id="proj-deactivate",
        name="Active Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        is_active=True,
    )
    repo.create(criterion)

    deactivated = repo.deactivate("proj-deactivate", criterion.criterion_id)
    assert deactivated.is_active is False

    fetched = repo.get("proj-deactivate", criterion.criterion_id)
    assert fetched.is_active is False

    # Idempotence: deactivating already inactive criterion does not raise
    deactivated2 = repo.deactivate("proj-deactivate", criterion.criterion_id)
    assert deactivated2.is_active is False


def test_list_active_only_filter(repo: SqliteScreeningCriterionRepository) -> None:
    c_active = ScreeningCriterion(
        project_id="proj-filter",
        name="Active",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
    )
    c_inactive = ScreeningCriterion(
        project_id="proj-filter",
        name="Inactive",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
        is_active=False,
    )
    repo.create(c_active)
    repo.create(c_inactive)

    all_criteria = repo.list_by_project("proj-filter", active_only=False)
    assert len(all_criteria) == 2

    active_criteria = repo.list_by_project("proj-filter", active_only=True)
    assert len(active_criteria) == 1
    assert active_criteria[0].criterion_id == c_active.criterion_id


def test_project_isolation_strict(repo: SqliteScreeningCriterionRepository) -> None:
    c1 = ScreeningCriterion(
        project_id="proj-A",
        name="Criterion Project A",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    c2 = ScreeningCriterion(
        project_id="proj-B",
        name="Criterion Project B",
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
    )
    repo.create(c1)
    repo.create(c2)

    # Project A cannot retrieve Project B's criterion
    with pytest.raises(CriterionNotFoundError):
        repo.get("proj-A", c2.criterion_id)

    # Project A listing only contains c1
    list_a = repo.list_by_project("proj-A")
    assert [c.criterion_id for c in list_a] == [c1.criterion_id]

    # Updating c1 via Project B's project_id raises CriterionNotFoundError
    invalid_cross_update = ScreeningCriterion(
        criterion_id=c1.criterion_id,
        project_id="proj-B",
        name="Malicious Cross Update",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
    )
    with pytest.raises(CriterionNotFoundError):
        repo.update(invalid_cross_update)

    # Deactivating c1 via Project B raises CriterionNotFoundError
    with pytest.raises(CriterionNotFoundError):
        repo.deactivate("proj-B", c1.criterion_id)


def test_nonexistent_criterion_raises_not_found(
    repo: SqliteScreeningCriterionRepository,
) -> None:
    with pytest.raises(CriterionNotFoundError):
        repo.get("proj-1", uuid4())


def test_enum_bool_description_round_trips(
    repo: SqliteScreeningCriterionRepository,
) -> None:
    c_none_desc = ScreeningCriterion(
        project_id="proj-roundtrip",
        name="No Description",
        description=None,
        criterion_type=ScreeningCriterionType.EXCLUSION,
        screening_stage=ScreeningCriterionStage.BOTH,
        is_active=False,
        is_required=True,
    )
    c_str_desc = ScreeningCriterion(
        project_id="proj-roundtrip",
        name="With Description",
        description="Detailed text instruction.",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
        is_active=True,
        is_required=False,
    )
    repo.create(c_none_desc)
    repo.create(c_str_desc)

    f1 = repo.get("proj-roundtrip", c_none_desc.criterion_id)
    assert f1.description is None
    assert f1.criterion_type == ScreeningCriterionType.EXCLUSION
    assert f1.screening_stage == ScreeningCriterionStage.BOTH
    assert f1.is_active is False
    assert f1.is_required is True

    f2 = repo.get("proj-roundtrip", c_str_desc.criterion_id)
    assert f2.description == "Detailed text instruction."
    assert f2.criterion_type == ScreeningCriterionType.INCLUSION
    assert f2.screening_stage == ScreeningCriterionStage.FULL_TEXT
    assert f2.is_active is True
    assert f2.is_required is False
