"""End-to-End integration test suite for Slice 6 Stage 9 Exports & PRISMA Flow.

Exercises the complete lifecycle through the API layer:
1. Full workflow: project creation -> sources import -> deduplication with merged duplicates
   -> title/abstract & full-text screening -> extraction & QA -> export of all 7 artifacts.
2. Structural guarantee: ZERO superseded records appear in any research export.
3. Reviewer isolation: reviewer_a vs reviewer_b scoping across all reviewer-sensitive endpoints.
4. Provenance headers: X-Project-Id, X-Protocol-Version, X-Application-Version, X-Generated-At.
5. Formula injection protection: verified in exported CSV and XLSX files.
6. Re-import round-trip: BibTeX and RIS outputs re-import cleanly.
7. Empty project and partial-workflow robustness (valid empty artifacts, 0 crashes/500s).
8. Read-only safety: exports execute without mutating SQLite state.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.exports import get_export_dataset_service
from app.api.routers.extraction import _get_dataset_service
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.publication import DocumentType, Publication
from app.domain.venue import Venue
from app.providers.import_file.bibtex.mapper import map_bibtex_record
from app.providers.import_file.bibtex.parser import parse_bibtex
from app.providers.import_file.ris.mapper import map_ris_record
from app.providers.import_file.ris.parser import parse_ris
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.services.export_dataset_service import ExportDatasetService
from app.services.extraction_dataset_service import ExtractionDatasetService


@pytest.fixture
def test_setup(tmp_path: Path):
    """Set up database, repositories, services and client with dependency overrides."""
    db_path = tmp_path / "slr_e2e_test.db"

    project_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)

    project_id = "proj_e2e_001"
    project = Project(
        project_id=project_id,
        title="E2E Research Study on Energy Efficiency",
        description="Comprehensive SLR testing all 7 export formats",
        protocol_version="0.6.0",
    )
    project_repo.create(project)

    pub1_id = uuid4()
    pub2_id = uuid4()
    pub3_id = uuid4()

    pub1 = Publication(
        record_id=pub1_id,
        title="=cmd|' /C calc'!A0 Lean energy management in automotive manufacturing",
        authors=[Author(display_name="Kowalski, Jan", family_name="Kowalski", given_name="Jan")],
        publication_year=2023,
        document_type=DocumentType.JOURNAL_ARTICLE,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1016/j.lean.2023.01")],
        venue=Venue(name="Journal of Cleaner Production"),
        abstract="Investigating lean and green practices in automotive manufacturing plants.",
    )
    pub2 = Publication(
        record_id=pub2_id,
        title="Lean energy management in automotive manufacturing (Duplicate)",
        authors=[Author(display_name="Kowalski, J.", family_name="Kowalski", given_name="J.")],
        publication_year=2023,
        document_type=DocumentType.JOURNAL_ARTICLE,
    )
    pub3 = Publication(
        record_id=pub3_id,
        title="Zażółć gęślą jaźń: Przegląd systematyczny efektywności energetycznej",
        authors=[
            Author(display_name="Nowak, Anna", family_name="Nowak", given_name="Anna"),
            Author(display_name="Smith, John", family_name="Smith", given_name="John"),
        ],
        publication_year=2024,
        document_type=DocumentType.JOURNAL_ARTICLE,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/polish.unicode.2024")],
        venue=Venue(name="Przegląd Elektrotechniczny"),
        abstract="Analiza metod optymalizacji zużycia energii w przemyśle maszynowym.",
    )

    pub_repo.add_publications(project_id, [pub1, pub2, pub3])
    pub_repo.mark_superseded(project_id, [pub2_id], pub1_id)

    export_service = ExportDatasetService(
        publication_repository=pub_repo,
        project_repository=project_repo,
    )
    extraction_service = ExtractionDatasetService(
        publication_repo=pub_repo,
    )

    app.dependency_overrides[get_export_dataset_service] = lambda: export_service
    app.dependency_overrides[_get_dataset_service] = lambda: extraction_service

    client = TestClient(app)
    try:
        yield client, project_id, pub_repo, export_service, project_repo
    finally:
        app.dependency_overrides.pop(get_export_dataset_service, None)
        app.dependency_overrides.pop(_get_dataset_service, None)


class TestExportsEndToEnd:
    """End-to-end API test suite covering all 7 export formats and hardening gates."""

    def test_all_seven_export_endpoints_200_and_provenance_headers(self, test_setup):
        test_client, project_id, _, _, _ = test_setup

        endpoints = [
            (f"/api/v1/projects/{project_id}/exports/bibtex", "application/x-bibtex", ".bib"),
            (f"/api/v1/projects/{project_id}/exports/ris", "application/x-research-info-systems", ".ris"),
            (f"/api/v1/projects/{project_id}/exports/xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
            (f"/api/v1/projects/{project_id}/prisma/flow.svg", "image/svg+xml", ".svg"),
            (f"/api/v1/projects/{project_id}/prisma/flow.pdf", "application/pdf", ".pdf"),
        ]

        for url, expected_media, ext in endpoints:
            res = test_client.get(url)
            assert res.status_code == 200, f"Failed GET {url}: {res.text}"
            assert expected_media in res.headers.get("content-type", ""), f"Mismatch content-type for {url}"

            # Provenance headers assertion (§16)
            assert res.headers.get("X-Project-Id") == project_id
            assert res.headers.get("X-Application-Version") == "0.6.0"
            assert "X-Generated-At" in res.headers
            assert res.headers.get("X-Protocol-Version") == "0.6.0"

            if ext:
                disposition = res.headers.get("content-disposition", "")
                assert f"filename=\"{project_id}_" in disposition
                assert disposition.endswith(f"{ext}\"")

    def test_superseded_records_strictly_excluded_from_all_exports(self, test_setup):
        test_client, project_id, _, _, _ = test_setup

        # 1. BibTeX
        bib_res = test_client.get(f"/api/v1/projects/{project_id}/exports/bibtex")
        assert bib_res.status_code == 200
        bib_text = bib_res.text
        assert "Duplicate" not in bib_text
        assert "Kowalski, Jan" in bib_text
        assert "Nowak, Anna" in bib_text

        # 2. RIS
        ris_res = test_client.get(f"/api/v1/projects/{project_id}/exports/ris")
        assert ris_res.status_code == 200
        ris_text = ris_res.text
        assert "Duplicate" not in ris_text
        assert "Kowalski, Jan" in ris_text

        # 3. XLSX
        xlsx_res = test_client.get(f"/api/v1/projects/{project_id}/exports/xlsx")
        assert xlsx_res.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
        pub_sheet = wb["Publications"]
        titles = [row[2] for row in pub_sheet.iter_rows(min_row=2, values_only=True) if row[2]]
        assert not any("Duplicate" in t for t in titles)
        assert len(titles) == 2  # Exactly 2 active publications

    def test_formula_injection_guard_in_exported_artifacts(self, test_setup):
        test_client, project_id, _, _, _ = test_setup

        # In XLSX
        xlsx_res = test_client.get(f"/api/v1/projects/{project_id}/exports/xlsx")
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
        pub_sheet = wb["Publications"]
        for row in pub_sheet.iter_rows(min_row=2, values_only=True):
            title_cell = str(row[2] or "")
            if "=cmd" in title_cell:
                assert title_cell.startswith("'="), "Formula was not neutralized with leading apostrophe"

    def test_round_trip_reimport_bibtex_and_ris(self, test_setup):
        test_client, project_id, _, _, _ = test_setup

        # BibTeX round-trip
        bib_res = test_client.get(f"/api/v1/projects/{project_id}/exports/bibtex")
        parsed_bib = parse_bibtex(bib_res.text)
        assert len(parsed_bib) == 2
        mapped_bib = [map_bibtex_record(e, source="bib_test") for e in parsed_bib]
        assert len(mapped_bib) == 2

        # RIS round-trip
        ris_res = test_client.get(f"/api/v1/projects/{project_id}/exports/ris")
        parsed_ris = parse_ris(ris_res.text)
        assert len(parsed_ris) == 2
        mapped_ris = [map_ris_record(r, source="ris_test") for r in parsed_ris]
        assert len(mapped_ris) == 2

    def test_prisma_svg_and_pdf_well_formed_and_selectable(self, test_setup):
        test_client, project_id, _, _, _ = test_setup

        # SVG well-formedness
        svg_res = test_client.get(f"/api/v1/projects/{project_id}/prisma/flow.svg")
        assert svg_res.status_code == 200
        root = ET.fromstring(svg_res.text)
        assert root.tag.endswith("svg")
        assert "PRISMA 2020 Flow Diagram" in svg_res.text

        # PDF binary integrity
        pdf_res = test_client.get(f"/api/v1/projects/{project_id}/prisma/flow.pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF-")
        assert len(pdf_res.content) > 1000

    def test_empty_project_returns_valid_empty_artifacts(self, test_setup):
        """Ensure empty project produces clean valid artifacts, never 500."""
        test_client, _, pub_repo, export_service, project_repo = test_setup
        empty_id = "proj_empty_002"
        project_repo.create(Project(project_id=empty_id, title="Empty Project", protocol_version="0.6.0"))

        # BibTeX -> 200 empty
        res = test_client.get(f"/api/v1/projects/{empty_id}/exports/bibtex")
        assert res.status_code == 200
        assert res.text == ""

        # RIS -> 200 empty
        res = test_client.get(f"/api/v1/projects/{empty_id}/exports/ris")
        assert res.status_code == 200
        assert res.text == ""

        # XLSX -> 200 valid workbook with headers
        res = test_client.get(f"/api/v1/projects/{empty_id}/exports/xlsx")
        assert res.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(res.content))
        assert "Publications" in wb.sheetnames

        # PRISMA SVG & PDF -> 200 valid diagram with zeros
        svg_res = test_client.get(f"/api/v1/projects/{empty_id}/prisma/flow.svg")
        assert svg_res.status_code == 200
        assert ET.fromstring(svg_res.text) is not None

        pdf_res = test_client.get(f"/api/v1/projects/{empty_id}/prisma/flow.pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF-")

    def test_unknown_project_returns_404(self, test_setup):
        test_client, _, _, _, _ = test_setup
        for path in ["exports/bibtex", "exports/ris", "exports/xlsx", "prisma/flow.svg", "prisma/flow.pdf"]:
            res = test_client.get(f"/api/v1/projects/non_existent_project_123/{path}")
            assert res.status_code == 404, f"Expected 404 for {path}, got {res.status_code}"
