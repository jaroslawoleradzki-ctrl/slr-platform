from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.normalization import Normalizer

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class LowercaseNormalizer:
    def normalize(self, value: str) -> str:
        return value.casefold()


class ExamplePublicationNormalizer:
    def normalize(self, value: Publication) -> Publication:
        return value.model_copy(
            update={"title_normalized": value.title.casefold()},
        )


def _normalize_one(
    normalizer: Normalizer[InputT, OutputT],
    value: InputT,
) -> OutputT:
    return normalizer.normalize(value)


def _publication() -> Publication:
    return Publication(
        record_id=UUID("11111111-1111-1111-1111-111111111111"),
        title="Lean Manufacturing",
        provenance=[
            ProvenanceEntry(
                source="openalex",
                source_record_id="W1",
            )
        ],
    )


def test_string_normalizer_satisfies_structural_contract() -> None:
    normalizer: Normalizer[str, str] = LowercaseNormalizer()

    assert _normalize_one(normalizer, "Lean ENERGY") == "lean energy"


def test_domain_normalizer_returns_immutable_copy_preserving_identity_fields() -> None:
    original = _publication()
    normalizer: Normalizer[Publication, Publication] = (
        ExamplePublicationNormalizer()
    )

    result = _normalize_one(normalizer, original)

    assert isinstance(result, Publication)
    assert result is not original
    assert result.record_id == original.record_id
    assert result.provenance == original.provenance
    assert result.created_at == original.created_at
    assert result.title == original.title
    assert result.title_normalized == "lean manufacturing"


def test_normalizer_is_deterministic_for_the_same_input() -> None:
    normalizer: Normalizer[str, str] = LowercaseNormalizer()

    first = normalizer.normalize("Lean ENERGY")
    second = normalizer.normalize("Lean ENERGY")

    assert first == second


def test_normalizer_idempotence_specification() -> None:
    normalizer: Normalizer[str, str] = LowercaseNormalizer()
    once = normalizer.normalize("Lean ENERGY")

    assert normalizer.normalize(once) == once


def test_domain_normalizer_does_not_mutate_input() -> None:
    original = _publication()
    original_dump = original.model_dump()

    result = ExamplePublicationNormalizer().normalize(original)

    assert original.model_dump() == original_dump
    assert original.title_normalized is None
    assert result is not original


def test_contract_operates_on_one_value_at_a_time() -> None:
    apply_to_one: Callable[
        [Normalizer[str, str], str],
        str,
    ] = _normalize_one

    assert apply_to_one(LowercaseNormalizer(), "One VALUE") == "one value"
