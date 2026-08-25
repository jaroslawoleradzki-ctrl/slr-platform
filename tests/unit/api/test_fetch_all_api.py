"""API contract tests for the fetch-all endpoints introduced in v0.6.5."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dto.search_strategy import (
    FetchAllStartResponse,
    FetchAllStatusResponse,
    SearchStrategyExecutionResponse,
)
from app.api.main import app
from app.api.routers.search_strategy import (
    get_fetch_all_search_service,
    get_project_publication_repository,
)
from app.repositories.project_publication_repository import (
    DemoProjectPublicationRepository,
    ProjectNotFoundError,
)
from app.services.fetch_all_search import (
    FetchAllJobAlreadyRunningError,
    UnknownFetchAllJobError,
)
from tests.unit.services.test_fetch_all_search import (
    FakeProvider,
    FakeSnapshotRepository,
    _out,
    _publication,
    _strategy,
)


class StubFetchAllService:
    """Deterministic stand-in for router contract tests."""

    def __init__(
        self,
        *,
        running: bool = True,
        fail_start: bool = False,
        status: FetchAllStatusResponse | None = None,
    ) -> None:
        self.running = running
        self.fail_start = fail_start
        self.status = status or FetchAllStatusResponse(
            job_id="job-1",
            project_id="lean_energy",
            status="running" if self.running else "completed",
            started_at=datetime.now(timezone.utc),
            providers=[],
            fetched_total=0,
            kept_total=0,
        )
        self.cancel_requested = False

    def start(self, project_id: str, strategy: Any) -> FetchAllStartResponse:
        if self.fail_start:
            raise FetchAllJobAlreadyRunningError(project_id)
        return FetchAllStartResponse(job_id="job-1", project_id=project_id)

    def get_status(self, job_id: str) -> FetchAllStatusResponse:
        if job_id == "missing":
            raise UnknownFetchAllJobError(job_id)
        return self.status

    def request_cancel(self, job_id: str) -> FetchAllStatusResponse:
        response = self.get_status(job_id)
        self.cancel_requested = True
        return response


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _client_with(
    service: StubFetchAllService,
    *,
    repository: Any | None = None,
) -> TestClient:
    app.dependency_overrides[get_fetch_all_search_service] = lambda: service
    app.dependency_overrides[get_project_publication_repository] = lambda: (
        repository if repository is not None else DemoProjectPublicationRepository()
    )
    return TestClient(app)


_PAYLOAD = {
    "publication_year_from": 2018,
    "publication_year_to": 2026,
    "providers": ["openalex", "crossref"],
    "concept_groups": [{"id": "group-1", "name": "Lean", "terms": ["Kaizen"]}],
}


def test_start_fetch_all_returns_accepted_job_handle() -> None:
    client = _client_with(StubFetchAllService())

    response = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all",
        json=_PAYLOAD,
    )

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["project_id"] == "lean_energy"
    assert body["status"] == "running"


def test_start_fetch_all_conflicts_while_a_job_is_already_running() -> None:
    client = _client_with(StubFetchAllService(fail_start=True))

    response = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all",
        json=_PAYLOAD,
    )

    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_start_fetch_all_returns_404_for_unknown_project() -> None:
    class MissingRepo:
        def get_publications(self, project_id: str) -> list[Any]:
            raise ProjectNotFoundError(project_id)

    client = _client_with(StubFetchAllService(), repository=MissingRepo())

    response = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all",
        json=_PAYLOAD,
    )

    assert response.status_code == 404


def test_fetch_all_status_returns_progress_without_result_while_running() -> None:
    status_response = FetchAllStatusResponse(
        job_id="job-1",
        project_id="lean_energy",
        status="running",
        started_at=datetime.now(timezone.utc),
        providers=[
            {
                "provider": "openalex",
                "status": "running",
                "fetched_count": 120,
                "kept_count": 90,
                "pages_fetched": 2,
                "total_reported": 7574,
                "limit_reached": False,
                "message": None,
            }
        ],
        fetched_total=120,
        kept_total=90,
    )
    client = _client_with(StubFetchAllService(status=status_response))

    response = client.get(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all/job-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["result"] is None
    assert body["providers"][0]["provider"] == "openalex"
    assert body["providers"][0]["kept_count"] == 90


def test_fetch_all_status_returns_404_for_unknown_or_foreign_job() -> None:
    client = _client_with(StubFetchAllService())

    missing = client.get(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all/missing",
    )
    foreign = client.get(
        "/api/v1/projects/other_project/search-strategy/executions/fetch-all/job-1",
    )

    assert missing.status_code == 404
    assert foreign.status_code == 404


def test_cancel_fetch_all_accepts_running_job() -> None:
    service = StubFetchAllService(running=True)
    client = _client_with(service)

    response = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all/job-1/cancel",
    )

    assert response.status_code == 200
    assert service.cancel_requested is True


def test_cancel_fetch_all_rejects_finished_job() -> None:
    finished_status = FetchAllStatusResponse(
        job_id="job-1",
        project_id="lean_energy",
        status="completed",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        providers=[],
        fetched_total=10,
        kept_total=10,
    )
    client = _client_with(StubFetchAllService(status=finished_status))

    response = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all/job-1/cancel",
    )

    assert response.status_code == 409


def test_completed_fetch_all_status_embeds_the_full_result_payload() -> None:
    """Real service driven to completion, then served through the API."""

    provider = FakeProvider(
        "openalex",
        [
            _out([_publication("A1", provider="openalex", source_id="W1")], "cursor-2"),
            _out([_publication("A2", provider="openalex", source_id="W2")], None),
        ],
    )

    async def factory(strategy: Any, http_client: Any) -> list[FakeProvider]:
        return [provider]

    from app.services.fetch_all_search import FetchAllSearchService

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
    )

    async def drive():
        started = service.start("lean_energy", _strategy())
        return await service.wait(started.job_id)

    job = asyncio.run(drive())
    final_status = service.get_status(job.job_id)

    client = _client_with(StubFetchAllService(status=final_status))
    response = client.get(
        "/api/v1/projects/lean_energy/search-strategy/executions/fetch-all/"
        + job.job_id,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    result = body["result"]
    assert result is not None
    assert result["returned_count"] == 2
    assert [record["source_id"] for record in result["results"]] == ["W1", "W2"]
    assert result["provider_errors"] == []
    execution_response = SearchStrategyExecutionResponse.model_validate(result)
    assert execution_response.has_more is False
