import re
import unicodedata
from app.domain.models import PublicationRecord

def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = doi.strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value or None

def normalize_title(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()

def normalize_record(record: PublicationRecord) -> PublicationRecord:
    record.doi = normalize_doi(record.doi)
    record.title_normalized = normalize_title(record.title)
    return record
