from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.search_strategy import (
    get_project_publication_repository,
    get_search_strategy_repository,
)
from app.repositories.project_publication_repository import (
    DemoProjectPublicationRepository,
)
from app.repositories.search_strategy_repository import (
    SqliteSearchStrategyRepository,
)


def _payload() -> dict[str, object]:
    return {
        "name": "Lean energy strategy",
        "description": "Primary protocol strategy",
        "research_questions": ["How does lean production affect energy use?"],
        "concept_groups": [
            {
                "group_id": "energy",
                "name": "Energy",
                "terms": ["energy efficiency", "energy reduction"],
                "operator": "or",
            }
        ],
        "group_operator": "and",
        "constraints": {
            "publication_year_from": 2015,
            "publication_year_to": 2026,
            "languages": ["en"],
            "publication_types": ["article"],
            "additional_limits": {"open_access": True},
        },
        "providers": ["openalex", "crossref", "semantic_scholar"],
        "queries": [
            {
                "name": "Core Boolean query",
                "expression": {
                    "node_type": "group",
                    "operator": "not",
                    "children": [
                        {
                            "node_type": "term",
                            "value": "conference abstract",
                        }
                    ],
                },
            }
        ],
    }


def _client(tmp_path: Path) -> TestClient:
    repository = SqliteSearchStrategyRepository(tmp_path / "api.db")
    app.dependency_overrides[get_search_strategy_repository] = lambda: repository
    app.dependency_overrides[get_project_publication_repository] = (
        DemoProjectPublicationRepository
    )
    return TestClient(app)


def test_put_then_get_returns_fully_serialized_strategy(tmp_path: Path) -> None:
    client = _client(tmp_path)

    put_response = client.put(
        "/projects/lean_energy/search-strategy",
        json=_payload(),
    )
    get_response = client.get("/projects/lean_energy/search-strategy")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json() == put_response.json()
    assert get_response.json()["project_id"] == "lean_energy"
    assert get_response.json()["queries"][0]["expression"]["operator"] == "not"
    app.dependency_overrides.clear()


def test_repeated_put_preserves_server_assigned_strategy_identity(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    first = client.put(
        "/projects/lean_energy/search-strategy",
        json=_payload(),
    )
    second = client.put(
        "/projects/lean_energy/search-strategy",
        json=_payload(),
    )

    assert second.status_code == 200
    assert second.json()["strategy_id"] == first.json()["strategy_id"]
    assert second.json()["created_at"] == first.json()["created_at"]
    app.dependency_overrides.clear()


def test_put_validates_year_range_and_unknown_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = _payload()
    payload["constraints"] = {
        "publication_year_from": 2026,
        "publication_year_to": 2015,
    }
    payload["unexpected"] = True

    response = client.put(
        "/projects/lean_energy/search-strategy",
        json=payload,
    )

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_get_missing_strategy_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/projects/lean_energy/search-strategy")

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_put_unknown_project_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put(
        "/projects/unknown/search-strategy",
        json=_payload(),
    )

    assert response.status_code == 404
    app.dependency_overrides.clear()
