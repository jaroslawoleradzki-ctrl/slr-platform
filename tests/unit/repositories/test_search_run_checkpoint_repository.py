from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.repositories.search_run_checkpoint_repository import (
    SearchRunCheckpoint,
    SqliteSearchRunCheckpointRepository,
)


def _make_checkpoint(
    *,
    search_run_id: UUID | None = None,
    project_id: str = "test_proj",
    job_id: UUID | None = None,
    provider: str = "openalex",
    cursor: str | None = "cur_1",
    status: str = "partial",
    resumable: bool = True,
    updated_at: datetime | None = None,
) -> SearchRunCheckpoint:
    now = updated_at or datetime.now(timezone.utc)
    return SearchRunCheckpoint(
        search_run_id=search_run_id or uuid4(),
        project_id=project_id,
        job_id=job_id or uuid4(),
        provider=provider,
        cursor=cursor,
        pages_fetched=1,
        fetched_count=10,
        canonical_accepted_count=8,
        canonical_rejected_count=2,
        canonical_indeterminate_count=0,
        deduplicated_count=1,
        status=status,
        resumable=resumable,
        plan_metadata={"strategy": {"providers": [provider]}},
        warnings=("Test warning",),
        created_at=now,
        updated_at=now,
    )


def test_save_and_get_checkpoint(tmp_path: Path) -> None:
    repo = SqliteSearchRunCheckpointRepository(tmp_path / "checkpoints.db")
    cp = _make_checkpoint()
    repo.save_checkpoint(cp)

    loaded = repo.get_checkpoint(cp.search_run_id)
    assert loaded is not None
    assert loaded.search_run_id == cp.search_run_id
    assert loaded.project_id == cp.project_id
    assert loaded.job_id == cp.job_id
    assert loaded.provider == "openalex"
    assert loaded.cursor == "cur_1"
    assert loaded.pages_fetched == 1
    assert loaded.fetched_count == 10
    assert loaded.canonical_accepted_count == 8
    assert loaded.resumable is True
    assert loaded.plan_metadata == {"strategy": {"providers": ["openalex"]}}
    assert loaded.warnings == ("Test warning",)


def test_upsert_updates_job_id_and_cursor(tmp_path: Path) -> None:
    repo = SqliteSearchRunCheckpointRepository(tmp_path / "checkpoints.db")
    run_id = uuid4()
    job1_id = uuid4()
    job2_id = uuid4()

    cp1 = _make_checkpoint(search_run_id=run_id, job_id=job1_id, cursor="c1")
    repo.save_checkpoint(cp1)

    # Re-save with new job_id and cursor
    cp2 = _make_checkpoint(search_run_id=run_id, job_id=job2_id, cursor="c2", status="complete", resumable=False)
    repo.save_checkpoint(cp2)

    loaded = repo.get_checkpoint(run_id)
    assert loaded is not None
    assert loaded.job_id == job2_id
    assert loaded.cursor == "c2"
    assert loaded.status == "complete"
    assert loaded.resumable is False

    # get_checkpoints_for_job finds by job2_id
    job2_cps = repo.get_checkpoints_for_job(job2_id)
    assert len(job2_cps) == 1
    assert job2_cps[0].search_run_id == run_id

    # job1_id returns empty
    assert repo.get_checkpoints_for_job(job1_id) == []


def test_get_latest_job_checkpoints_groups_by_job(tmp_path: Path) -> None:
    repo = SqliteSearchRunCheckpointRepository(tmp_path / "checkpoints.db")
    project_id = "proj_latest"
    job1_id = uuid4()
    job2_id = uuid4()

    # Job 1 with 2 providers at time T1
    t1 = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    cp1_a = _make_checkpoint(project_id=project_id, job_id=job1_id, provider="openalex", updated_at=t1)
    cp1_b = _make_checkpoint(project_id=project_id, job_id=job1_id, provider="crossref", updated_at=t1)
    repo.save_checkpoint(cp1_a)
    repo.save_checkpoint(cp1_b)

    # Job 2 with 2 providers at time T2 > T1
    t2 = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    cp2_a = _make_checkpoint(project_id=project_id, job_id=job2_id, provider="openalex", updated_at=t2)
    cp2_b = _make_checkpoint(project_id=project_id, job_id=job2_id, provider="crossref", updated_at=t2)
    repo.save_checkpoint(cp2_a)
    repo.save_checkpoint(cp2_b)

    latest = repo.get_latest_job_checkpoints(project_id)
    assert len(latest) == 2
    assert all(cp.job_id == job2_id for cp in latest)


def test_delete_for_project(tmp_path: Path) -> None:
    repo = SqliteSearchRunCheckpointRepository(tmp_path / "checkpoints.db")
    cp_a = _make_checkpoint(project_id="proj_a")
    cp_b = _make_checkpoint(project_id="proj_b")
    repo.save_checkpoint(cp_a)
    repo.save_checkpoint(cp_b)

    repo.delete_for_project("proj_a")
    assert repo.get_checkpoint(cp_a.search_run_id) is None
    assert repo.get_checkpoint(cp_b.search_run_id) is not None
