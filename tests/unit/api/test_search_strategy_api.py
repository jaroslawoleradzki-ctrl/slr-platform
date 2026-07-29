from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def valid_payload() -> dict[str, object]:
    return {
        "publication_year_from": 2018,
        "publication_year_to": 2026,
        "providers": ["openalex", "crossref"],
        "concept_groups": [
            {"id": "group-1", "name": "Lean", "terms": ["Kaizen", "Lean"]}
        ],
    }


def test_execute_search_strategy_validates_and_returns_backend_contract() -> None:
    response = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=valid_payload(),
    )

    assert response.status_code == 200
    assert response.json() | {"executed_at": "ignored"} == {
        "project_id": "lean_energy",
        "status": "validated",
        "rendered_query": '("Kaizen" OR "Lean")',
        "providers": ["openalex", "crossref"],
        "publication_year_from": 2018,
        "publication_year_to": 2026,
        "executed_at": "ignored",
    }


def test_execute_search_strategy_rejects_invalid_years_and_empty_providers() -> None:
    payload = valid_payload()
    payload["publication_year_from"] = 2027
    payload["publication_year_to"] = 2020
    payload["providers"] = []

    response = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=payload,
    )

    assert response.status_code == 422
