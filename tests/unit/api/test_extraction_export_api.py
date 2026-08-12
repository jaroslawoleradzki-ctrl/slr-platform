from fastapi import HTTPException

from app.api.routers import extraction
from app.repositories.project_repository import ProjectNotFoundError


class FakeDatasetService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def export_json(self, *args, **kwargs):
        self.calls.append(("json", args, kwargs))
        return [{"project_id": args[0]}]

    def export_csv(self, *args, **kwargs):
        self.calls.append(("csv", args, kwargs))
        return "project_id\nproject\n"


def test_json_export_uses_complete_default_contract(monkeypatch) -> None:
    service = FakeDatasetService()
    monkeypatch.setattr(extraction, "_get_dataset_service", lambda: service)

    response = extraction.export_extraction_dataset(
        "project", format="json", dataset="publications", reviewer_id="", include_all=False
    )

    assert response == [{"project_id": "project"}]
    assert service.calls[0][0] == "json"
    assert service.calls[0][2]["status_filter"].value == "complete"


def test_csv_exports_are_separate_downloads(monkeypatch) -> None:
    service = FakeDatasetService()
    monkeypatch.setattr(extraction, "_get_dataset_service", lambda: service)

    publication_response = extraction.export_extraction_dataset(
        "project", format="csv", dataset="publications", reviewer_id="", include_all=False
    )
    relationship_response = extraction.export_extraction_dataset(
        "project", format="csv", dataset="relationships", reviewer_id="", include_all=False
    )

    assert publication_response.media_type == "text/csv"
    assert relationship_response.media_type == "text/csv"
    assert service.calls[0][2]["status_filter"].value == "complete"
    assert service.calls[1][2]["status_filter"].value == "complete"


def test_export_rejects_unknown_format_or_dataset() -> None:
    for kwargs in ({"format": "xml"}, {"dataset": "flat"}):
        try:
            extraction.export_extraction_dataset("project", reviewer_id="", include_all=False, **kwargs)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("invalid export query must return HTTP 422")


def test_export_maps_missing_configuration_or_project_to_404(monkeypatch) -> None:
    class MissingService(FakeDatasetService):
        def export_json(self, *args, **kwargs):
            raise ProjectNotFoundError(args[0])

    monkeypatch.setattr(extraction, "_get_dataset_service", lambda: MissingService())
    try:
        extraction.export_extraction_dataset(
            "missing", format="json", dataset="publications", reviewer_id="", include_all=False
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("missing project must return HTTP 404")
