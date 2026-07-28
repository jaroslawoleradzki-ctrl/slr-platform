from app.domain.models import PublicationRecord
from app.normalization.doi import normalize_doi as normalize_doi
from app.normalization.title import normalize_title as normalize_title


def normalize_record(record: PublicationRecord) -> PublicationRecord:
    record.doi = normalize_doi(record.doi)
    record.title_normalized = normalize_title(record.title)
    return record
