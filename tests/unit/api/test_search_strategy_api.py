from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.search_strategy import (
    get_live_search_executor,
    get_project_publication_repository,
)
from app.domain.author import Author
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.providers.search.base import ProviderSearchOutput
from app.repositories.project_publication_repository import (
    DemoProjectPublicationRepository,
    ProjectNotFoundError,
)
from app.services.live_search import build_search_query
from app.services.search_engine import SearchEngine


class _Archive:
    async def save(self, entry: object) -> None:
        pass


class _Provider:
    def __init__(
        self,
        name: str,
        publications: list[Publication] | None = None,
        error: Exception | None = None,
        total_count: int | None = None,
        next_cursor: str | None = None,
    ) -> None:
        self.name = name
        self.publications = publications or []
        self.error = error
        self.total_count = total_count
        self.next_cursor = next_cursor
        self.cursors: list[str] = []

    async def search_with_raw(
        self,
        *,
        search_run: object,
        search_query: object,
        cursor: str = "*",
    ) -> ProviderSearchOutput:
        self.cursors.append(cursor)
        if self.error is not None:
            raise self.error
        return ProviderSearchOutput(
            publications=self.publications,
            raw_responses=[],
            total_count=self.total_count,
            next_cursor=self.next_cursor,
            has_more=self.next_cursor is not None,
        )


class _Executor:
    def __init__(
        self,
        providers: list[_Provider],
        *,
        missing_project: bool = False,
    ) -> None:
        self.providers = providers
        self.missing_project = missing_project
        self.cursors: list[str] = []

    async def execute(self, project_id: str, strategy: object) -> object:
        if self.missing_project:
            raise ProjectNotFoundError(project_id)
        return await SearchEngine(
            providers=self.providers,
            raw_response_archive=_Archive(),
        ).execute(build_search_query(strategy), cursor=getattr(strategy, "cursor", None) or "*")


def _publication(
    title: str,
    *,
    provider: str,
    source_id: str,
    year: int = 2024,
) -> Publication:
    return Publication(
        title=title,
        authors=[Author(display_name="Ada Author")],
        publication_year=year,
        provenance=[
            ProvenanceEntry(source=provider, source_record_id=source_id)
        ],
    )


def _payload(providers: list[str] | None = None) -> dict[str, object]:
    return {
        "publication_year_from": 2018,
        "publication_year_to": 2026,
        "providers": providers or ["openalex", "crossref"],
        "concept_groups": [
            {"id": "group-1", "name": "Lean", "terms": ["Kaizen", "Lean"]}
        ],
    }


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _client_with_executor(executor: _Executor) -> TestClient:
    app.dependency_overrides[get_live_search_executor] = lambda: executor
    return TestClient(app)


def test_openalex_and_crossref_success_are_returned_without_deduplication() -> None:
    openalex = _publication(
        "Shared record",
        provider="openalex",
        source_id="https://openalex.org/W1",
    )
    crossref = _publication(
        "Shared record",
        provider="crossref",
        source_id="10.1000/shared",
    )
    client = _client_with_executor(
        _Executor(
            [
                _Provider("openalex", [openalex]),
                _Provider("crossref", [crossref]),
            ]
        )
    )

    response = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert body["returned_count"] == 2
    assert [item["provider"] for item in body["results"]] == [
        "openalex",
        "crossref",
    ]
    assert [item["source_id"] for item in body["results"]] == [
        "https://openalex.org/W1",
        "10.1000/shared",
    ]
    assert body["provider_errors"] == []


@pytest.mark.parametrize(
    ("failed_provider", "successful_provider"),
    [("openalex", "crossref"), ("crossref", "openalex")],
)
def test_one_provider_failure_returns_other_results_and_partial_error(
    failed_provider: str,
    successful_provider: str,
) -> None:
    providers = [
        _Provider(
            name,
            (
                [_publication("Available", provider=name, source_id=f"{name}-1")]
                if name == successful_provider
                else None
            ),
            RuntimeError("provider unavailable") if name == failed_provider else None,
        )
        for name in ("openalex", "crossref")
    ]
    response = _client_with_executor(_Executor(providers)).post(
        "/projects/lean_energy/search-strategy/executions",
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["provider"] for item in body["results"]] == [
        successful_provider
    ]
    assert body["provider_errors"] == [
        {
            "provider": failed_provider,
            "message": "RuntimeError: provider unavailable",
        }
    ]


def test_execution_timestamp_is_real_and_remaining_response_is_stable() -> None:
    publication = _publication(
        "Stable result",
        provider="openalex",
        source_id="W-stable",
    )
    client = _client_with_executor(
        _Executor([_Provider("openalex", [publication])])
    )
    started_at = datetime.now(timezone.utc)
    first = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=_payload(["openalex"]),
    ).json()
    second = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=_payload(["openalex"]),
    ).json()
    finished_at = datetime.now(timezone.utc)
    timestamps = [
        datetime.fromisoformat(first.pop("executed_at")),
        datetime.fromisoformat(second.pop("executed_at")),
    ]

    assert all(started_at <= value <= finished_at for value in timestamps)
    assert first["total_count"] == second["total_count"] == 1
    assert first["returned_count"] == second["returned_count"] == 1
    assert first["rendered_query"] == second["rendered_query"]
    assert first["providers"] == second["providers"] == ["openalex"]
    assert first["results"][0]["title"] == second["results"][0]["title"]
    assert first["results"][0]["source_id"] == second["results"][0]["source_id"]
    assert first["results"][0]["id"] == second["results"][0]["id"]


