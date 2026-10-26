"""Read-only dry-run and gated reconciliation for Google Scholar RIS imports.

Default mode is read-only. Production recovery requires explicit ``--execute``
and ``--approved-ids``; this repository's tests never use production data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.normalization import normalize_publication
from app.providers.import_file.ris.mapper import map_ris_record
from app.providers.import_file.ris.parser import parse_ris


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _publication_doi(publication) -> str | None:
    for identifier in publication.identifiers:
        if identifier.type.value == "doi":
            return identifier.value
    return None


def build_reconciliation_report(db_path: str | Path, project_id: str, ris_files: list[str | Path]) -> list[dict]:
    """Build one row per RIS source occurrence without writing to the database."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    existing = con.execute(
        "SELECT record_id, title, publication_year, identifiers FROM project_publications WHERE project_id=?",
        (project_id,),
    ).fetchall()
    con.close()

    existing_dois: dict[str, str] = {}
    existing_titles: dict[str, list[str]] = {}
    for record_id, title, _year, identifiers in existing:
        for identifier in json.loads(identifiers):
            if identifier.get("type") == "doi":
                existing_dois[_normalized(identifier.get("value"))] = record_id
        existing_titles.setdefault(_normalized(title), []).append(record_id)

    rows: list[dict] = []
    for ris_path in ris_files:
        path = Path(ris_path)
        raw = path.read_bytes()
        file_hash = _file_hash(raw)
        records = parse_ris(raw.decode("utf-8-sig"))
        for index, record in enumerate(records, 1):
            publication = normalize_publication(map_ris_record(record, source="ris"))
            doi = _publication_doi(publication)
            normalized_doi = _normalized(doi)
            matched = None
            match_type = "none"
            if normalized_doi and normalized_doi in existing_dois:
                matched = existing_dois[normalized_doi]
                match_type = "exact_doi"
            elif _normalized(publication.title) in existing_titles:
                matched = existing_titles[_normalized(publication.title)][0]
                match_type = "title_candidate"

            if match_type == "exact_doi":
                classification = "confirmed_exact_doi"
                proposed_action = "link_to_existing_canonical"
                review_required = False
            elif match_type == "title_candidate":
                classification = "ambiguous_potential_duplicate"
                proposed_action = "manual_review"
                review_required = True
            elif publication.title.strip():
                classification = "confirmed_distinct_publication"
                proposed_action = "import_as_new_source"
                review_required = False
            else:
                classification = "insufficient_evidence"
                proposed_action = "manual_review"
                review_required = True

            rows.append(
                {
                    "source_file": path.name,
                    "source_file_hash": file_hash,
                    "source_record_index": index,
                    "original_title": publication.title,
                    "original_doi": doi,
                    "normalized_doi": normalized_doi or None,
                    "matched_canonical_publication_id": matched,
                    "match_evidence": match_type,
                    "classification": classification,
                    "proposed_action": proposed_action,
                    "approval_required": review_required,
                    "recovery_status": "not_started",
                }
            )
    return rows


def compute_prisma_reconciliation(db_path: str | Path, project_id: str) -> dict:
    """Derive source-aware PRISMA accounting from persisted state (read-only)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    source_records = con.execute(
        "SELECT COUNT(*) FROM import_source_records WHERE project_id=?",
        (project_id,),
    ).fetchone()[0]
    exact_doi_links = con.execute(
        "SELECT COUNT(*) FROM import_skip_audit WHERE project_id=? AND match_type='exact_doi'",
        (project_id,),
    ).fetchone()[0]
    canonical_active = con.execute(
        "SELECT COUNT(*) FROM project_publications WHERE project_id=? AND superseded_by IS NULL",
        (project_id,),
    ).fetchone()[0]
    con.close()
    return {
        "source_records_identified": source_records,
        "exact_doi_duplicates_linked": exact_doi_links,
        "active_canonical_publications": canonical_active,
        "canonical_equals_source_minus_duplicates": canonical_active
        == max(0, source_records - exact_doi_links),
    }


def apply_approved_recovery(
    db_path: str | Path,
    project_id: str,
    report: list[dict],
    approved_source_ids: set[str],
) -> int:
    """Apply only explicitly approved rows; idempotent by deterministic publication ID.

    This function is implemented for tests and requires an explicit approval set.
    It is never called by the CLI without ``--execute``.
    """
    con = sqlite3.connect(db_path)
    recovered = 0
    try:
        con.execute("BEGIN IMMEDIATE")
        for row in report:
            occurrence_id = f"{row['source_file_hash']}:{row['source_record_index']}"
            if occurrence_id not in approved_source_ids:
                continue
            if row["classification"] in {"confirmed_exact_doi", "ambiguous_potential_duplicate", "insufficient_evidence"}:
                continue
            record_id = str(uuid5(NAMESPACE_URL, f"slr:recovery:{project_id}:{occurrence_id}"))
            exists = con.execute(
                "SELECT 1 FROM project_publications WHERE project_id=? AND record_id=?",
                (project_id, record_id),
            ).fetchone()
            if exists:
                continue
            con.execute(
                """INSERT INTO project_publications
                   (project_id, record_id, position, title, title_normalized, publication_year,
                    authors, identifiers, provenance, created_at, document)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    project_id,
                    record_id,
                    0,
                    row["original_title"],
                    _normalized(row["original_title"]),
                    None,
                    json.dumps([]),
                    json.dumps([{"type": "doi", "value": row["original_doi"]}] if row["original_doi"] else []),
                    json.dumps([{"source": "ris", "source_record_id": row["source_file_hash"], "retrieved_at": None}]),
                    "recovery",
                    json.dumps({"title": row["original_title"], "recovery": True}),
                ),
            )
            recovered += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return recovered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--ris", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prisma-output")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved-ids", nargs="*", default=[])
    args = parser.parse_args()

    report = build_reconciliation_report(args.db, args.project, args.ris)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.prisma_output:
        Path(args.prisma_output).write_text(
            json.dumps(compute_prisma_reconciliation(args.db, args.project), indent=2),
            encoding="utf-8",
        )
    if args.execute:
        if not args.approved_ids:
            raise SystemExit("--execute requires explicit --approved-ids")
        recovered = apply_approved_recovery(
            args.db, args.project, report, set(args.approved_ids)
        )
        print(f"Recovered {recovered} approved source record(s)")
    print(f"Wrote {len(report)} rows to {args.output}")


if __name__ == "__main__":
    main()
