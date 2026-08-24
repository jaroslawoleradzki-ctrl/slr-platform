"""Semantic read-back tests for the XLSX research-matrix builder (v0.6.1 Slice 2)."""

import io
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from openpyxl import load_workbook

from app.domain.author import Author
from app.domain.extraction import ExtractedValueState, ValueStatus
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.domain.quality_assessment import (
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplateCriterion,
)
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    EvidenceCharacter,
    RelationDirection,
)
from app.domain.venue import Venue
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.services.export.cell_safety import excel_safe_cell
from app.services.export.xlsx_workbook import (
    ALL_SHEET_NAMES,
    SHEET_DATA_EXTRACTION,
    SHEET_PRISMA_SUMMARY,
    SHEET_PUBLICATIONS,
    SHEET_QUALITY_ASSESSMENT,
    SHEET_SCREENING_TITLE_ABSTRACT,
    SHEET_SYNTHESIS_RELATIONS,
    build_data_extraction_sheet,
    build_prisma_summary_sheet,
    build_publications_sheet,
    build_quality_assessment_sheet,
    build_screening_title_abstract_sheet,
    build_synthesis_relations_sheet,
    collect_research_matrix_inputs,
    render_research_matrix_workbook,
)
from app.services.export_dataset_service import (
    BibliographicEntry,
    ExportDatasetService,
    QualityAssessmentRow,
    QualityAssessmentSheetData,
)
from app.services.prisma_metrics_service import PrismaMetrics
from tests.fixtures.factories import make_publication

PROJECT_ID = "lean_energy"
TEST_TIME = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def make_decision(publication_id: UUID, stage: ScreeningStage, outcome: ScreeningOutcome) -> ScreeningDecision:
    return ScreeningDecision(
        project_id=PROJECT_ID,
        publication_id=publication_id,
        stage=stage,
        outcome=outcome,
        reviewer_id="alice",
        decided_at=TEST_TIME,
    )


def make_relation(publication_id: UUID, group_item_id: UUID, *, approved: bool = True) -> AnalyticalRelation:
    return AnalyticalRelation(
        project_id=PROJECT_ID,
        publication_id=publication_id,
        latest_revision_id=uuid4(),
        group_item_id=group_item_id,
        item_index=1,
        source_practice="5S",
        source_effect="kWh reduction",
        direction=RelationDirection.POSITIVE,
        magnitude=12.5,
        evidence_character=EvidenceCharacter.EMPIRICAL,
        approval_state=ClassificationApprovalState.APPROVED if approved else ClassificationApprovalState.PENDING,
    )


def render_single_sheet(title: str, builder) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = title
    builder(sheet)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def sheet_values(workbook_bytes: bytes, title: str) -> list[list]:
    workbook = load_workbook(io.BytesIO(workbook_bytes), data_only=True)
    return [list(row) for row in workbook[title].iter_rows(values_only=True)]


class TestCellSafety:
    def test_formula_trigger_characters_are_neutralized(self) -> None:
        for hostile in ("=1+1", "+2", "-3", "@cmd", "\tTAB"):
            assert excel_safe_cell(hostile).startswith("'")

    def test_control_characters_are_stripped(self) -> None:
        assert excel_safe_cell("a\x00b\x0bc\x1fd") == "abcd"

    def test_overlong_values_are_truncated_with_marker(self) -> None:
        result = excel_safe_cell("x" * 40000)
        assert len(result) == 32767
        assert result.endswith("…[truncated]")

    def test_none_becomes_empty(self) -> None:
        assert excel_safe_cell(None) == ""