def test_openalex_metadata_is_exposed_without_confusing_total_and_returned() -> None:
    publications = [
        _publication(
            f"Result {index}",
            provider="openalex",
            source_id=f"W{index}",
        )
        for index in range(2)
    ]
    response = _client_with_executor(
        _Executor(
            [
                _Provider(
                    "openalex",
                    publications,
                    total_count=3560,
                    next_cursor="next-page",
                )
            ]
        )
    ).post(
        "/projects/lean_energy/search-strategy/executions",
        json=_payload(["openalex"]),
    )

    assert response.status_code == 200
    assert response.json()["total_count"] == 3560
    assert response.json()["returned_count"] == 2
    assert response.json()["next_cursor"] == "next-page"
    assert response.json()["has_more"] is True


def test_cursor_is_optional_and_forwarded_to_provider() -> None:
    provider = _Provider(
        "openalex",
        [_publication("Cursor result", provider="openalex", source_id="W-cursor")],
        total_count=2,
        next_cursor="next-next",
    )
    executor = _Executor([provider])
    payload = _payload(["openalex"])
    payload["cursor"] = "next-page"

    response = _client_with_executor(executor).post(
        "/projects/lean_energy/search-strategy/executions",
        json=payload,
    )

    assert response.status_code == 200
    assert provider.cursors == ["next-page"]
    assert response.json()["next_cursor"] == "next-next"
    assert response.json()["has_more"] is True


def test_unknown_project_and_invalid_strategy_are_rejected() -> None:
    client = _client_with_executor(_Executor([], missing_project=True))
    missing = client.post(
        "/projects/not-a-project/search-strategy/executions",
        json=_payload(),
    )
    invalid_payload = _payload()
    invalid_payload["providers"] = []
    invalid = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=invalid_payload,
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422


def _import_record(
    *,
    number: int,
    provider: str = "openalex",
    source_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": f"00000000-0000-0000-0000-{number:012d}",
        "title": f"Selected {number}",
        "authors": ["Ada Author"],
        "year": 2024,
        "provider": provider,
        "source_id": source_id or f"source-{number}",
        "doi": None,
    }


def _client_with_repository(
    repository: DemoProjectPublicationRepository,
) -> TestClient:
    app.dependency_overrides[get_project_publication_repository] = (
        lambda: repository
    )
    return TestClient(app)


def test_first_and_repeated_import_are_idempotent() -> None:
    repository = DemoProjectPublicationRepository()
    client = _client_with_repository(repository)
    record = _import_record(number=1, source_id="W-new")

    first = client.post(
        "/projects/lean_energy/search-results/imports",
        json={"records": [record]},
    )
    repeated = client.post(
        "/projects/lean_energy/search-results/imports",
        json={"records": [record]},
    )

    assert first.json() == {
        "project_id": "lean_energy",
        "imported_count": 1,
        "skipped_count": 0,
        "total_requested": 1,
        "working_collection_count": 6,
    }
    assert repeated.json() == {
        "project_id": "lean_energy",
        "imported_count": 0,
        "skipped_count": 1,
        "total_requested": 1,
        "working_collection_count": 6,
    }


def test_imports_multiple_new_records_and_mixed_new_existing_records() -> None:
    repository = DemoProjectPublicationRepository()
    client = _client_with_repository(repository)
    first = _import_record(number=1)
    second = _import_record(number=2)
    third = _import_record(number=3)

    multiple = client.post(
        "/projects/ai_architecture/search-results/imports",
        json={"records": [first, second]},
    )
    mixed = client.post(
        "/projects/ai_architecture/search-results/imports",
        json={"records": [second, third]},
    )

    assert multiple.json()["imported_count"] == 2
    assert multiple.json()["skipped_count"] == 0
    assert multiple.json()["total_requested"] == 2
    assert multiple.json()["working_collection_count"] == 2
    assert mixed.json()["imported_count"] == 1
    assert mixed.json()["skipped_count"] == 1
    assert mixed.json()["total_requested"] == 2
    assert mixed.json()["working_collection_count"] == 3


def test_source_identity_is_isolated_by_project_and_provider() -> None:
    repository = DemoProjectPublicationRepository()
    client = _client_with_repository(repository)
    openalex = _import_record(number=1, source_id="shared")
    crossref = _import_record(
        number=2,
        provider="crossref",
        source_id="shared",
    )

    lean = client.post(
        "/projects/lean_energy/search-results/imports",
        json={"records": [openalex, crossref]},
    )
    other_project = client.post(
        "/projects/ai_architecture/search-results/imports",
        json={"records": [openalex]},
    )

    assert lean.json()["imported_count"] == 2
    assert lean.json()["skipped_count"] == 0
    assert other_project.json()["imported_count"] == 1
    assert other_project.json()["skipped_count"] == 0


def test_empty_and_missing_project_imports() -> None:
    repository = DemoProjectPublicationRepository()
    client = _client_with_repository(repository)

    empty = client.post(
        "/projects/lean_energy/search-results/imports",
        json={"records": []},
    )
    missing = client.post(
        "/projects/missing/search-results/imports",
        json={"records": []},
    )

    assert empty.json() == {
        "project_id": "lean_energy",
        "imported_count": 0,
        "skipped_count": 0,
        "total_requested": 0,
        "working_collection_count": 5,
    }
    assert missing.status_code == 404


def test_invalid_payload_does_not_partially_write() -> None:
    repository = DemoProjectPublicationRepository()
    client = _client_with_repository(repository)
    valid = _import_record(number=1)
    invalid = {**_import_record(number=2), "authors": [" "]}

    response = client.post(
        "/projects/lean_energy/search-results/imports",
        json={"records": [valid, invalid]},
    )

    assert response.status_code == 422
    assert len(repository.get_publications("lean_energy")) == 5
