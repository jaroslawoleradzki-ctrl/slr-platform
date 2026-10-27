from app.normalization.author import AuthorNormalizer, normalize_author
from app.normalization.contracts import Normalizer
from app.normalization.doi import (
    DoiNormalizer,
    is_valid_doi,
    normalize_doi,
    normalize_doi_strict,
)
from app.normalization.language import LanguageNormalizer, normalize_language
from app.normalization.orcid import OrcidNormalizer, normalize_orcid
from app.normalization.publication import (
    PublicationNormalizer,
    normalize_publication,
)
from app.normalization.title import TitleNormalizer, normalize_title

__all__ = [
    "Normalizer",
    "DoiNormalizer",
    "normalize_doi",
    "normalize_doi_strict",
    "is_valid_doi",
    "TitleNormalizer",
    "normalize_title",
    "AuthorNormalizer",
    "normalize_author",
    "OrcidNormalizer",
    "normalize_orcid",
    "LanguageNormalizer",
    "normalize_language",
    "PublicationNormalizer",
    "normalize_publication",
]
