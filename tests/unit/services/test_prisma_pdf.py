"""Unit tests for PRISMA 2020 PDF renderer (v0.6.1 Slice 4)."""

import io
from datetime import datetime, timezone
from pathlib import Path

import pypdf

from app.domain.project import Project
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.services.export.prisma_flow_builder import build_flow_model
from app.services.export.prisma_pdf_renderer import render_prisma_pdf
from app.services.export_dataset_service import ExportDatasetService
from app.services.prisma_metrics_service import PrismaMetrics
from tests.fixtures.factories import make_publication

PROJECT_ID = "prisma_pdf_project"


def _sample_metrics(
    *,
    providers: int = 150,
    imports: int = 50,
    working: int = 200,
    after_dedup: int = 180,
    screened_ta: int = 180,
    excluded_ta: int = 60,
    screened_ft: int = 120,
    excluded_ft: int = 75,
    included: int = 45,
    pending_groups: int = 2,
    manual_breakdown: dict[str, int] | None = None,
) -> PrismaMetrics:
    return PrismaMetrics(
        project_id=PROJECT_ID,
        records_identified_providers=providers,
        records_identified_imports=imports,
        total_identified=providers + imports,
        records_after_normalization=working,
        records_before_dedup=working,
        records_after_technical_merger=after_dedup,
        duplicate_groups_pending_review=pending_groups,
        records_screened_title_abstract=screened_ta,
        records_excluded_title_abstract=excluded_ta,
        records_screened_full_text=screened_ft,
        records_excluded_full_text=excluded_ft,
        studies_included_synthesis=included,
        manual_source_breakdown=manual_breakdown or {"pubmed_export": 30, "scopus_export": 20},
    )


class TestPrismaPdfRenderer:
    def test_render_pdf_starts_with_pdf_magic_number(self) -> None:
        metrics = _sample_metrics()
        model = build_flow_model(metrics)
        pdf_bytes = render_prisma_pdf(model)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000

    def test_render_pdf_extracts_stages_and_semantic_counts_via_pypdf(self) -> None:
        metrics = _sample_metrics()
        model = build_flow_model(metrics)
        pdf_bytes = render_prisma_pdf(model)

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) == 1

        text = reader.pages[0].extract_text()

        # Stages
        assert "PRISMA 2020 Flow Diagram" in text
        assert "Identification" in text
        assert "Screening" in text
        assert "Included" in text

        # Node labels and counts
        assert "Records identified from databases & registers" in text
        assert "Database records (n = 150)" in text
        assert "Records identified from other methods" in text
        assert "Manual file imports (n = 50)" in text
        assert "pubmed_export: 30" in text
        assert "scopus_export: 20" in text
        assert "Records after duplicate removal" in text
        assert "Active canonical records (n = 180)" in text
        assert "Duplicates removed" in text
        assert "Technical duplicates merged (n = 20)" in text
        assert "Candidate groups pending review: 2" in text
        assert "Records screened" in text
        assert "Title & Abstract screened (n = 180)" in text
        assert "Records excluded" in text
        assert "Title & Abstract excluded (n = 60)" in text
        assert "Reports sought for retrieval & assessed" in text
        assert "Full-Text reports assessed (n = 120)" in text
        assert "Reports excluded" in text
        assert "Full-Text excluded (n = 75)" in text
        assert "Studies included in review" in text
        assert "Studies included in synthesis (n = 45)" in text

    def test_render_pdf_handles_empty_project_cleanly(self) -> None:
        metrics = _sample_metrics(
            providers=0,
            imports=0,
            working=0,
            after_dedup=0,
            screened_ta=0,
            excluded_ta=0,
            screened_ft=0,
            excluded_ft=0,
            included=0,
            pending_groups=0,
            manual_breakdown={},
        )
        model = build_flow_model(metrics)
        pdf_bytes = render_prisma_pdf(model)

        assert pdf_bytes.startswith(b"%PDF-")
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) == 1
        text = reader.pages[0].extract_text()

        assert "Database records (n = 0)" in text
        assert "Active canonical records (n = 0)" in text
        assert "Title & Abstract screened (n = 0)" in text
        assert "Full-Text reports assessed (n = 0)" in text
        assert "Studies included in synthesis (n = 0)" in text

        # Zero-valued side boxes must NOT be rendered when denominator is 0
        assert "Technical duplicates merged" not in text
        assert "Title & Abstract excluded" not in text
        assert "Full-Text excluded" not in text

    def test_render_pdf_unicode_and_polish_diacritics_survive_extraction(self) -> None:
        polish_title = "Systematyczny Przegląd — Zażółć gęślą jaźń"
        project = Project(
            project_id=PROJECT_ID,
            title=polish_title,
            protocol_version="Wersja 1.0 (Łódź & Śrem)",
        )
        metrics = _sample_metrics(
            manual_breakdown={"Źródło_PubMed": 30, "Baza_Gdańsk": 20},
        )
        model = build_flow_model(metrics, project=project)
        pdf_bytes = render_prisma_pdf(model)

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = reader.pages[0].extract_text()

        # Polish diacritics in title, subtitle, and manual source breakdown
        assert "Zażółć gęślą jaźń" in text
        assert "Łódź" in text
        assert "Śrem" in text
        assert "Źródło_PubMed: 30" in text
        assert "Baza_Gdańsk: 20" in text

    def test_render_pdf_semantic_determinism_across_calls(self) -> None:
        metrics = _sample_metrics()
        now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
        project = Project(project_id=PROJECT_ID, title="Determinism Check")
        model1 = build_flow_model(metrics, project=project, generated_at=now)
        model2 = build_flow_model(metrics, project=project, generated_at=now)

        pdf1 = render_prisma_pdf(model1)
        pdf2 = render_prisma_pdf(model2)

        reader1 = pypdf.PdfReader(io.BytesIO(pdf1))
        reader2 = pypdf.PdfReader(io.BytesIO(pdf2))

        assert len(reader1.pages) == len(reader2.pages) == 1
        assert reader1.pages[0].extract_text() == reader2.pages[0].extract_text()
        assert pdf1 == pdf2


