"""Read-only dry-run reconciliation for Google Scholar RIS imports.

Usage:
  python scripts/ris_import_reconciliation.py --db data/slr-platform.db \
      --project lean-green-phd-d05d3d --ris GS01.ris ... --output report.json

The script never writes to the database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from app.providers.import_file.ris.parser import parse_ris
from app.providers.import_file.ris.mapper import map_ris_record
from app.normalization import normalize_publication


def _source_key(title, authors, year, doi):
    return hashlib.sha256(
        "|".join([title.strip().casefold(), ",".join(authors), str(year or ""), (doi or "").casefold()]).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--ris", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    existing = con.execute(
        "SELECT record_id, title, publication_year, identifiers, provenance FROM project_publications WHERE project_id=?",
        (args.project,),
    ).fetchall()
    existing_dois = {}
    existing_titles = {}
    for rid, title, year, ids, prov in existing:
        for ident in json.loads(ids):
            if ident.get("type") == "doi":
                existing_dois[ident.get("value", "").casefold()] = rid
        existing_titles.setdefault(title.strip().casefold(), []).append(rid)

    rows = []
    index = 0
    for ris_path in args.ris:
        content = Path(ris_path).read_text(encoding="utf-8-sig")
        records = parse_ris(content)
        for i, record in enumerate(records, 1):
            pub = normalize_publication(map_ris_record(record, source="ris"))
            doi = None
            for ident in pub.identifiers:
                if ident.type.value == "doi":
                    doi = ident.value
            matched = None
            match_type = "none"
            if doi and doi.casefold() in existing_dois:
                matched = existing_dois[doi.casefold()]
                match_type = "exact_doi"
            elif not doi and pub.title.strip().casefold() in existing_titles:
                matched = existing_titles[pub.title.strip().casefold()][0]
                match_type = "title_candidate"
            rows.append(
                {
                    "source_file": Path(ris_path).name,
                    "source_record_index": i,
                    "title": pub.title,
                    "doi": doi,
                    "publication_year": pub.publication_year,
                    "matched_publication_id": matched,
                    "match_type": match_type,
                    "proposed_action": "link_to_existing" if match_type == "exact_doi" else "import_and_review",
                    "review_required": match_type != "exact_doi",
                }
            )
            index += 1

    Path(args.output).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
PY
echo created