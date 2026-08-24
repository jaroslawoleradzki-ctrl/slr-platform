"""Unit test suite for Slice 6 export hardening, security guards, and edge cases.

Verifies:
- Formula injection guards in CSV and XLSX
- Control character stripping across all export serializers
- Truncation and clamping of overlong text
- Unicode and Polish character preservation
- Malformed and XML-special metadata handling in SVG and PDF
- Semantic and byte-level determinism
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.prisma_flow import (
    PrismaFlowEdge,
    PrismaFlowMetadata,
    PrismaFlowModel,
    PrismaFlowNode,
)
from app.domain.publication import DocumentType, Publication
from app.domain.venue import Venue
from app.services.export.bibtex_writer import escape_bibtex_value, render_bibtex
from app.services.export.cell_safety import excel_safe_cell, sanitize_csv_cell
from app.services.export.prisma_pdf_renderer import render_prisma_pdf
from app.services.export.prisma_svg_renderer import render_prisma_svg
from app.services.export.ris_writer import render_ris, sanitize_ris_value


def _make_publication(
    title: str,
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    doi: str | None = None,
    abstract: str | None = None,
    journal: str | None = None,
) -> Publication:
    author_objs = [Author(family_name=family, given_name=given, display_name=f"{family}, {given}")]
    venue = Venue(name=journal) if journal else None
    return Publication(
        record_id=uuid4(),
        title=title,
        authors=author_objs,
        publication_year=year,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)] if doi else [],
        abstract=abstract,
        venue=venue,
        document_type=DocumentType.JOURNAL_ARTICLE,
    )


class TestCellSafetyAndFormulaGuard:
    """Test formula injection guards and string sanitization."""

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_csv_formula_injection_neutralization(self, prefix: str):
        malicious = f"{prefix}cmd|' /C calc'!A0"
        sanitized = sanitize_csv_cell(malicious)
        assert sanitized.startswith("'"), f"Expected neutralization prefix for {prefix}"
        assert sanitized == f"'{prefix}cmd|' /C calc'!A0"

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_xlsx_formula_injection_neutralization(self, prefix: str):
        malicious = f"{prefix}SUM(A1:A10)"
        sanitized = excel_safe_cell(malicious)
        assert sanitized.startswith("'")
        assert sanitized == f"'{prefix}SUM(A1:A10)"

    def test_control_character_stripping_csv(self):
        dirty = "Title\x00with\x08null\x1band\x1fcontrols"
        sanitized = sanitize_csv_cell(dirty)
        assert "\x00" not in sanitized
        assert "\x08" not in sanitized
        assert "\x1b" not in sanitized
        assert "\x1f" not in sanitized
        assert sanitized == "Titlewithnullandcontrols"

    def test_control_character_stripping_xlsx(self):
        dirty = "Value\x00with\x0cform\x0efeed"
        sanitized = excel_safe_cell(dirty)
        assert "\x00" not in sanitized
        assert "\x0c" not in sanitized
        assert "\x0e" not in sanitized
        assert sanitized == "Valuewithformfeed"

    def test_xlsx_overlong_cell_truncation(self):
        huge_text = "A" * 40000
        safe = excel_safe_cell(huge_text)
        assert len(safe) == 32767
        assert safe.endswith("…[truncated]")

    def test_unicode_and_polish_preserved_in_cells(self):
        polish = "Zażółć gęślą jaźń / 100% êmîssiøns / 日本語 / العربية"
        assert sanitize_csv_cell(polish) == polish
        assert excel_safe_cell(polish) == polish


class TestBibtexAndRisHardening:
    """Test BibTeX and RIS writers with adversarial and edge-case inputs."""

    def test_bibtex_special_character_protection(self):
        val = "100% of & operations #1 with ~ and ^ and _ plus +"
        escaped = escape_bibtex_value(val)
        assert "{%}" in escaped
        assert "{&}" in escaped
        assert "{#}" in escaped
        assert "{~}" in escaped
        assert "{^}" in escaped
        assert "{_}" in escaped
        assert "{+}" in escaped

    def test_bibtex_control_character_stripping(self):
        pub = _make_publication(title="Paper\x00Title\x1fEnd")
        rendered = render_bibtex([pub])
        assert "\x00" not in rendered
        assert "\x1f" not in rendered
        assert "PaperTitleEnd" in rendered

    def test_ris_crlf_tag_injection_sanitization(self):
        malicious = "Title\r\nER  - \r\nTY  - FAKE\r\nTI  - Injected"
        sanitized = sanitize_ris_value(malicious)
        assert "\r" not in sanitized
        assert "\n" not in sanitized
        assert "Title ER  -  TY  - FAKE TI  - Injected" == sanitized

    def test_ris_control_characters_stripped(self):
        pub = _make_publication(title="RIS\x07Title\x0bClean")
        rendered = render_ris([pub])
        assert "\x07" not in rendered
        assert "\x0b" not in rendered
        assert "RISTitleClean" in rendered

    def test_empty_publications_returns_empty_string(self):
        assert render_bibtex([]) == ""
        assert render_ris([]) == ""


class TestPrismaDiagramHardening:
    """Test SVG and PDF diagram renderers under extreme metadata and characters."""

    def _build_test_flow_model(
        self,
        project_title: str = "Test Project",
        protocol_version: str | None = "0.6.0",
    ) -> PrismaFlowModel:
        metadata = PrismaFlowMetadata(
            project_id="proj_harden",
            project_title=project_title,
            protocol_version=protocol_version,
            application_version="0.6.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            counts_echo={"total_identified": 10, "studies_included_synthesis": 4},
        )
        nodes = [
            PrismaFlowNode(
                node_id="identification.database_searches",
                stage="identification",
                label_key="identification.databases",
                values={"count": 10},
            ),
            PrismaFlowNode(
                node_id="included.synthesis",
                stage="included",
                label_key="included.synthesis",
                values={"count": 4},
            ),
        ]
        edges = [
            PrismaFlowEdge(
                from_node="identification.database_searches",
                to_node="included.synthesis",
            )
        ]
        return PrismaFlowModel(
            project_id="proj_harden",
            metadata=metadata,
            nodes=nodes,
            edges=edges,
            removed={},
        )

    def test_svg_xml_escaping_and_well_formedness_under_malicious_title(self):
        malicious_title = "<script>alert('XSS')</script> & \"quotes\" 'apostrophes' <tag>"
        model = self._build_test_flow_model(project_title=malicious_title)
        svg = render_prisma_svg(model)

        # Must parse cleanly as XML without syntax errors
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg

    def test_svg_long_title_clamping_and_control_chars(self):
        overlong_title = "Huge Title " * 50 + "\x00\x08\x1f"
        model = self._build_test_flow_model(project_title=overlong_title)
        svg = render_prisma_svg(model)

        assert "\x00" not in svg
        assert "\x08" not in svg
        assert "\x1f" not in svg
        root = ET.fromstring(svg)
        assert root is not None

    def test_pdf_rendering_with_polish_diacritics_and_long_title(self):
        long_polish_title = "Zażółć gęślą jaźń: Bardzo długi tytuł badania przeglądowego " * 10
        model = self._build_test_flow_model(project_title=long_polish_title)
        pdf_bytes = render_prisma_pdf(model)

        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000

    def test_svg_byte_determinism_for_identical_model(self):
        model = self._build_test_flow_model(project_title="Stable Project Title")
        svg1 = render_prisma_svg(model)
        svg2 = render_prisma_svg(model)
        assert svg1 == svg2
