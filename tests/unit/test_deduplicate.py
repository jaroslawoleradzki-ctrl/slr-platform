from app.core.models import PublicationRecord
from app.modules.deduplicate.service import deduplicate_by_doi

def test_deduplicate_by_doi():
    records = [
        PublicationRecord(title="A", doi="10.1/a"),
        PublicationRecord(title="A2", doi="10.1/a"),
        PublicationRecord(title="B", doi="10.1/b"),
    ]
    unique, duplicates = deduplicate_by_doi(records)
    assert len(unique) == 2
    assert len(duplicates) == 1
