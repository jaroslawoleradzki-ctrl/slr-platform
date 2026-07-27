from app.providers.import_file.base import ImportProvider
from app.providers.import_file.ris.google_scholar import GoogleScholarImportProvider


def _import_with(provider: ImportProvider, content: str) -> list[str]:
    return [publication.title for publication in provider.import_publications(content)]


def test_google_scholar_implements_import_provider_contract() -> None:
    content = "TY  - JOUR\nTI  - Contract Test\nER  - "

    assert _import_with(GoogleScholarImportProvider(), content) == ["Contract Test"]
