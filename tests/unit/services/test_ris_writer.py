"""Unit tests for deterministic RIS serialization (v0.6.1 Slice 1)."""

from uuid import UUID

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import DocumentType, Publication
from app.domain.venue import Venue
from app.providers.import_file.ris.parser import parse_ris
from app.services.export.ris_writer import render_ris, render_ris_record


def make_rich_publication(
    record_id: UUID,
    title: str = "Energy efficiency of lean production systems",
    *,
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    document_type: DocumentType | None = DocumentType.JOURNAL_ARTICLE,
    venue: Venue | None = None,
    doi: str | None = "10.1000/example",
    url: str | None = None,
    abstract: str | None = None,
    keywords: list[str] | None = None,
    language: str | None = None,
) -> Publication:
    return Publication(
        record_id=record_id,
        title=title,
        authors=[Author(display_name=f"{family}, {given}", family_name=family, given_name=given)],
        publication_year=year,
        document_type=document_type,
        venue=venue,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)] if doi else [],
        urls=[url] if url else [],
        abstract=abstract,
        keywords=keywords or [],
        language=language,
    )


class TestRecordStructure:
    def test_record_starts_with_ty_and_ends_with_er(self) -> None:
        lines = render_ris_record(make_rich_publication(UUID(int=1)))
        assert lines[0].startswith("TY  - ")
        assert lines[-1] == "ER  - "

    def test_document_type_mapping_including_fallbacks(self) -> None:
        mapping = {
            DocumentType.JOURNAL_ARTICLE: "JOUR",
            DocumentType.CONFERENCE_PAPER: "CONF",
            DocumentType.BOOK: "BOOK",
            DocumentType.BOOK_CHAPTER: "CHAP",
            DocumentType.DISSERTATION: "THES",
            DocumentType.REPORT: "RPRT",
            DocumentType.PREPRINT: "UNPB",
            DocumentType.DATASET: "DATA",
        }
        for document_type, expected_tag in mapping.items():
            lines = render_ris_record(make_rich_publication(UUID(int=1), document_type=document_type))
            assert lines[0] == f"TY  - {expected_tag}"

        for fallback_type in (DocumentType.REVIEW, DocumentType.OTHER, None):
            lines = render_ris_record(make_rich_publication(UUID(int=1), document_type=fallback_type))
            assert lines[0] == "TY  - JOUR"

    def test_repeated_author_lines_one_per_value(self) -> None:
        publication = Publication(
            record_id=UUID(int=1),
            title="Team output",
            authors=[
                Author(display_name="Smith, John", family_name="Smith", given_name="John"),
                Author(display_name="Kowalski, Piotr", family_name="Kowalski", given_name="Piotr"),
                Author(display_name="Cher"),
            ],
            publication_year=2024,
        )
        lines = render_ris_record(publication)
        author_lines = [line for line in lines if line.startswith("AU  - ")]
        assert author_lines == ["AU  - Smith, John", "AU  - Kowalski, Piotr", "AU  - Cher"]

    def test_venue_emitted_as_both_jo_and_t2(self) -> None:
        publication = make_rich_publication(UUID(int=1), venue=Venue(name="Journal of Cleaner Production"))
        lines = render_ris_record(publication)
        assert "JO  - Journal of Cleaner Production" in lines
        assert "T2  - Journal of Cleaner Production" in lines

    def test_missing_optional_fields_are_omitted_never_empty(self) -> None:
        publication = make_rich_publication(
            UUID(int=1),
            doi=None,
            url=None,
            abstract=None,
            keywords=[],
            language=None,
            venue=None,
        )
        tags = [line.split("  - ")[0] for line in render_ris_record(publication)]
        for absent in ("JO", "T2", "DO", "UR", "AB", "KW", "LA"):
            assert absent not in tags

    def test_control_characters_are_stripped_from_values(self) -> None:
        publication = make_rich_publication(
            UUID(int=1), title="Polluted\x07\x1ftitle", abstract="Abstract\x00 text"
        )
        rendered = "\n".join(render_ris_record(publication))
        assert "TI  - Pollutedtitle" in rendered
        assert "AB  - Abstract text" in rendered


class TestDocumentRendering:
    def test_crlf_newlines_and_trailing_terminator(self) -> None:
        rendered = render_ris([make_rich_publication(UUID(int=1))])
        assert "\n" in rendered
        assert "\r\n" in rendered
        assert not rendered.replace("\r\n", "").endswith("\n")
        assert rendered.endswith("ER  - \r\n")

    def test_multiple_records_each_terminated_with_er(self) -> None:
        publications = [
            make_rich_publication(UUID(int=1)),
            make_rich_publication(UUID(int=2), title="Second study"),
        ]
        rendered = render_ris(publications)
        assert rendered.count("ER  - \r\n") == 2
        assert rendered.count("TY  - ") == 2

    def test_unicode_content_passes_through_verbatim(self) -> None:
        publication = make_rich_publication(
            UUID(int=1), title="Wpływ zarządzania lean na efektywność energetyczną"
        )
        assert "Wpływ zarządzania lean na efektywność energetyczną" in render_ris([publication])

    def test_rendering_is_deterministic(self) -> None:
        publications = [make_rich_publication(UUID(int=index)) for index in range(1, 4)]
        assert render_ris(publications) == render_ris([p for p in publications])

    def test_empty_collection_renders_empty_artifact(self) -> None:
        assert render_ris([]) == ""


class TestRoundTripThroughImporterParser:
    def test_exported_records_reparse_with_counts_titles_dois_years(self) -> None:
        publications = [
            make_rich_publication(
                UUID(int=1),
                title="Lean energy review",
                year=2021,
                doi="10.1016/j.jclepro.2021.102834",
                keywords=["lean", "energy"],
                language="en",
            ),
            make_rich_publication(
                UUID(int=2),
                title="Kaizen energy impacts",
                year=2019,
                doi=None,
                document_type=DocumentType.CONFERENCE_PAPER,
                venue=Venue(name="ICLM Proceedings"),
            ),
        ]

        records = parse_ris(render_ris(publications))

        assert len(records) == 2
        by_title = {record["TI"][0]: record for record in records}
        lean = by_title["Lean energy review"]
        kaizen = by_title["Kaizen energy impacts"]

        assert lean["TY"] == ["JOUR"]
        assert lean["PY"] == ["2021"]
        assert lean["DO"] == ["10.1016/j.jclepro.2021.102834"]
        assert lean["KW"] == ["lean", "energy"]
        assert lean["LA"] == ["en"]
        assert kaizen["TY"] == ["CONF"]
        assert kaizen["PY"] == ["2019"]
        assert "DO" not in kaizen
