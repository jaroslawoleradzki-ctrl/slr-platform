import re
import unicodedata

from app.domain.models import PublicationRecord
from app.normalization.doi import normalize_doi as normalize_doi


def normalize_title(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_record(record: PublicationRecord) -> PublicationRecord:
    record.doi = normalize_doi(record.doi)
    record.title_normalized = normalize_title(record.title)
    return record
