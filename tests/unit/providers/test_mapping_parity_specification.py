from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class MappingRequirement(StrEnum):
    REQUIRED = "Required"
    PROVIDER_DATA_DEPENDENT = "Provider-data-dependent"
    GENERATED = "Generated"
    DEFERRED = "Deferred"


class MappingSupport(StrEnum):
    YES = "Yes"
    PARTIAL = "Partial"
    NO = "No"
    PROVIDER_DEPENDENT = "Provider-dependent"
    GENERATED = "Generated"
    DEFERRED = "Deferred"


@dataclass(frozen=True)
class MappingCapability:
    field: str
    requirement: MappingRequirement
    openalex: MappingSupport
    crossref: MappingSupport
    semantic_scholar: MappingSupport
    harmonization_target: MappingSupport


R = MappingRequirement
S = MappingSupport

MAPPING_CAPABILITIES = (
    MappingCapability("title", R.REQUIRED, S.YES, S.YES, S.YES, S.YES),
    MappingCapability(
        "abstract", R.PROVIDER_DATA_DEPENDENT, S.NO, S.YES, S.YES, S.PROVIDER_DEPENDENT
    ),
    MappingCapability(
        "authors.display_name",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "authors.given_name",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "authors.family_name",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "authors.identifiers.ORCID",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "authors.affiliations",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "publication_year",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "publication_date",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "identifiers.DOI",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "identifiers.PMID",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.NO,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "identifiers.provider_native",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.NO,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "venue.name",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "venue.type",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.NO,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "venue.identifiers.ISSN",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "publisher",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "document_type",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "language",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "urls",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.YES,
        S.YES,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "keywords",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.NO,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "open_access",
        R.PROVIDER_DATA_DEPENDENT,
        S.NO,
        S.NO,
        S.NO,
        S.PROVIDER_DEPENDENT,
    ),
    MappingCapability(
        "provenance.source", R.REQUIRED, S.YES, S.YES, S.YES, S.YES
    ),
    MappingCapability(
        "provenance.source_record_id", R.REQUIRED, S.YES, S.YES, S.YES, S.YES
    ),
    MappingCapability(
        "provenance.retrieved_at", R.REQUIRED, S.YES, S.YES, S.YES, S.YES
    ),
    MappingCapability(
        "provenance.search_context", R.REQUIRED, S.YES, S.YES, S.YES, S.YES
    ),
    MappingCapability(
        "record_id", R.GENERATED, S.GENERATED, S.GENERATED, S.GENERATED, S.GENERATED
    ),
    MappingCapability(
        "schema_version",
        R.GENERATED,
        S.GENERATED,
        S.GENERATED,
        S.GENERATED,
        S.GENERATED,
    ),
    MappingCapability(
        "title_normalized", R.DEFERRED, S.DEFERRED, S.DEFERRED, S.DEFERRED, S.DEFERRED
    ),
    MappingCapability(
        "created_at", R.GENERATED, S.GENERATED, S.GENERATED, S.GENERATED, S.GENERATED
    ),
)

EXPECTED_FIELDS = {
    "title",
    "abstract",
    "authors.display_name",
    "authors.given_name",
    "authors.family_name",
    "authors.identifiers.ORCID",
    "authors.affiliations",
    "publication_year",
    "publication_date",
    "identifiers.DOI",
    "identifiers.PMID",
    "identifiers.provider_native",
    "venue.name",
    "venue.type",
    "venue.identifiers.ISSN",
    "publisher",
    "document_type",
    "language",
    "urls",
    "keywords",
    "open_access",
    "provenance.source",
    "provenance.source_record_id",
    "provenance.retrieved_at",
    "provenance.search_context",
    "record_id",
    "schema_version",
    "title_normalized",
    "created_at",
}


def _by_field() -> dict[str, MappingCapability]:
    return {capability.field: capability for capability in MAPPING_CAPABILITIES}


def test_specification_covers_all_agreed_canonical_fields() -> None:
    assert {item.field for item in MAPPING_CAPABILITIES} == EXPECTED_FIELDS


def test_specification_field_names_are_unique() -> None:
    fields = [item.field for item in MAPPING_CAPABILITIES]
    assert len(fields) == len(set(fields))


