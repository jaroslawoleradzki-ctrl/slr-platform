"""Unit tests for deterministic BibTeX serialization (v0.6.1 Slice 1)."""

from uuid import UUID

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import DocumentType, Publication
from app.domain.venue import Venue
from app.providers.import_file.bibtex.mapper import map_bibtex_record
from app.providers.import_file.bibtex.parser import parse_bibtex
from app.services.export.bibtex_writer import (
    assign_citation_keys,
    citation_key_base,
    escape_bibtex_value,
    render_bibtex,
)


def _roundtrip_authors(parsed_entry) -> list[Author]:
    """Re-import one parsed BibTeX entry through the production mapper."""
    return map_bibtex_record(parsed_entry, source="test").authors


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


class TestEscaping:
    def test_literal_braces_are_doubled(self) -> None:
        assert escape_bibtex_value("A {braced} value") == "A {{braced}} value"

    def test_special_characters_are_brace_protected(self) -> None:
        assert escape_bibtex_value("100% & more") == "100{%} {&} more"
        assert escape_bibtex_value("a_b~c^d#e+f") == "a{_}b{~}c{^}d{#}e{+}f"

    def test_control_characters_are_stripped(self) -> None:
        assert escape_bibtex_value("clean\x00\x07value\x1f") == "cleanvalue"


class TestCitationKeys:
    def test_base_key_composition(self) -> None:
        publication = make_rich_publication(UUID(int=1))
        assert citation_key_base(publication) == "smith2024energy"

    def test_non_ascii_characters_are_dropped_from_keys(self) -> None:
        publication = make_rich_publication(
            UUID(int=2), title="Énergy studies", family="Müller", given="Hans", year=2021
        )
        assert citation_key_base(publication) == "mller2021nergy"

    def test_base_falls_back_when_all_segments_empty(self) -> None:
        publication = Publication(record_id=UUID(int=3), title="日本語の研究")
        assert citation_key_base(publication) == "item"

    def test_collisions_get_letter_suffixes_in_record_id_order(self) -> None:
        first = make_rich_publication(UUID("00000000-0000-0000-0000-000000000002"))
        second = make_rich_publication(UUID("00000000-0000-0000-0000-000000000001"))

        assigned = assign_citation_keys([first, second])
        keys_by_record = {
            str(publication.record_id): key for publication, key in zip([first, second], assigned)
        }

        # Assignment depends on ascending record_id, not input order.
        assert keys_by_record[str(first.record_id)] == "smith2024energy-b"
        assert keys_by_record[str(second.record_id)] == "smith2024energy"

    def test_suffixes_progress_alphabetically_for_many_collisions(self) -> None:
        publications = [
            make_rich_publication(UUID(f"00000000-0000-0000-0000-{index:012d}")) for index in range(1, 5)
        ]
        keys = sorted(assign_citation_keys(publications))
        assert keys == ["smith2024energy", "smith2024energy-b", "smith2024energy-c", "smith2024energy-d"]


class TestEntryRendering:
    def test_document_type_mapping_including_fallback(self) -> None:
        conference = make_rich_publication(UUID(int=1), document_type=DocumentType.CONFERENCE_PAPER)
        book = make_rich_publication(UUID(int=2), document_type=DocumentType.BOOK)
        unknown = make_rich_publication(UUID(int=3), document_type=DocumentType.DATASET)
        missing = make_rich_publication(UUID(int=4), document_type=None)

        rendered = render_bibtex([conference, book, unknown, missing])

        assert "@inproceedings{" in rendered
        assert "@book{" in rendered
        assert "@misc{" in rendered  # DATASET and None both fall back to misc

    def test_journal_articles_use_journal_and_others_booktitle(self) -> None:
        article = make_rich_publication(
            UUID(int=1), venue=Venue(name="Journal of Cleaner Production")
        )
        chapter = make_rich_publication(
            UUID(int=2),
            document_type=DocumentType.BOOK_CHAPTER,
            venue=Venue(name="Lean Handbook"),
        )

        article_text = render_bibtex([article])
        chapter_text = render_bibtex([chapter])

        assert "journal = {Journal of Cleaner Production}" in article_text
        assert "booktitle" not in article_text
        assert "booktitle = {Lean Handbook}" in chapter_text
        assert "journal = {" not in chapter_text

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
        rendered = render_bibtex([publication])

        for absent in ("doi", "url", "abstract", "keywords", "language", "journal", "booktitle"):
            assert f"\n  {absent} =" not in rendered

    def test_publisher_is_emitted_from_publication_or_venue(self) -> None:
        with_venue_publisher = make_rich_publication(
            UUID(int=1), venue=Venue(name="Some Journal", publisher="Elsevier")
        )
        text = render_bibtex([with_venue_publisher])
        assert "publisher = {Elsevier}" in text

    def test_unicode_content_passes_through_verbatim(self) -> None:
        publication = make_rich_publication(
            UUID(int=1), title="Wpływ zarządzania lean na efektywność energetyczną"
        )
        rendered = render_bibtex([publication])
        assert "Wpływ zarządzania lean na efektywność energetyczną" in rendered

    def test_authors_joined_with_and_in_family_given_form(self) -> None:
        publication = Publication(
            record_id=UUID(int=1),
            title="Team output",
            authors=[
                Author(display_name="Smith, John", family_name="Smith", given_name="John"),
                Author(display_name="Kowalski, Piotr", family_name="Kowalski", given_name="Piotr"),
            ],
            publication_year=2024,
        )
        rendered = render_bibtex([publication])
        assert "author = {Smith, John and Kowalski, Piotr}" in rendered

    def test_rendering_is_deterministic(self) -> None:
        publications = [make_rich_publication(UUID(int=index)) for index in range(1, 4)]
        assert render_bibtex(publications) == render_bibtex([p for p in publications])


