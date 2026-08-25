from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.projects import get_project_repository
from app.api.routers.search_strategy import (
    get_live_search_executor,
    get_project_import_service,
    get_project_publication_repository,
    get_search_result_snapshot_repository,
    get_search_strategy_repository,
)
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.venue import Venue, VenueType
from app.providers.search.base import ProviderSearchOutput
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    DemoProjectPublicationRepository,
    ProjectNotFoundError,
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.search_result_snapshot_repository import (
    SqliteSearchResultSnapshotRepository,
)
from app.repositories.search_strategy_repository import SqliteSearchStrategyRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.live_search import build_search_query
from app.services.project_import_service import ProjectImportService
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
        publications = [
            publication.model_copy(
                update={
                    "provenance": [
                        entry.model_copy(update={"run_id": search_run.run_id}) for entry in publication.provenance
                    ]
                }
            )
            for publication in self.publications
        ]
        return ProviderSearchOutput(
            publications=publications,
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
        provenance=[ProvenanceEntry(source=provider, source_record_id=source_id)],
    )


def _payload(providers: list[str] | None = None) -> dict[str, object]:
    return {
        "publication_year_from": 2018,
        "publication_year_to": 2026,
        "providers": providers or ["openalex", "crossref"],
        "concept_groups": [{"id": "group-1", "name": "Lean", "terms": ["Kaizen", "Lean"]}],
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
        "/api/v1/projects/lean_energy/search-strategy/executions",
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


def test_execution_accepts_semantic_scholar_provider() -> None:
    provider = _Provider(
        "semantic_scholar",
        [_publication("Semantic result", provider="semantic_scholar", source_id="S1")],
        total_count=1,
    )
    response = _client_with_executor(_Executor([provider])).post(
        "/api/v1/projects/lean_energy/search-strategy/executions",
        json=_payload(["semantic_scholar"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["providers"] == ["semantic_scholar"]
    assert body["total_count"] == 1
    assert body["returned_count"] == 1
    assert body["results"][0]["provider"] == "semantic_scholar"
    assert body["results"][0]["source_id"] == "S1"
    assert any(
        pq["provider"] == "semantic_scholar" for pq in body["provider_queries"]
    )
    semantic_query = next(
        pq
        for pq in body["provider_queries"]
        if pq["provider"] == "semantic_scholar"
    )
    assert semantic_query["rendered_query"] == "Kaizen Lean"
    assert semantic_query["is_lossless"] is False
    assert any("OR operators" in warning for warning in semantic_query["warnings"])
    assert body["provider_errors"] == []


def test_semantic_scholar_http_400_remains_auditable_provider_error() -> None:
    request = httpx.Request(
        "GET", "https://api.semanticscholar.org/graph/v1/paper/search"
    )
    with pytest.raises(httpx.HTTPStatusError) as error_info:
        httpx.Response(400, request=request).raise_for_status()

    response = _client_with_executor(
        _Executor([_Provider("semantic_scholar", error=error_info.value)])
    ).post(
        "/api/v1/projects/lean_energy/search-strategy/executions",
        json=_payload(["semantic_scholar"]),
    )

    assert response.status_code == 200
    provider_errors = response.json()["provider_errors"]
    assert len(provider_errors) == 1
    assert provider_errors[0]["provider"] == "semantic_scholar"
    assert provider_errors[0]["message"].startswith(
        "HTTPStatusError: Client error '400 Bad Request'"
    )


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
        "/api/v1/projects/lean_energy/search-strategy/executions",
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["provider"] for item in body["results"]] == [successful_provider]
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
    client = _client_with_executor(_Executor([_Provider("openalex", [publication])]))
    started_at = datetime.now(timezone.utc)
    first = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions",
        json=_payload(["openalex"]),
    ).json()
    second = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions",
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
    assert first["results"][0]["id"] != second["results"][0]["id"]


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
        "/api/v1/projects/lean_energy/search-strategy/executions",
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
        "/api/v1/projects/lean_energy/search-strategy/executions",
        json=payload,
    )

    assert response.status_code == 200
    assert provider.cursors == ["next-page"]
    assert response.json()["next_cursor"] == "next-next"
    assert response.json()["has_more"] is True


def test_unknown_project_and_invalid_strategy_are_rejected() -> None:
    client = _client_with_executor(_Executor([], missing_project=True))
    missing = client.post(
        "/api/v1/projects/not-a-project/search-strategy/executions",
        json=_payload(),
    )
    invalid_payload = _payload()
    invalid_payload["providers"] = []
    invalid = client.post(
        "/api/v1/projects/lean_energy/search-strategy/executions",
        json=invalid_payload,
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_new_project_accepts_frontend_search_contract_and_preserves_snapshot_metadata(
    tmp_path,
) -> None:
    """Exercise the exact browser contract through search, snapshot, and import.

    `providers` is intentionally part of both the persisted-strategy and execution
    requests.  A newly created project has an empty Working Collection, so its
    existence must come from the durable project resource rather than a
    publication row.
    """
    database = tmp_path / "frontend-search-contract.db"
    project_repository = SqliteProjectRepository(database)
    publication_repository = SqliteProjectPublicationRepository(database)
    strategy_repository = SqliteSearchStrategyRepository(database)
    snapshot_repository = SqliteSearchResultSnapshotRepository(database)
    import_service = ProjectImportService(
        publication_repository,
        SqliteImportHistoryRepository(database),
        SqliteNormalizationExecutionRepository(database),
        SqliteTransactionManager(database),
        snapshot_repository,
    )
    publication = Publication(
        title="Fresh OpenAlex result",
        abstract="An abstract retained from the provider response.",
        authors=[Author(display_name="Ada Author")],
        publication_year=2024,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/fresh")],
        venue=Venue(name="Journal of Fresh Results", type=VenueType.JOURNAL),
        publisher="Provider Publisher",
        language="en",
        keywords=["lean", "energy"],
        urls=["https://example.test/fresh"],
        open_access=True,
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W-fresh")],
    )

    app.dependency_overrides[get_project_repository] = lambda: project_repository
    app.dependency_overrides[get_project_publication_repository] = lambda: publication_repository
    app.dependency_overrides[get_search_strategy_repository] = lambda: strategy_repository
    app.dependency_overrides[get_search_result_snapshot_repository] = lambda: snapshot_repository
    app.dependency_overrides[get_project_import_service] = lambda: import_service
    app.dependency_overrides[get_live_search_executor] = lambda: _Executor(
        [_Provider("openalex", [publication])]
    )
    client = TestClient(app)

    created = client.post(
        "/api/v1/projects",
        json={"title": "Frontend search contract", "description": None, "protocol_version": "1.0"},
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    # This is the canonical payload emitted by SearchStrategyPage/projectApi.
    saved = client.put(
        f"/api/v1/projects/{project_id}/search-strategy",
        json={
            "name": "Fresh strategy",
            "description": None,
            "research_questions": ["RQ"],
            "concept_groups": [
                {"group_id": "lean", "name": "Lean", "terms": ["lean"], "operator": "or"}
            ],
            "group_operator": "and",
            "constraints": {
                "publication_year_from": 2024,
                "publication_year_to": 2024,
                "languages": [],
                "publication_types": [],
                "additional_limits": {},
            },
            "providers": ["openalex"],
            "queries": [{"name": "Lean", "expression": {"node_type": "term", "value": "lean"}}],
            "version": 1,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["providers"] == ["openalex"]

    executed = client.post(
        f"/api/v1/projects/{project_id}/search-strategy/executions",
        json={
            "publication_year_from": 2024,
            "publication_year_to": 2024,
            "languages": [],
            "publication_types": [],
            "open_access": False,
            "providers": ["openalex"],
            "concept_groups": [{"id": "lean", "name": "Lean", "terms": ["lean"]}],
        },
    )
    assert executed.status_code == 200
    record = executed.json()["results"][0]
    assert record["source_id"] == "W-fresh"

    imported = client.post(
        f"/api/v1/projects/{project_id}/search-results/imports",
        json={"records": [record]},
    )
    assert imported.status_code == 200
    stored = publication_repository.get_publications(project_id)
    assert len(stored) == 1
    assert stored[0].abstract == "An abstract retained from the provider response."
    assert stored[0].venue == publication.venue
    assert stored[0].publisher == "Provider Publisher"
    assert stored[0].language == "en"
    assert stored[0].urls == ["https://example.test/fresh"]
    assert stored[0].open_access is True
    assert stored[0].identifiers == publication.identifiers
    assert stored[0].provenance[0].source_record_id == "W-fresh"


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
    app.dependency_overrides[get_project_publication_repository] = lambda: repository
    return TestClient(app)


def test_first_and_repeated_import_are_idempotent() -> None:
    repository = DemoProjectPublicationRepository()
    client = _client_with_repository(repository)
    record = _import_record(number=1, source_id="W-new")

    first = client.post(
        "/api/v1/projects/lean_energy/search-results/imports",
        json={"records": [record]},
    )
    repeated = client.post(
        "/api/v1/projects/lean_energy/search-results/imports",
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
        "/api/v1/projects/ai_architecture/search-results/imports",
        json={"records": [first, second]},
    )
    mixed = client.post(
        "/api/v1/projects/ai_architecture/search-results/imports",
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
        "/api/v1/projects/lean_energy/search-results/imports",
        json={"records": [openalex, crossref]},
    )
    other_project = client.post(
        "/api/v1/projects/ai_architecture/search-results/imports",
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
        "/api/v1/projects/lean_energy/search-results/imports",
        json={"records": []},
    )
    missing = client.post(
        "/api/v1/projects/missing/search-results/imports",
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
        "/api/v1/projects/lean_energy/search-results/imports",
        json={"records": [valid, invalid]},
    )

    assert response.status_code == 422
    assert len(repository.get_publications("lean_energy")) == 5


def test_real_browser_flow_lean_energy_strategy_execution_and_import(tmp_path: Path) -> None:
    """Regression test recreating the exact browser flow for project lean_energy.

    Flow:
    1. PUT /api/v1/projects/lean_energy/search-strategy -> 200
    2. POST /api/v1/projects/lean_energy/search-strategy/executions -> 200
    3. Rejection of uncorrected payload with extra 'providers' field -> 422
    4. POST /api/v1/projects/lean_energy/search-results/imports with corrected frontend payload -> 200
    5. Verification of SearchResultSnapshot.abstract -> Publication.abstract preservation.
    """
    database = tmp_path / "browser_flow_lean_energy.db"
    project_repository = SqliteProjectRepository(database)
    publication_repository = SqliteProjectPublicationRepository(database)
    strategy_repository = SqliteSearchStrategyRepository(database)
    snapshot_repository = SqliteSearchResultSnapshotRepository(database)
    import_service = ProjectImportService(
        publication_repository,
        SqliteImportHistoryRepository(database),
        SqliteNormalizationExecutionRepository(database),
        SqliteTransactionManager(database),
        snapshot_repository,
    )
    publication_with_abstract = Publication(
        title="Energy Efficient Machine Learning in Edge Computing",
        abstract="This paper presents a comprehensive study on lean energy optimization.",
        authors=[Author(display_name="Jan Kowalski")],
        publication_year=2024,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/lean.energy.123")],
        venue=Venue(name="IEEE Transactions on Sustainable Computing", type=VenueType.JOURNAL),
        publisher="IEEE",
        language="en",
        keywords=["lean energy", "optimization"],
        urls=["https://example.test/lean_energy_paper"],
        open_access=True,
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W-lean-energy-1")],
    )

    app.dependency_overrides[get_project_repository] = lambda: project_repository
    app.dependency_overrides[get_project_publication_repository] = lambda: publication_repository
    app.dependency_overrides[get_search_strategy_repository] = lambda: strategy_repository
    app.dependency_overrides[get_search_result_snapshot_repository] = lambda: snapshot_repository
    app.dependency_overrides[get_project_import_service] = lambda: import_service
    app.dependency_overrides[get_live_search_executor] = lambda: _Executor(
        [_Provider("openalex", [publication_with_abstract])]
    )
    client = TestClient(app)

    # Ensure lean_energy project exists
    created = client.post(
        "/api/v1/projects",
        json={"title": "lean_energy", "description": "Lean Energy Project", "protocol_version": "1.0"},
    )
    assert created.status_code == 201

    # 1. PUT strategy = 200
    strategy_payload = {
        "name": "Lean Energy Strategy",
        "description": "Strategy for lean energy research",
        "research_questions": ["What is the energy efficiency?"],
        "concept_groups": [
            {"group_id": "grp-1", "name": "Lean Energy", "terms": ["lean energy"], "operator": "or"}
        ],
        "group_operator": "and",
        "constraints": {
            "publication_year_from": 2020,
            "publication_year_to": 2026,
            "languages": ["en"],
            "publication_types": ["article"],
            "additional_limits": {"open_access": True},
        },
        "providers": ["openalex"],
        "queries": [{"name": "Lean Energy", "expression": {"node_type": "term", "value": "lean energy"}}],
        "version": 1,
    }
    put_res = client.put("/api/v1/projects/lean_energy/search-strategy", json=strategy_payload)
    assert put_res.status_code == 200

    # 2. POST execution = 200
    exec_payload = {
        "publication_year_from": 2020,
        "publication_year_to": 2026,
        "languages": ["en"],
        "publication_types": [],
        "open_access": True,
        "providers": ["openalex"],
        "concept_groups": [{"id": "grp-1", "name": "Lean Energy", "terms": ["lean energy"]}],
    }
    exec_res = client.post("/api/v1/projects/lean_energy/search-strategy/executions", json=exec_payload)
    assert exec_res.status_code == 200
    results = exec_res.json()["results"]
    assert len(results) == 1
    record = results[0]

    # 3. Verify bad payload with extra 'providers' field is rejected with 422
    bad_import_payload = {
        "records": [record],
        "query": "(lean energy)",
        "providers": ["openalex"],  # Extra forbidden input
    }
    bad_import_res = client.post("/api/v1/projects/lean_energy/search-results/imports", json=bad_import_payload)
    assert bad_import_res.status_code == 422
    assert "Extra inputs are not permitted" in bad_import_res.text

    # 4. POST search-results/imports with corrected frontend payload = 200
    correct_import_payload = {
        "records": [record],
        "query": "(lean energy)",
        "provider": "openalex",
        "total_available": 1,
    }
    import_res = client.post("/api/v1/projects/lean_energy/search-results/imports", json=correct_import_payload)
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data["project_id"] == "lean_energy"
    assert import_data["imported_count"] == 1

    # 5. Verify SearchResultSnapshot.abstract -> Publication.abstract preservation
    stored_pubs = publication_repository.get_publications("lean_energy")
    assert len(stored_pubs) == 1
    imported_pub = stored_pubs[0]
    assert imported_pub.abstract == "This paper presents a comprehensive study on lean energy optimization."
    assert imported_pub.abstract is not None
    assert len(imported_pub.abstract) > 0