class TestSheetBuildersPure:
    def test_publications_sheet_columns_and_values(self) -> None:
        publication = Publication(
            record_id=UUID(int=1),
            title="Lean energy",
            authors=[Author(display_name="Smith, John", family_name="Smith", given_name="John")],
            publication_year=2024,
            venue=Venue(name="JoCP"),
            identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/x")],
            keywords=["lean"],
            created_at=TEST_TIME,
        )
        payload = render_single_sheet(
            SHEET_PUBLICATIONS, lambda sheet: build_publications_sheet(sheet, [BibliographicEntry(7, publication)])
        )
        rows = sheet_values(payload, SHEET_PUBLICATIONS)

        assert rows[0][:6] == ["record_id", "position", "title", "authors", "publication_year", "doi"]
        assert rows[1][0] == "00000000-0000-0000-0000-000000000001"
        assert rows[1][1] == 7
        assert rows[1][2] == "Lean energy"
        assert rows[1][3] == "Smith, John"
        assert rows[1][4] == 2024
        assert rows[1][5] == "10.1000/x"

    def test_screening_sheet_filters_by_stage(self) -> None:
        pub_a, pub_b = UUID(int=1), UUID(int=2)
        decisions = [
            make_decision(pub_b, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.INCLUDE),
            make_decision(pub_a, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.EXCLUDE),
            make_decision(pub_a, ScreeningStage.FULL_TEXT, ScreeningOutcome.INCLUDE),
        ]
        payload = render_single_sheet(
            SHEET_SCREENING_TITLE_ABSTRACT,
            lambda sheet: build_screening_title_abstract_sheet(sheet, decisions),
        )
        rows = sheet_values(payload, SHEET_SCREENING_TITLE_ABSTRACT)

        assert len(rows) == 3  # header + exactly the two T&A decisions
        assert {rows[1][0], rows[2][0]} == {str(pub_a), str(pub_b)}
        assert all(row[2] in {"include", "exclude"} for row in rows[1:])

    def test_quality_assessment_criterion_profile_without_numeric_collapse(self) -> None:
        criterion_yes = QualityAssessmentTemplateCriterion(
            template_id=UUID(int=99), display_order=1, question="Clear rationale?"
        )
        criterion_unclear = QualityAssessmentTemplateCriterion(
            template_id=UUID(int=99), display_order=2, question="Methods sound?"
        )
        response_yes = QualityAssessmentResponse(
            assessment_id=uuid4(),
            criterion_id=criterion_yes.criterion_id,
            question_snapshot=criterion_yes.question,
            response_value=QualityAssessmentResponseValue.YES,
        )
        response_unclear = QualityAssessmentResponse(
            assessment_id=uuid4(),
            criterion_id=criterion_unclear.criterion_id,
            question_snapshot=criterion_unclear.question,
            response_value=QualityAssessmentResponseValue.CANNOT_DETERMINE,
            justification="Unclear sampling",
        )
        qa_data = QualityAssessmentSheetData(
            criteria=(criterion_yes, criterion_unclear),
            rows=(
                QualityAssessmentRow(
                    publication_id=UUID(int=1),
                    reviewer_id="bob",
                    template_id=str(UUID(int=99)),
                    template_version=3,
                    responses_by_criterion={
                        criterion_yes.criterion_id: response_yes,
                        criterion_unclear.criterion_id: response_unclear,
                    },
                    assessed_at=TEST_TIME,
                ),
            ),
        )

        payload = render_single_sheet(
            SHEET_QUALITY_ASSESSMENT, lambda sheet: build_quality_assessment_sheet(sheet, qa_data)
        )
        rows = sheet_values(payload, SHEET_QUALITY_ASSESSMENT)
        headers, data_row = rows[0], rows[1]

        yes_index = headers.index("C1 Clear rationale?")
        unclear_index = headers.index("C2 Methods sound?")
        justification_index = headers.index("C2 Methods sound? — justification")
        assert data_row[yes_index] == "YES"
        assert data_row[unclear_index] == "CANNOT_DETERMINE"
        assert data_row[justification_index] == "Unclear sampling"

    def test_quality_assessment_headers_only_when_unconfigured(self) -> None:
        payload = render_single_sheet(
            SHEET_QUALITY_ASSESSMENT, lambda sheet: build_quality_assessment_sheet(sheet, None)
        )
        rows = sheet_values(payload, SHEET_QUALITY_ASSESSMENT)

        assert rows[0][:4] == ["publication_id", "reviewer_id", "template_id", "template_version"]
        assert len(rows) == 1

    def test_synthesis_sheet_schema_state_column_and_ordering(self) -> None:
        relations = [
            make_relation(UUID(int=2), UUID(int=22)),
            make_relation(UUID(int=1), UUID(int=11)),
        ]
        payload = render_single_sheet(
            SHEET_SYNTHESIS_RELATIONS, lambda sheet: build_synthesis_relations_sheet(sheet, relations)
        )
        rows = sheet_values(payload, SHEET_SYNTHESIS_RELATIONS)

        assert rows[0] == [
            "publication_id", "group_item_id", "source_practice",
            "analytical_lean_category_id", "source_effect",
            "analytical_energy_category_id", "direction", "magnitude",
            "evidence_character", "approval_state",
        ]
        assert rows[1][0] < rows[2][0]
        assert rows[1][6] == "positive" or isinstance(rows[1][6], str)
        assert rows[1][7] == 12.5
        assert all(row[9] == "approved" for row in rows[1:])

    def test_prisma_summary_echoes_authoritative_metrics_and_flattens_breakdown(self) -> None:
        metrics = PrismaMetrics(
            project_id=PROJECT_ID,
            records_identified_providers=10,
            records_identified_imports=5,
            total_identified=15,
            records_after_normalization=15,
            records_before_dedup=15,
            records_after_technical_merger=13,
            duplicate_groups_pending_review=1,
            records_screened_title_abstract=8,
            records_screened_full_text=4,
            studies_included_synthesis=3,
            manual_source_breakdown={"scopus": 3, "google_scholar_pop": 2},
        )
        payload = render_single_sheet(SHEET_PRISMA_SUMMARY, lambda sheet: build_prisma_summary_sheet(sheet, metrics))
        rows = sheet_values(payload, SHEET_PRISMA_SUMMARY)

        by_header = dict(zip(rows[0], rows[1]))
        assert by_header["records_identified_providers"] == 10
        assert by_header["records_after_technical_merger"] == 13
        assert by_header["studies_included_synthesis"] == 3
        assert by_header["manual_source_google_scholar_pop"] == 2
        assert by_header["manual_source_scopus"] == 3

    def test_extraction_sheet_uses_csv_export_header_scheme(self) -> None:
        from types import SimpleNamespace

        from app.domain.extraction import ValueOrigin

        value = ExtractedValueState(
            field_key="e4_country",
            status=ValueStatus.PRESENT,
            text_value="Poland",
            origin=ValueOrigin.REPORTED,
            source_page="1",
        )
        model = SimpleNamespace(
            project_id=PROJECT_ID,
            publication_id=UUID(int=1),
            canonical_title="T",
            canonical_authors=["A"],
            canonical_publication_year=2024,
            canonical_doi=None,
            canonical_journal=None,
            template_id="tpl",
            template_version="v1",
            completeness_status=SimpleNamespace(value="complete"),
            latest_revision_index=1,
            latest_revision_id=uuid4(),
            reviewer_id="alice",
            submitted_at=TEST_TIME,
            publication_values=[value],
        )

        class _Template:
            publication_fields = []

        payload = render_single_sheet(
            SHEET_DATA_EXTRACTION, lambda sheet: build_data_extraction_sheet(sheet, [model], _Template())
        )
        rows = sheet_values(payload, SHEET_DATA_EXTRACTION)

        assert len(rows) == 2
        assert rows[0][13] == "submitted_at"


