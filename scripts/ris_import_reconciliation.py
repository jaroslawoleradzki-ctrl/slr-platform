"""Read-only reconciliation and researcher-approved recovery for RIS imports.

Default mode builds a dry-run report and never writes project data.  Recovery
requires persisted approvals, a verified database backup, a source manifest and
an explicit execution confirmation.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.normalization import normalize_publication
from app.normalization.doi import normalize_doi_strict
from app.normalization.title import normalize_title, titles_are_similar
from app.providers.import_file.ris.mapper import map_ris_record
from app.providers.import_file.ris.parser import parse_ris
from app.repositories.import_source_record_repository import (
    RecoveryApproval,
    SqliteImportSourceRecordRepository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    SqliteProjectPublicationRepository,
)
from app.services.import_identity import (
    fingerprint_raw_record,
    source_occurrence_id,
)

CLASSIFICATIONS = (
    "confirmed_exact_doi",
    "confirmed_duplicate_verified",
    "ambiguous_potential_duplicate",
    "confirmed_distinct_publication",
    "insufficient_evidence",
)
SIMILAR_TITLE_THRESHOLD = 0.92


@dataclass(frozen=True, slots=True)
class RecoveryExecution:
    recovered_count: int
    skipped_count: int
    outcomes: tuple[dict[str, Any], ...]


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def _file_hash(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _publication_doi(publication: Publication) -> str | None:
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.DOI:
            return normalize_doi_strict(identifier.value)
    return None


def _invalid_doi(publication: Publication) -> str | None:
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.OTHER and identifier.source == "invalid_doi":
            return identifier.value.strip()
    return None


def _first_author(publication: Publication) -> str:
    if not publication.authors:
        return ""
    return _normalized(publication.authors[0].display_name or publication.authors[0].family_name)


def _title_year_author_key(title: str | None, year: int | None, first_author: str) -> str:
    return f"{_normalized(title)}|{year or ''}|{_normalized(first_author)}"


def _connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)


def _read_existing(db_path: str | Path, project_id: str) -> dict[str, Any]:
    con = _connect_readonly(db_path)
    try:
        project = con.execute(
            "SELECT 1 FROM projects WHERE project_id=?", (project_id,)
        ).fetchone()
        if project is None:
            raise ProjectNotFoundError(project_id)
        rows = con.execute(
            """SELECT record_id, title, publication_year, identifiers, authors
               FROM project_publications
               WHERE project_id=? AND superseded_by IS NULL""",
            (project_id,),
        ).fetchall()
        try:
            source_rows = con.execute(
                """SELECT source_record_id, source_filename, source_file_hash,
                          record_fingerprint, source_record_index, title, original_doi,
                          normalized_doi, canonical_publication_id, recovery_status
                   FROM import_source_records WHERE project_id=?""",
                (project_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            source_rows = []
        try:
            skip_rows = con.execute(
                """SELECT source_record_id, source_filename, source_file_hash,
                          record_fingerprint, source_record_index, source_title, source_doi,
                          matched_publication_id, match_type, recovery_status
                   FROM import_skip_audit WHERE project_id=?""",
                (project_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            skip_rows = []
    finally:
        con.close()

    dois: dict[str, str] = {}
    titles: dict[str, list[str]] = {}
    title_year_author: dict[str, str] = {}
    title_list: list[tuple[str, str]] = []
    for record_id, title, year, identifiers_json, authors_json in rows:
        title_key = normalize_title(title) or ""
        if title_key:
            titles.setdefault(title_key, []).append(str(record_id))
            title_list.append((title_key, str(record_id)))
        try:
            identifiers = json.loads(identifiers_json)
        except (TypeError, json.JSONDecodeError):
            identifiers = []
        for identifier in identifiers:
            if identifier.get("type") == "doi":
                doi = normalize_doi_strict(identifier.get("value"))
                if doi:
                    dois.setdefault(doi, str(record_id))
        try:
            authors = json.loads(authors_json)
        except (TypeError, json.JSONDecodeError):
            authors = []
        first_author = ""
        if authors:
            first_author = _normalized(
                authors[0].get("display_name") or authors[0].get("family_name")
            )
        title_year_author.setdefault(
            _title_year_author_key(title_key, year, first_author), str(record_id)
        )

    source_by_id = {
        str(row[0]): {
            "source_record_id": str(row[0]),
            "source_filename": row[1],
            "source_file_hash": row[2],
            "record_fingerprint": row[3],
            "source_record_index": row[4],
            "title": row[5],
            "original_doi": row[6],
            "normalized_doi": row[7],
            "canonical_publication_id": row[8],
            "recovery_status": row[9],
        }
        for row in source_rows
    }
    # Skip rows with an occurrence ID are keyed directly; legacy rows without
    # one are also indexed by (file hash, index) for evidence lookup.
    skip_by_id: dict[str, dict] = {}
    for row in skip_rows:
        payload = {
            "source_record_id": row[0],
            "source_filename": row[1],
            "source_file_hash": row[2],
            "record_fingerprint": row[3],
            "source_record_index": row[4],
            "title": row[5],
            "doi": row[6],
            "matched_publication_id": row[7],
            "match_type": row[8],
            "recovery_status": row[9],
        }
        if row[0]:
            skip_by_id[str(row[0])] = payload
        if row[2] is not None and row[4] is not None:
            skip_by_id[f"{row[2]}:{row[4]}"] = payload
    return {
        "dois": dois,
        "titles": titles,
        "title_year_author": title_year_author,
        "title_list": title_list,
        "source_by_id": source_by_id,
        "skip_by_id": skip_by_id,
    }


def _fallback_publication(record: dict[str, list[str]]) -> tuple[str, str | None, list[str], int | None]:
    title = next((value.strip() for value in record.get("TI", []) if value.strip()), "")
    doi = next((value.strip() for value in record.get("DO", []) if value.strip()), None)
    authors = [value.strip() for value in record.get("AU", []) if value.strip()]
    year: int | None = None
    for tag in ("PY", "Y1"):
        raw = next((value.strip() for value in record.get(tag, []) if value.strip()), None)
        if raw:
            try:
                year = int(raw)
            except ValueError:
                year = None
            break
    return title, doi, authors, year


def _similar_existing(
    title: str,
    title_list: list[tuple[str, str]],
    *,
    exclude: set[str],
) -> tuple[str, str] | None:
    if not title:
        return None
    for candidate, record_id in title_list:
        if record_id in exclude or candidate == title:
            continue
        if titles_are_similar(
            title, candidate, threshold=SIMILAR_TITLE_THRESHOLD
        ):
            return candidate, record_id
    return None


def build_reconciliation_report(
    db_path: str | Path,
    project_id: str,
    ris_files: list[str | Path],
    *,
    source_database: str = "google_scholar_pop",
) -> list[dict]:
    """Build one row per RIS source occurrence without writing project data."""

    existing = _read_existing(db_path, project_id)
    rows: list[dict] = []
    batch_dois: dict[str, str] = {}
    batch_titles: dict[str, str] = {}
    batch_title_year_author: dict[str, str] = {}
    batch_title_list: list[tuple[str, str]] = []
    occurrence_ordinals: dict[str, int] = {}

    for ris_path in ris_files:
        path = Path(ris_path)
        raw = path.read_bytes()
        file_hash = _file_hash(raw)
        try:
            parsed = parse_ris(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            rows.append(
                {
                    "source_file": path.name,
                    "source_file_hash": file_hash,
                    "source_database": source_database,
                    "source_record_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            f"slr:unparsable:{project_id}:{file_hash}",
                        )
                    ),
                    "source_record_index": 0,
                    "record_fingerprint": None,
                    "original_title": "(unparsable RIS file)",
                    "original_doi": None,
                    "normalized_doi": None,
                    "doi_status": "missing",
                    "authors": [],
                    "publication_year": None,
                    "document_type": None,
                    "abstract": None,
                    "matched_canonical_publication_id": None,
                    "matched_source_record_id": None,
                    "match_evidence": "parse_error",
                    "classification": "insufficient_evidence",
                    "proposed_action": "manual_review",
                    "approval_required": True,
                    "review_required": True,
                    "historical_status": "unknown",
                    "historical_evidence": "parse_error",
                    "recovery_status": "not_started",
                    "validation_error": str(exc),
                }
            )
            continue

        for index, record in enumerate(parsed, 1):
            fingerprint = fingerprint_raw_record(record)
            ordinal = occurrence_ordinals.get(fingerprint, 0) + 1
            occurrence_ordinals[fingerprint] = ordinal
            occurrence_id = source_occurrence_id(
                project_id=project_id,
                source_label=source_database,
                filename=path.name,
                record_fingerprint=fingerprint,
                ordinal=ordinal,
            )
            validation_error: str | None = None
            try:
                publication = normalize_publication(
                    map_ris_record(record, source="ris", source_database=source_database)
                )
                title = publication.title
                doi = _publication_doi(publication)
                invalid_doi = _invalid_doi(publication)
                authors = [author.display_name for author in publication.authors]
                year = publication.publication_year
                document_type = (
                    publication.document_type.value
                    if publication.document_type
                    else None
                )
                abstract = publication.abstract
                provenance = publication.provenance[0].model_dump(mode="json")
                first_author = _first_author(publication)
            except ValueError as exc:
                validation_error = str(exc)
                title, raw_doi, authors, year = _fallback_publication(record)
                doi = normalize_doi_strict(raw_doi)
                invalid_doi = raw_doi if raw_doi and doi is None else None
                document_type = None
                abstract = None
                provenance = {
                    "source": source_database,
                    "source_record_id": raw_doi or title,
                }
                first_author = _normalized(authors[0]) if authors else ""
                publication = None

            title_key = normalize_title(title) or ""
            doi_status = "valid" if doi else "invalid" if invalid_doi else "missing"
            matched_canonical: str | None = None
            matched_source: str | None = None
            evidence = "none"
            historical_status = "unknown"
            historical_evidence = "none"
            review_required = False

            source_state = existing["source_by_id"].get(occurrence_id)
            skip_state = existing["skip_by_id"].get(occurrence_id)
            if skip_state is None:
                skip_state = existing["skip_by_id"].get(f"{file_hash}:{index}")

            if source_state is not None:
                matched_canonical = source_state.get("canonical_publication_id")
                historical_status = "imported"
                historical_evidence = "source_record"
                classification = "confirmed_duplicate_verified"
                evidence = "persisted_source_record"
                proposed_action = "already_imported"
                if doi and doi in existing["dois"]:
                    classification = "confirmed_exact_doi"
                    evidence = "persisted_source_record_exact_doi"
            elif skip_state is not None:
                matched_canonical = skip_state.get("matched_publication_id")
                historical_status = "skipped"
                historical_evidence = "skip_audit"
                if skip_state.get("match_type") == "exact_doi":
                    classification = "confirmed_exact_doi"
                    evidence = "persisted_skip_audit_exact_doi"
                else:
                    classification = "confirmed_duplicate_verified"
                    evidence = f"persisted_skip_audit_{skip_state.get('match_type')}"
                proposed_action = "link_to_existing_canonical"
            elif doi and doi in existing["dois"]:
                matched_canonical = existing["dois"][doi]
                classification = "confirmed_exact_doi"
                evidence = "canonical_exact_doi"
                historical_status = "imported"
                historical_evidence = "canonical_match"
                proposed_action = "link_to_existing_canonical"
            elif doi and doi in batch_dois:
                matched_source = batch_dois[doi]
                classification = "confirmed_exact_doi"
                evidence = "same_batch_exact_doi"
                historical_status = "unknown"
                historical_evidence = "same_batch"
                proposed_action = "link_to_existing_canonical"
            else:
                tya_key = _title_year_author_key(title_key, year, first_author)
                if tya_key in existing["title_year_author"]:
                    matched_canonical = existing["title_year_author"][tya_key]
                    classification = "confirmed_duplicate_verified"
                    evidence = "title_year_first_author_match"
                    historical_status = "imported"
                    historical_evidence = "canonical_match"
                    proposed_action = "link_to_existing_canonical"
                elif tya_key in batch_title_year_author:
                    matched_source = batch_title_year_author[tya_key]
                    classification = "confirmed_duplicate_verified"
                    evidence = "same_batch_title_year_author"
                    historical_status = "unknown"
                    historical_evidence = "same_batch"
                    proposed_action = "link_to_existing_canonical"
                elif title_key and title_key in existing["titles"]:
                    matched_canonical = existing["titles"][title_key][0]
                    classification = "ambiguous_potential_duplicate"
                    evidence = "canonical_title_match"
                    historical_status = "imported"
                    historical_evidence = "canonical_title_match"
                    proposed_action = "manual_review"
                    review_required = True
                elif title_key and title_key in batch_titles:
                    matched_source = batch_titles[title_key]
                    classification = "ambiguous_potential_duplicate"
                    evidence = "same_batch_title_match"
                    historical_status = "unknown"
                    historical_evidence = "same_batch"
                    proposed_action = "manual_review"
                    review_required = True
                else:
                    similar = _similar_existing(
                        title_key,
                        existing["title_list"] + batch_title_list,
                        exclude=set(),
                    )
                    if similar is not None:
                        matched_source = similar[1]
                        classification = "ambiguous_potential_duplicate"
                        evidence = "similar_title"
                        historical_status = "unknown"
                        historical_evidence = "similar_title"
                        proposed_action = "manual_review"
                        review_required = True
                    elif title_key:
                        classification = "confirmed_distinct_publication"
                        evidence = "no_match"
                        historical_status = "skipped"
                        historical_evidence = "inferred_missing_from_corpus"
                        proposed_action = "recover_as_new_source"
                        review_required = True
                    else:
                        classification = "insufficient_evidence"
                        evidence = "missing_title"
                        historical_status = "unknown"
                        historical_evidence = "insufficient_metadata"
                        proposed_action = "manual_review"
                        review_required = True

            if validation_error is not None and classification == "confirmed_distinct_publication":
                classification = "insufficient_evidence"
                proposed_action = "manual_review"
                review_required = True
                evidence = "malformed_record"

            if doi:
                batch_dois.setdefault(doi, occurrence_id)
            if title_key:
                batch_titles.setdefault(title_key, occurrence_id)
                batch_title_list.append((title_key, occurrence_id))
                batch_title_year_author.setdefault(
                    _title_year_author_key(title_key, year, first_author), occurrence_id
                )
            rows.append(
                {
                    "source_file": path.name,
                    "source_file_hash": file_hash,
                    "source_database": source_database,
                    "source_record_id": occurrence_id,
                    "source_record_index": index,
                    "record_fingerprint": fingerprint,
                    "original_title": title,
                    "original_doi": invalid_doi or doi,
                    "normalized_doi": doi,
                    "doi_status": doi_status,
                    "authors": authors,
                    "publication_year": year,
                    "document_type": document_type,
                    "abstract": abstract,
                    "matched_canonical_publication_id": matched_canonical,
                    "matched_source_record_id": matched_source,
                    "match_evidence": evidence,
                    "classification": classification,
                    "proposed_action": proposed_action,
                    "approval_required": review_required,
                    "review_required": review_required,
                    "historical_status": historical_status,
                    "historical_evidence": historical_evidence,
                    "recovery_status": (
                        source_state.get("recovery_status")
                        if source_state is not None
                        else "not_started"
                    ),
                    "validation_error": validation_error,
                }
            )

    return rows


def _project_exists(db_path: str | Path, project_id: str) -> bool:
    con = _connect_readonly(db_path)
    try:
        return (
            con.execute(
                "SELECT 1 FROM projects WHERE project_id=?", (project_id,)
            ).fetchone()
            is not None
        )
    finally:
        con.close()


def record_recovery_approvals(
    db_path: str | Path,
    project_id: str,
    source_record_ids: list[str],
    *,
    reviewer_identity: str,
    decision: str,
    rationale: str,
    allowed_source_ids: set[str] | None = None,
    now: datetime | None = None,
) -> list[RecoveryApproval]:
    """Persist researcher decisions for explicitly listed source occurrences."""

    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be 'approved' or 'rejected'")
    if not reviewer_identity.strip():
        raise ValueError("reviewer identity is required")
    if not rationale.strip():
        raise ValueError("rationale is required")
    if not _project_exists(db_path, project_id):
        raise ProjectNotFoundError(project_id)
    if not source_record_ids:
        raise ValueError("at least one source occurrence ID is required")
    if allowed_source_ids is not None:
        unknown = set(source_record_ids) - set(allowed_source_ids)
        if unknown:
            raise ValueError(f"source occurrence IDs not present in report: {sorted(unknown)}")
    repo = SqliteImportSourceRecordRepository(db_path)
    timestamp = now or datetime.now(timezone.utc)
    approvals: list[RecoveryApproval] = []
    for source_record_id in sorted(set(source_record_ids)):
        approval = RecoveryApproval(
            approval_id=str(uuid4()),
            project_id=project_id,
            source_record_id=source_record_id,
            reviewer_identity=reviewer_identity.strip(),
            decision=decision,
            rationale=rationale.strip(),
            approved_at=timestamp,
        )
        repo.save_recovery_approval(approval)
        approvals.append(approval)
    return approvals


def _publication_from_row(row: dict, project_id: str) -> Publication:
    record_id = uuid5(
        NAMESPACE_URL,
        f"slr:recovery:{project_id}:{row['source_record_id']}",
    )
    identifiers: list[Identifier] = []
    if row.get("normalized_doi"):
        identifiers.append(
            Identifier(type=IdentifierType.DOI, value=row["normalized_doi"])
        )
    elif row.get("original_doi"):
        identifiers.append(
            Identifier(
                type=IdentifierType.OTHER,
                value=row["original_doi"],
                source="invalid_doi",
            )
        )
    authors = []
    from app.domain.author import Author

    for name in row.get("authors") or []:
        authors.append(Author(display_name=name))
    provenance = [
        ProvenanceEntry(
            source=row.get("source_database") or "ris",
            source_record_id=row["source_record_id"],
            retrieved_at=datetime.now(timezone.utc),
            transformation="historical_recovery",
        )
    ]
    publication = Publication(
        record_id=record_id,
        title=row["original_title"],
        authors=authors,
        publication_year=row.get("publication_year"),
        identifiers=identifiers,
        provenance=provenance,
        abstract=row.get("abstract"),
        language=None,
        created_at=datetime.now(timezone.utc),
    )
    if row.get("document_type"):
        from app.domain.publication import DocumentType

        try:
            publication = publication.model_copy(
                update={"document_type": DocumentType(row["document_type"])}
            )
        except ValueError:
            pass
    return normalize_publication(publication)


def _validate_backup(backup_path: str | Path) -> None:
    path = Path(backup_path)
    if not path.is_file():
        raise ValueError("backup file does not exist")
    with open(path, "rb") as handle:
        if handle.read(16) != b"SQLite format 3\x00":
            raise ValueError("backup is not a SQLite database")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup integrity check failed")
    finally:
        con.close()


def _validate_manifest(
    manifest_path: str | Path,
    report: list[dict],
    *,
    expected_total: int | None = None,
) -> None:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("manifest must contain a 'files' list")
    report_counts: dict[str, int] = {}
    for row in report:
        file_name = row["source_file"]
        report_counts[file_name] = report_counts.get(file_name, 0) + 1
    manifest_counts: dict[str, int] = {}
    for entry in files:
        name = str(entry.get("filename", ""))
        count = int(entry.get("count", -1))
        if not name or count < 0:
            raise ValueError("manifest entries need filename and non-negative count")
        manifest_counts[name] = count
    if manifest_counts != report_counts:
        raise ValueError(
            f"manifest/report count mismatch: manifest={manifest_counts} report={report_counts}"
        )
    total = int(manifest.get("total", sum(manifest_counts.values())))
    if total != len(report):
        raise ValueError("manifest total does not match report rows")
    if expected_total is not None and total != expected_total:
        raise ValueError("manifest total does not match expected total")


def execute_approved_recovery(
    db_path: str | Path,
    project_id: str,
    report: list[dict],
    *,
    backup_path: str | Path,
    manifest_path: str | Path,
    confirmation: str,
    expected_total: int | None = None,
    now: datetime | None = None,
) -> RecoveryExecution:
    """Execute only persisted approvals, atomically and idempotently."""

    if confirmation != "RECOVER":
        raise ValueError("explicit confirmation 'RECOVER' is required")
    _validate_backup(backup_path)
    _validate_manifest(manifest_path, report, expected_total=expected_total)
    if not _project_exists(db_path, project_id):
        raise ProjectNotFoundError(project_id)
    repo = SqliteImportSourceRecordRepository(db_path)
    approvals = [
        item
        for item in repo.list_recovery_approvals(project_id)
        if item.decision == "approved"
    ]
    if not approvals:
        raise ValueError("no persisted approved recovery decisions")
    by_id: dict[str, dict] = {}
    for row in report:
        source_id = row["source_record_id"]
        if source_id in by_id:
            raise ValueError(f"duplicate source occurrence ID in report: {source_id}")
        by_id[source_id] = row

    executions: list[dict] = []
    recovered = 0
    skipped = 0
    canonical_repo = SqliteProjectPublicationRepository(db_path)
    timestamp = now or datetime.now(timezone.utc)

    # Preflight the whole approved set before any write.
    existing_rows = canonical_repo.get_publications(project_id)
    existing_dois = {
        normalize_doi_strict(identifier.value)
        for publication in existing_rows
        for identifier in publication.identifiers
        if identifier.type is IdentifierType.DOI
    }
    existing_dois.discard(None)
    planned_dois: set[str] = set()
    to_recover: list[tuple[RecoveryApproval, dict]] = []
    for approval in approvals:
        row = by_id.get(approval.source_record_id)
        if row is None:
            raise ValueError(
                f"approval references a source occurrence absent from the report: {approval.source_record_id}"
            )
        if approval.recovery_executed_at is not None:
            executions.append(
                {
                    "source_record_id": approval.source_record_id,
                    "outcome": "already_executed",
                    "canonical_publication_id": approval.canonical_publication_id,
                }
            )
            skipped += 1
            continue
        if row["classification"] != "confirmed_distinct_publication":
            executions.append(
                {
                    "source_record_id": approval.source_record_id,
                    "outcome": "not_recoverable",
                    "classification": row["classification"],
                }
            )
            skipped += 1
            continue
        doi = row.get("normalized_doi")
        if doi:
            if doi in existing_dois or doi in planned_dois:
                raise ValueError(f"duplicate DOI recovery rejected: {doi}")
            planned_dois.add(doi)
        to_recover.append((approval, row))

    recovered_ids: list[tuple[RecoveryApproval, dict, str]] = []
    with sqlite3.connect(db_path) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            for approval, row in to_recover:
                publication = _publication_from_row(row, project_id)
                canonical_id = str(publication.record_id)
                existing = connection.execute(
                    "SELECT 1 FROM project_publications WHERE project_id=? AND record_id=?",
                    (project_id, canonical_id),
                ).fetchone()
                if existing is None:
                    canonical_repo.add_publications(
                        project_id, [publication], connection=connection
                    )
                source_record = repo.find_source_record_by_id(
                    project_id, approval.source_record_id
                )
                recovery_import_id = uuid5(
                    NAMESPACE_URL,
                    f"slr:recovery-import:{project_id}:{row['source_file_hash']}:{approval.source_record_id}",
                )
                if source_record is None:
                    from app.repositories.import_source_record_repository import (
                        ImportSourceRecord,
                    )

                    repo.create_source_record(
                        ImportSourceRecord(
                            source_record_id=approval.source_record_id,
                            project_id=project_id,
                            import_id=recovery_import_id,
                            source_filename=row["source_file"],
                            source_file_hash=row["source_file_hash"],
                            record_fingerprint=row.get("record_fingerprint"),
                            import_format="RIS",
                            source_record_index=int(row["source_record_index"]),
                            title=row["original_title"],
                            publication_year=row.get("publication_year"),
                            original_doi=row.get("original_doi"),
                            normalized_doi=row.get("normalized_doi"),
                            doi_status=row.get("doi_status", "missing"),
                            authors=tuple(row.get("authors") or []),
                            document_type=row.get("document_type"),
                            provenance={
                                "source": "ris",
                                "source_record_id": approval.source_record_id,
                                "transformation": "historical_recovery",
                            },
                            canonical_publication_id=canonical_id,
                            duplicate_match_type="recovered",
                            duplicate_match_reason=(
                                "Researcher-approved historical recovery"
                            ),
                            recovery_status="recovered",
                        ),
                        connection=connection,
                    )
                else:
                    repo.mark_recovered(
                        project_id,
                        approval.source_record_id,
                        canonical_id,
                        connection=connection,
                    )
                repo.record_recovery_execution(
                    approval,
                    executed_at=timestamp,
                    outcome="recovered",
                    canonical_publication_id=canonical_id,
                    detail=f"report classification={row['classification']}",
                    connection=connection,
                )
                recovered_ids.append((approval, row, canonical_id))
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    for approval, row, canonical_id in recovered_ids:
        executions.append(
            {
                "source_record_id": approval.source_record_id,
                "outcome": "recovered",
                "canonical_publication_id": canonical_id,
            }
        )
        recovered += 1
    return RecoveryExecution(
        recovered_count=recovered,
        skipped_count=skipped,
        outcomes=tuple(executions),
    )


def compute_prisma_reconciliation(db_path: str | Path, project_id: str) -> dict:
    """Derive source-aware accounting from persisted state (read-only)."""

    con = _connect_readonly(db_path)
    try:
        try:
            source_records = con.execute(
                "SELECT COUNT(*) FROM import_source_records WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            exact_doi_links = con.execute(
                "SELECT COUNT(*) FROM import_skip_audit WHERE project_id=? AND match_type='exact_doi'",
                (project_id,),
            ).fetchone()[0]
            repeated = con.execute(
                "SELECT COUNT(*) FROM import_skip_audit WHERE project_id=? AND match_type='repeated_occurrence'",
                (project_id,),
            ).fetchone()[0]
            recovered = con.execute(
                "SELECT COUNT(*) FROM import_source_records WHERE project_id=? AND recovery_status='recovered'",
                (project_id,),
            ).fetchone()[0]
            historical_without_source = con.execute(
                """SELECT COUNT(*) FROM project_publications p
                   WHERE p.project_id=? AND p.superseded_by IS NULL
                     AND NOT EXISTS (
                       SELECT 1 FROM import_source_records s
                       WHERE s.project_id=p.project_id
                         AND s.canonical_publication_id=p.record_id
                     )""",
                (project_id,),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            source_records = exact_doi_links = repeated = recovered = 0
            historical_without_source = 0
        canonical_active = con.execute(
            "SELECT COUNT(*) FROM project_publications WHERE project_id=? AND superseded_by IS NULL",
            (project_id,),
        ).fetchone()[0]
    finally:
        con.close()
    return {
        "source_records_identified": source_records + repeated,
        "persisted_source_records": source_records,
        "exact_doi_duplicates_linked": exact_doi_links,
        "repeated_source_occurrences": repeated,
        "recovered_records": recovered,
        "active_canonical_publications": canonical_active,
        "historical_canonicals_without_source_records": historical_without_source,
        "canonical_equals_source_minus_duplicates": canonical_active
        == max(0, (source_records + repeated) - exact_doi_links - repeated),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--ris", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prisma-output")
    parser.add_argument("--source-database", default="google_scholar_pop")
    parser.add_argument("--approve-source-ids", nargs="*", default=[])
    parser.add_argument("--reviewer")
    parser.add_argument("--rationale")
    parser.add_argument("--decision", choices=("approved", "rejected"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--backup-path")
    parser.add_argument("--manifest")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    report = build_reconciliation_report(
        args.db,
        args.project,
        args.ris,
        source_database=args.source_database,
    )
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if args.prisma_output:
        Path(args.prisma_output).write_text(
            json.dumps(compute_prisma_reconciliation(args.db, args.project), indent=2),
            encoding="utf-8",
        )

    if args.approve_source_ids:
        if not args.reviewer or not args.rationale or not args.decision:
            raise SystemExit(
                "--approve-source-ids requires --reviewer, --rationale and --decision"
            )
        approved = record_recovery_approvals(
            args.db,
            args.project,
            args.approve_source_ids,
            reviewer_identity=args.reviewer,
            decision=args.decision,
            rationale=args.rationale,
            allowed_source_ids={row["source_record_id"] for row in report},
        )
        print(f"Recorded {len(approved)} {args.decision} approval(s)")

    if args.execute:
        if not args.backup_path or not args.manifest:
            raise SystemExit("--execute requires --backup-path and --manifest")
        if args.confirm != "RECOVER":
            raise SystemExit("--execute requires --confirm RECOVER")
        result = execute_approved_recovery(
            args.db,
            args.project,
            report,
            backup_path=args.backup_path,
            manifest_path=args.manifest,
            confirmation=args.confirm,
        )
        print(
            f"Recovered {result.recovered_count} approved source record(s); "
            f"skipped {result.skipped_count}"
        )
    print(f"Wrote {len(report)} rows to {args.output}")


if __name__ == "__main__":
    main()