def test_every_field_has_explicit_requirement_provider_baseline_and_target() -> None:
    assert all(isinstance(item.requirement, MappingRequirement) for item in MAPPING_CAPABILITIES)
    assert all(isinstance(item.openalex, MappingSupport) for item in MAPPING_CAPABILITIES)
    assert all(isinstance(item.crossref, MappingSupport) for item in MAPPING_CAPABILITIES)
    assert all(
        isinstance(item.semantic_scholar, MappingSupport)
        for item in MAPPING_CAPABILITIES
    )
    assert all(
        isinstance(item.harmonization_target, MappingSupport)
        for item in MAPPING_CAPABILITIES
    )


def test_title_is_required_and_currently_supported_by_all_providers() -> None:
    title = _by_field()["title"]
    assert title.requirement == R.REQUIRED
    assert (title.openalex, title.crossref, title.semantic_scholar) == (
        S.YES,
        S.YES,
        S.YES,
    )


def test_complete_search_provenance_is_required_and_supported() -> None:
    fields = _by_field()
    provenance_fields = {
        "provenance.source",
        "provenance.source_record_id",
        "provenance.retrieved_at",
        "provenance.search_context",
    }
    for field in provenance_fields:
        capability = fields[field]
        assert capability.requirement == R.REQUIRED
        assert (
            capability.openalex,
            capability.crossref,
            capability.semantic_scholar,
            capability.harmonization_target,
        ) == (S.YES, S.YES, S.YES, S.YES)


def test_generated_metadata_is_not_a_mapper_requirement() -> None:
    fields = _by_field()
    for field in {"record_id", "schema_version", "created_at"}:
        capability = fields[field]
        assert capability.requirement == R.GENERATED
        assert capability.harmonization_target == S.GENERATED


def test_title_normalized_is_deferred() -> None:
    capability = _by_field()["title_normalized"]
    assert capability.requirement == R.DEFERRED
    assert capability.harmonization_target == S.DEFERRED


def test_openalex_gaps_are_explicitly_registered() -> None:
    fields = _by_field()
    openalex_gaps = {
        field
        for field, capability in fields.items()
        if capability.requirement == R.PROVIDER_DATA_DEPENDENT
        and capability.openalex == S.NO
    }
    assert openalex_gaps == {
        "abstract",
        "authors.display_name",
        "authors.given_name",
        "authors.family_name",
        "authors.identifiers.ORCID",
        "authors.affiliations",
        "publication_year",
        "publication_date",
        "identifiers.DOI",
        "identifiers.PMID",
        "identifiers.provider_native",
        "venue.name",
        "venue.type",
        "venue.identifiers.ISSN",
        "publisher",
        "document_type",
        "language",
        "urls",
        "keywords",
        "open_access",
    }


def test_provider_data_dependent_targets_do_not_require_missing_data() -> None:
    for capability in MAPPING_CAPABILITIES:
        if capability.requirement == R.PROVIDER_DATA_DEPENDENT:
            assert capability.harmonization_target == S.PROVIDER_DEPENDENT


def test_documented_matrix_matches_machine_checked_specification() -> None:
    repository_root = Path(__file__).parents[3]
    document = (repository_root / "docs" / "MAPPING_PARITY.md").read_text()
    documented_matrix = {
        cells[0].strip("`"): tuple(cells[1:6])
        for line in document.splitlines()
        if line.startswith("| `")
        if (cells := [cell.strip() for cell in line.strip("|").split("|")])
    }
    expected_matrix = {
        capability.field: (
            capability.requirement.value,
            capability.openalex.value,
            capability.crossref.value,
            capability.semantic_scholar.value,
            capability.harmonization_target.value,
        )
        for capability in MAPPING_CAPABILITIES
    }
    assert documented_matrix == expected_matrix


def test_crossref_and_semantic_scholar_baseline_remains_explicitly_distinct() -> None:
    fields = _by_field()
    assert fields["authors.given_name"].crossref == S.YES
    assert fields["authors.given_name"].semantic_scholar == S.NO
    assert fields["identifiers.PMID"].crossref == S.NO
    assert fields["identifiers.PMID"].semantic_scholar == S.YES
    assert fields["venue.type"].crossref == S.NO
    assert fields["venue.type"].semantic_scholar == S.YES