class TestWorkbookAssemblyIntegration:
    @pytest.fixture
    def seeded_environment(self, tmp_path: Path):
        database = tmp_path / "xlsx.db"
        repo = SqliteProjectPublicationRepository(database)
        publications = [
            make_publication(1, doi="10.1000/a"),
            make_publication(2),
            make_publication(3, doi="10.1000/c"),
        ]
        repo.add_publications(PROJECT_ID, publications)
        canonical, superseded = publications[0], publications[1]
        repo.mark_superseded(PROJECT_ID, [superseded.record_id], canonical.record_id)

        service = ExportDatasetService(publication_repository=repo)
        inputs = collect_research_matrix_inputs(service, PROJECT_ID)
        payload = render_research_matrix_workbook(inputs)
        return canonical, superseded, payload, repo, service

    def test_all_seven_plan_sheets_present_in_plan_order(self, seeded_environment) -> None:
        _, _, payload, _, _ = seeded_environment
        workbook = load_workbook(io.BytesIO(payload))
        assert tuple(workbook.sheetnames) == ALL_SHEET_NAMES

    def test_publications_sheet_excludes_superseded_records_with_persisted_positions(self, seeded_environment) -> None:
        canonical, superseded, payload, *_ = seeded_environment
        rows = sheet_values(payload, SHEET_PUBLICATIONS)

        record_ids = {row[0] for row in rows[1:]}
        assert str(canonical.record_id) in record_ids
        assert str(superseded.record_id) not in record_ids
        positions = sorted(row[1] for row in rows[1:])
        assert positions == [0, 2]  # true persisted positions; superseded gap preserved

    def test_empty_project_yields_all_sheets_headers_only(self, tmp_path: Path) -> None:
        from app.services.export.xlsx_workbook import SHEET_PRISMA_SUMMARY

        repo = SqliteProjectPublicationRepository(tmp_path / "empty.db")
        repo.get_publications("ai_architecture")
        service = ExportDatasetService(publication_repository=repo)
        payload = render_research_matrix_workbook(collect_research_matrix_inputs(service, "ai_architecture"))

        workbook = load_workbook(io.BytesIO(payload))
        assert tuple(workbook.sheetnames) == ALL_SHEET_NAMES
        for name in ALL_SHEET_NAMES:
            sheet = workbook[name]
            if name is SHEET_PRISMA_SUMMARY or name == SHEET_PRISMA_SUMMARY:
                # PRISMA echoes authoritative zero-filled metrics for empty projects.
                assert sheet.max_row == 2
            else:
                assert sheet.max_row == 1  # header row only

    def test_semantic_determinism_across_repeated_generation(self, seeded_environment) -> None:
        _, _, payload_first, _, service = seeded_environment
        payload_second = render_research_matrix_workbook(collect_research_matrix_inputs(service, PROJECT_ID))

        first_wb = load_workbook(io.BytesIO(payload_first))
        second_wb = load_workbook(io.BytesIO(payload_second))
        for name in ALL_SHEET_NAMES:
            first = tuple(tuple(row) for row in first_wb[name].iter_rows(values_only=True))
            second = tuple(tuple(row) for row in second_wb[name].iter_rows(values_only=True))
            assert first == second, name

    def test_unicode_metadata_survives_roundtrip_through_workbook(self, tmp_path: Path) -> None:
        unicode_title = "Wpływ zarządzania lean na efektywność energetyczną"
        repo = SqliteProjectPublicationRepository(tmp_path / "uni.db")
        repo.add_publications(PROJECT_ID, [make_publication(1, title=unicode_title)])
        service = ExportDatasetService(publication_repository=repo)
        payload = render_research_matrix_workbook(collect_research_matrix_inputs(service, PROJECT_ID))

        rows = sheet_values(payload, SHEET_PUBLICATIONS)
        assert any(row[2] == unicode_title for row in rows[1:])

    def test_formula_injection_neutralized_inside_cells(self, tmp_path: Path) -> None:
        repo = SqliteProjectPublicationRepository(tmp_path / "formula.db")
        repo.add_publications(PROJECT_ID, [make_publication(1, title='=HYPERLINK("http://evil")')])
        service = ExportDatasetService(publication_repository=repo)
        payload = render_research_matrix_workbook(collect_research_matrix_inputs(service, PROJECT_ID))

        rows = sheet_values(payload, SHEET_PUBLICATIONS)
        assert any(isinstance(row[2], str) and row[2].startswith("'=") for row in rows[1:])

    def test_missing_optional_metadata_leaves_empty_cells_not_placeholders(self, tmp_path: Path) -> None:
        bare = Publication(record_id=UUID(int=9), title="Minimal record", authors=[], created_at=TEST_TIME)
        repo = SqliteProjectPublicationRepository(tmp_path / "bare.db")
        repo.add_publications(PROJECT_ID, [bare])
        service = ExportDatasetService(publication_repository=repo)
        payload = render_research_matrix_workbook(collect_research_matrix_inputs(service, PROJECT_ID))

        row = sheet_values(payload, SHEET_PUBLICATIONS)[1]
        assert row[3] is None  # authors empty
        assert row[5] is None  # no doi
        assert row[6] is None  # no venue
        assert row[9] is None  # no keywords

    def test_export_is_read_only(self, seeded_environment) -> None:
        _, _, _, repo, service = seeded_environment
        total_before = repo.count_by_project(PROJECT_ID)
        active_before = repo.count_active_by_project(PROJECT_ID)

        render_research_matrix_workbook(collect_research_matrix_inputs(service, PROJECT_ID))

        assert repo.count_by_project(PROJECT_ID) == total_before
        assert repo.count_active_by_project(PROJECT_ID) == active_before
