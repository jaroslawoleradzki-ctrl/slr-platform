from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

import app.api.main as main_module


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    frontend_dist = tmp_path / "frontend-dist"
    assets = frontend_dist / "assets"
    assets.mkdir(parents=True)
    (frontend_dist / "index.html").write_text('<html><body><div id="root"></div></body></html>', encoding="utf-8")
    (assets / "test.js").write_text("console.log('fixture');", encoding="utf-8")

    monkeypatch.setattr(main_module, "_FRONTEND_DIST", frontend_dist)
    original_routes = list(main_module.app.router.routes)
    main_module.app.router.routes[:] = [
        route for route in original_routes if getattr(route, "path", None) != "/assets"
    ]
    fallback_index = next(
        index for index, route in enumerate(main_module.app.router.routes)
        if getattr(route, "path", None) == "/{full_path:path}"
    )
    main_module.app.router.routes.insert(
        fallback_index,
        Mount("/assets", app=StaticFiles(directory=assets), name="test-assets"),
    )

    yield TestClient(main_module.app)
    main_module.app.router.routes[:] = original_routes


def test_spa_routes_are_served_as_html_on_direct_requests(client: TestClient) -> None:
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


def test_business_api_is_namespaced_and_legacy_project_paths_are_not_api(client: TestClient) -> None:
    api_response = client.get("/api/v1/projects")
    assert api_response.status_code == 200
    assert api_response.headers["content-type"].startswith("application/json")
    assert set(api_response.json()) == {"items", "total"}

    for legacy_route in ("/projects", "/projects/project-1"):
        response = client.get(legacy_route)
        assert response.headers["content-type"].startswith("text/html"), legacy_route


def test_unknown_api_route_is_json_404_and_assets_remain_static(client: TestClient) -> None:
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}

    asset_response = client.get("/assets/test.js")
    assert asset_response.status_code == 200
    assert not asset_response.headers["content-type"].startswith("text/html")