class TestCorporateAuthors:
    """P1-1: unstructured/corporate authors must survive round-trip as one entity."""

    def make_corporate(self, record_id: UUID, name: str) -> Publication:
        return Publication(record_id=record_id, title="Corporate study", authors=[Author(display_name=name)])

    def test_one_corporate_author_is_brace_protected(self) -> None:
        rendered = render_bibtex([self.make_corporate(UUID(int=1), "World Health Organization")])
        assert "author = {{World Health Organization}}" in rendered

    def test_corporate_author_reimports_as_single_author_not_split(self) -> None:
        publication = self.make_corporate(UUID(int=1), "World Health Organization")

        parsed = parse_bibtex(render_bibtex([publication]))

        assert len(parsed[0]["fields"]["author"].split(" and ")) == 1

    def test_corporate_name_containing_and_stays_one_author_on_roundtrip(self) -> None:
        publication = self.make_corporate(UUID(int=1), "Food and Agriculture Organization")

        parsed = parse_bibtex(render_bibtex([publication]))

        authors = _roundtrip_authors(parsed[0])
        assert len(authors) == 1
        assert authors[0].display_name == "Food and Agriculture Organization"

    def test_multiple_corporate_authors_remain_distinct_entities(self) -> None:
        publication = Publication(
            record_id=UUID(int=1),
            title="Multi org study",
            authors=[
                Author(display_name="World Health Organization"),
                Author(display_name="European Commission"),
                Author(display_name="International Energy Agency"),
            ],
        )

        parsed = parse_bibtex(render_bibtex([publication]))

        authors = _roundtrip_authors(parsed[0])
        assert [author.display_name for author in authors] == [
            "World Health Organization",
            "European Commission",
            "International Energy Agency",
        ]

    def test_mixed_personal_and_corporate_authors_round_trip(self) -> None:
        publication = Publication(
            record_id=UUID(int=1),
            title="Mixed authorship study",
            authors=[
                Author(display_name="Doe, John", family_name="Doe", given_name="John"),
                Author(display_name="International Energy Agency"),
                Author(display_name="Smith, Jane", family_name="Smith", given_name="Jane"),
            ],
        )

        parsed = parse_bibtex(render_bibtex([publication]))

        authors = _roundtrip_authors(parsed[0])
        assert len(authors) == 3
        assert (authors[0].family_name, authors[0].given_name) == ("Doe", "John")
        assert authors[1] == Author(display_name="International Energy Agency")
        assert (authors[2].family_name, authors[2].given_name) == ("Smith", "Jane")

    def test_personal_author_formatting_unchanged_by_corporate_protection(self) -> None:
        publication = Publication(
            record_id=UUID(int=1),
            title="Personal only",
            authors=[Author(display_name="Smith, Jane", family_name="Smith", given_name="Jane")],
        )
        rendered = render_bibtex([publication])
        assert "author = {Smith, Jane}" in rendered

    def test_corporate_protection_keeps_output_deterministic(self) -> None:
        publications = [
            Publication(record_id=UUID(int=index), title=f"Study {index}", authors=[Author(display_name="IEA")])
            for index in range(1, 4)
        ]
        assert render_bibtex(publications) == render_bibtex([p for p in publications])

    def test_unicode_corporate_author_round_trips_verbatim(self) -> None:
        publication = self.make_corporate(UUID(int=1), "Polskie Towarzystwo Energetyki Słonecznej")

        parsed = parse_bibtex(render_bibtex([publication]))

        assert parsed[0]["fields"]["author"] == "{Polskie Towarzystwo Energetyki Słonecznej}"


class TestRoundTripThroughImporterParser:
    def test_exported_entries_reparse_with_counts_titles_dois_years(self) -> None:
        publications = [
            make_rich_publication(UUID(int=1)),
            make_rich_publication(
                UUID(int=2),
                title="Kaizen energy impacts",
                year=2019,
                doi="10.1000/kaizen",
                document_type=DocumentType.CONFERENCE_PAPER,
                venue=Venue(name="ICLM Proceedings"),
            ),
        ]

        parsed = parse_bibtex(render_bibtex(publications))

        assert len(parsed) == 2
        by_title = {record["fields"].get("title"): record for record in parsed}
        assert "Energy efficiency of lean production systems" in by_title
        assert "Kaizen energy impacts" in by_title
        kaizen = by_title["Kaizen energy impacts"]
        assert kaizen["entry_type"] == "inproceedings"
        assert kaizen["fields"]["year"] == "2019"
        assert kaizen["fields"]["doi"] == "10.1000/kaizen"

    def test_empty_collection_renders_empty_artifact(self) -> None:
        assert render_bibtex([]) == ""
