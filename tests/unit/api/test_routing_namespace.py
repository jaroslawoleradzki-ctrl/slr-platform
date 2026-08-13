from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_spa_routes_are_served_as_html_on_direct_requests() -> None:
    routes = [
        "/",
        "/projects",
        "/projects/project-1",
        "/projects/project-1/dashboard",
        "/projects/project-1/search",
        "/projects/project-1/sources",
        "/projects/project-1/normalize",
        "/projects/project-1/dedup",
        "/projects/project-1/screen",
        "/projects/project-1/quality-assessment",
        "/projects/project-1/quality-assessment/configuration",
        "/projects/project-1/extract",
        "/projects/project-1/exports",
    ]

    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.headers["content-type"].startswith("text/html"), route
        assert "<div id=\"root\">" in response.text, route


def test_business_api_is_namespaced_and_legacy_project_paths_are_not_api() -> None:
    api_response = client.get("/api/v1/projects")
    assert api_response.status_code == 200
    assert api_response.headers["content-type"].startswith("application/json")
    assert set(api_response.json()) == {"items", "total"}

    for legacy_route in ("/projects", "/projects/project-1"):
        response = client.get(legacy_route)
        assert response.headers["content-type"].startswith("text/html"), legacy_route


def test_unknown_api_route_is_json_404_and_assets_remain_static() -> None:
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}

    asset = next((Path("frontend/dist/assets")).iterdir())
    asset_response = client.get(f"/assets/{asset.name}")
    assert asset_response.status_code == 200
    assert not asset_response.headers["content-type"].startswith("text/html")