class TestPrismaPdfPartialWorkflowIntegration:
    """Integration test verifying end-to-end PDF generation from persisted database state."""

    def test_partial_workflow_persisted_pdf_generation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "pdf_partial.db"
        proj_repo = SqliteProjectRepository(db_path)
        proj_repo.create(Project(project_id=PROJECT_ID, title="Metabolic SLR"))

        pub_repo = SqliteProjectPublicationRepository(db_path)
        pubs = [make_publication(i, title=f"Study {i}") for i in range(1, 11)]
        pub_repo.add_publications(PROJECT_ID, pubs)

        dec_repo = SqliteScreeningDecisionRepository(db_path)
        # 10 evaluated at T&A: 7 INCLUDE, 3 EXCLUDE
        for i in range(7):
            dec_repo.save(
                ScreeningDecision(
                    project_id=PROJECT_ID,
                    publication_id=pubs[i].record_id,
                    stage=ScreeningStage.TITLE_ABSTRACT,
                    outcome=ScreeningOutcome.INCLUDE,
                    reviewer_id="rev_1",
                )
            )
        for i in range(7, 10):
            dec_repo.save(
                ScreeningDecision(
                    project_id=PROJECT_ID,
                    publication_id=pubs[i].record_id,
                    stage=ScreeningStage.TITLE_ABSTRACT,
                    outcome=ScreeningOutcome.EXCLUDE,
                    reviewer_id="rev_1",
                )
            )

        # 3 evaluated at FT: 2 INCLUDE, 1 EXCLUDE; 4 pending
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pubs[0].record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_1",
            )
        )
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pubs[1].record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id="rev_1",
            )
        )
        dec_repo.save(
            ScreeningDecision(
                project_id=PROJECT_ID,
                publication_id=pubs[2].record_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.EXCLUDE,
                reviewer_id="rev_1",
            )
        )

        service = ExportDatasetService(
            publication_repository=pub_repo,
            screening_reporting_repository=ScreeningReportingRepository(db_path),
        )

        pdf_bytes = service.get_prisma_pdf(PROJECT_ID, reviewer_id="rev_1")
        assert pdf_bytes.startswith(b"%PDF-")

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = reader.pages[0].extract_text()

        assert "Title & Abstract screened (n = 10)" in text
        assert "Title & Abstract excluded (n = 3)" in text
        assert "Full-Text reports assessed (n = 3)" in text
        assert "Full-Text excluded (n = 1)" in text
        assert "Studies included in synthesis (n = 2)" in text


class TestPrismaFontAssetAndLicenseCompliance:
    """Compliance tests for P1-S4-2: Font asset tracking and complete official licensing."""

    def test_bundled_font_binaries_exist_and_are_non_empty(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        regular = repo_root / "assets" / "fonts" / "DejaVuSans.ttf"
        bold = repo_root / "assets" / "fonts" / "DejaVuSans-Bold.ttf"

        assert regular.is_file(), f"Expected font file missing: {regular}"
        assert bold.is_file(), f"Expected font file missing: {bold}"
        assert regular.stat().st_size > 500_000, f"Font file abnormally small: {regular}"
        assert bold.stat().st_size > 500_000, f"Font file abnormally small: {bold}"

    def test_license_contains_bitstream_vera_and_tavmjong_bah_arev_notices(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        license_file = repo_root / "assets" / "fonts" / "LICENSE.txt"

        assert license_file.is_file(), f"Expected license file missing: {license_file}"
        license_text = license_file.read_text(encoding="utf-8")

        # 1. Bitstream Vera copyright notice and terms
        assert "Bitstream Vera Fonts Copyright" in license_text
        assert "Copyright (c) 2003 by Bitstream, Inc." in license_text
        assert "Bitstream Vera is" in license_text

        # 2. Tavmjong Bah / Arev Fonts copyright notice and terms
        assert "Arev Fonts Copyright" in license_text
        assert "Copyright (c) 2006 by Tavmjong Bah" in license_text
        assert "Tavmjong Bah" in license_text

        # 3. DejaVu public domain declaration
        assert "DejaVu changes are in public domain" in license_text

    def test_dockerfile_copies_fonts_into_production_runtime_stage(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        dockerfile = repo_root / "docker" / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        assert "COPY assets/fonts ./assets/fonts" in content or "COPY assets ./assets" in content


class TestFontResolutionWithoutSystemFonts:
    """Regression tests for P1-S4-1: Proof font resolution works without system fonts."""

    def test_get_font_paths_resolves_bundled_in_repo_assets(self) -> None:
        from app.services.export.prisma_pdf_renderer import _get_font_paths

        regular, bold = _get_font_paths()
        assert regular.name == "DejaVuSans.ttf"
        assert bold.name == "DejaVuSans-Bold.ttf"
        assert regular.is_file()
        assert bold.is_file()
        assert "assets/fonts" in str(regular) or str(regular).startswith("/app")
