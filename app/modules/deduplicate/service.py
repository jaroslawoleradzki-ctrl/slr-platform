from app.core.models import PublicationRecord

def deduplicate_by_doi(
    records: list[PublicationRecord],
) -> tuple[list[PublicationRecord], list[PublicationRecord]]:
    unique, duplicates = [], []
    seen: set[str] = set()
    for record in records:
        if record.doi and record.doi in seen:
            duplicates.append(record)
            continue
        if record.doi:
            seen.add(record.doi)
        unique.append(record)
    return unique, duplicates
