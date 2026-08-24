from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.normalization.author import normalize_author
from app.normalization.doi import normalize_doi
from app.normalization.language import normalize_language
from app.normalization.orcid import normalize_orcid
from app.normalization.title import normalize_title


def _normalize_identifier(identifier: Identifier) -> Identifier:
    normalized_value: str | None = None
    if identifier.type is IdentifierType.DOI:
        normalized_value = normalize_doi(identifier.value)
    elif identifier.type is IdentifierType.ORCID:
        normalized_value = normalize_orcid(identifier.value)

    return identifier.model_copy(
        update={
            "value": (
                normalized_value
                if normalized_value is not None
                else identifier.value
            )
        },
        deep=True,
    )


def _normalize_author(author: Author) -> Author:
    normalized = normalize_author(author)
    return normalized.model_copy(
        update={
            "identifiers": [
                _normalize_identifier(identifier)
                for identifier in normalized.identifiers
            ]
        },
        deep=True,
    )


class PublicationNormalizer:
    """Compose canonical value normalizers for one complete publication."""

    def normalize(self, value: Publication) -> Publication:
        return value.model_copy(
            update={
                "title_normalized": normalize_title(value.title),
                "authors": [_normalize_author(author) for author in value.authors],
                "identifiers": [
                    _normalize_identifier(identifier)
                    for identifier in value.identifiers
                ],
                "language": normalize_language(value.language),
            },
            deep=True,
        )


publication_normalizer = PublicationNormalizer()


def normalize_publication(value: Publication) -> Publication:
    return publication_normalizer.normalize(value)
