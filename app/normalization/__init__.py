from app.normalization.author import AuthorNormalizer, normalize_author
from app.normalization.contracts import Normalizer
from app.normalization.doi import DoiNormalizer, normalize_doi
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
    "TitleNormalizer",
    "normalize_title",
    "AuthorNormalizer",
    "normalize_author",
    "OrcidNormalizer",
    "normalize_orcid",
    "PublicationNormalizer",
    "normalize_publication",
]
