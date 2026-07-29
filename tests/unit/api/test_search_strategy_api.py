from datetime import datetime, timezone

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
    body = response.json()
    assert body["project_id"] == "lean_energy"
    assert body["status"] == "validated"
    assert body["rendered_query"] == '("Kaizen" OR "Lean")'
    assert body["providers"] == ["openalex", "crossref"]
    assert body["publication_year_from"] == 2018
    assert body["publication_year_to"] == 2026
    assert body["result_count"] == 3
    assert [record["provider"] for record in body["results"]] == [
        "openalex",
        "crossref",
        "openalex",
    ]
    assert body["results"][2]["doi"] is None


def test_controlled_results_are_fully_deterministic() -> None:
    started_at = datetime.now(timezone.utc)
    first = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=valid_payload(),
    )
    second = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=valid_payload(),
    )
    finished_at = datetime.now(timezone.utc)

    first_body = first.json()
    second_body = second.json()
    first_executed_at = datetime.fromisoformat(first_body.pop("executed_at"))
    second_executed_at = datetime.fromisoformat(second_body.pop("executed_at"))

    assert started_at <= first_executed_at <= finished_at
    assert started_at <= second_executed_at <= finished_at
    assert first_executed_at.tzinfo is not None
    assert second_executed_at.tzinfo is not None
    assert first_body == second_body
    assert first_body["result_count"] == 3
    assert first_body["results"] == second_body["results"]
    assert [record["id"] for record in first_body["results"]] == [
        record["id"] for record in second_body["results"]
    ]
    assert first_body["rendered_query"] == '("Kaizen" OR "Lean")'
    assert first_body["providers"] == ["openalex", "crossref"]
    assert first_body["publication_year_from"] == 2018
    assert first_body["publication_year_to"] == 2026


def test_empty_results_and_unknown_project() -> None:
    empty = client.post(
        "/projects/ai_architecture/search-strategy/executions",
        json=valid_payload(),
    )
    missing = client.post(
        "/projects/not-a-project/search-strategy/executions",
        json=valid_payload(),
    )

    assert empty.status_code == 200
    assert empty.json()["result_count"] == 0
    assert empty.json()["results"] == []
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Project 'not-a-project' not found."}


def test_results_follow_provider_and_year_filters_in_stable_order() -> None:
    payload = valid_payload()
    payload["providers"] = ["openalex"]
    payload["publication_year_from"] = 2022
    response = client.post(
        "/projects/lean_energy/search-strategy/executions",
        json=payload,
    )

    assert response.status_code == 200
    assert [(item["year"], item["provider"]) for item in response.json()["results"]] == [
        (2024, "openalex")
    ]


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
