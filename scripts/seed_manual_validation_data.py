#!/usr/bin/env python3
"""Development script for seeding, verifying, and cleaning up controlled manual test data.

Version: 0.2.1 (Manual Validation Dataset)
Target Project: lean_energy
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from uuid import UUID, uuid4

# Ensure app modules can be imported
sys.path.insert(0, str(Path(__file__).parents[1]))

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.normalization.publication import PublicationNormalizer, normalize_publication
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.services.duplicate_group_builder import DuplicateGroupBuilder

PROJECT_ID = "lean_energy"
SEED_TAG = "manual-validation-0.2.1"
DB_PATH = Path(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
BACKUP_PATH = DB_PATH.with_suffix(".db.bak")
MANIFEST_PATH = Path("data/manual_validation_0_2_1_manifest.json")


def ensure_backup() -> Path:
    """Create a safety backup copy of the SQLite database if not already present."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found at {DB_PATH}")
    if not BACKUP_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"[BACKUP] Created safety backup: {BACKUP_PATH}")
    else:
        print(f"[BACKUP] Existing backup found at: {BACKUP_PATH}")
    return BACKUP_PATH


def is_already_seeded(conn: sqlite3.Connection) -> bool:
    """Check whether seed data has already been inserted into the database or manifest exists."""
    if MANIFEST_PATH.exists():
        return True
    row = conn.execute(
        "SELECT COUNT(*) FROM project_publications WHERE project_id = ? AND provenance LIKE ?",
        (PROJECT_ID, f"%{SEED_TAG}%"),
    ).fetchone()
    return int(row[0]) > 0


def run_seed() -> None:
    """Seed 35 controlled records (15 duplicates, 20 normalization cases) into SQLite."""
    ensure_backup()

    repo = SqliteProjectPublicationRepository(DB_PATH)
    source_pubs = repo.get_publications(PROJECT_ID)

    if len(source_pubs) < 35:
        raise ValueError(f"Project '{PROJECT_ID}' has only {len(source_pubs)} publications; required >= 35.")

    conn = sqlite3.connect(DB_PATH)
    if is_already_seeded(conn):
        conn.close()
        print(f"[ERROR] Seed data already exists in database or manifest '{MANIFEST_PATH}' exists. Aborting.")
        sys.exit(1)

    print(f"[SEED] Preparing seed data for project '{PROJECT_ID}' (source pubs before seed: {len(source_pubs)})...")

    # Select 15 source publications for Part A (duplicates)
    part_a_sources = source_pubs[0:15]
    # Select 20 source publications for Part B (normalization)
    part_b_sources = source_pubs[15:35]

    duplicate_manifest: list[dict] = []
    normalization_manifest: list[dict] = []
    new_publications: list[Publication] = []

    # --- PART A: 15 DUPLICATE RECORDS ---
    for idx, src in enumerate(part_a_sources):
        dup_num = idx + 1
        new_id = uuid4()
        doi_val = next((i.value for i in src.identifiers if i.type == IdentifierType.DOI), None)

        # Variations for duplicate pairs
        if dup_num <= 5:
            # Pair 1-5: DOI as URL, Title in uppercase
            new_identifiers = [
                Identifier(type=IdentifierType.DOI, value=f"https://doi.org/{doi_val}") if doi_val else i
                for i in src.identifiers
            ]
            new_title = src.title.upper()
        elif dup_num <= 10:
            # Pair 6-10: Extra spaces in title and author names
            new_identifiers = [
                Identifier(type=IdentifierType.DOI, value=f"doi:{doi_val}") if doi_val else i
                for i in src.identifiers
            ]
            new_title = f"  {src.title}  "
        else:
            # Pair 11-15: Modified title formatting / spaces
            new_identifiers = list(src.identifiers)
            new_title = f"{src.title}."

        new_authors = [
            Author(
                display_name=f"  {a.display_name}  ",
                given_name=a.given_name,
                family_name=a.family_name,
                identifiers=a.identifiers,
            )
            for a in src.authors
        ]

        dup_pub = Publication(
            record_id=new_id,
            title=new_title,
            title_normalized=None,
            abstract=src.abstract,
            authors=new_authors,
            publication_year=src.publication_year,
            identifiers=new_identifiers,
            venue=src.venue,
            publisher=src.publisher,
            document_type=src.document_type,
            language=src.language,
            provenance=[
                ProvenanceEntry(
                    source=SEED_TAG,
                    source_record_id=f"SEED-DUP-{dup_num:02d}",
                )
            ],
            created_at=src.created_at,
        )
        new_publications.append(dup_pub)
        duplicate_manifest.append(
            {
                "case_index": dup_num,
                "source_record_id": str(src.record_id),
                "seed_record_id": str(new_id),
                "strong_identifier_type": "doi",
                "strong_identifier_value": doi_val,
                "variation_note": f"Duplicate pair #{dup_num:02d} created with presentational variations",
            }
        )

    # --- PART B: 20 NORMALIZATION RECORDS ---
    for idx, src in enumerate(part_b_sources):
        norm_num = idx + 1
        new_id = uuid4()
        doi_val = next((i.value for i in src.identifiers if i.type == IdentifierType.DOI), None)

        unnorm_title = src.title
        unnorm_identifiers = list(src.identifiers)
        unnorm_authors = list(src.authors)
        test_category = ""
        before_val = ""
        expected_val = ""

        if norm_num == 1:
            # DOI with https://doi.org/
            test_category = "DOI"
            before_val = f"https://doi.org/{doi_val}"
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 2:
            # DOI with http://dx.doi.org/
            test_category = "DOI"
            before_val = f"http://dx.doi.org/{doi_val}"
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 3:
            # DOI with doi: prefix and UPPERCASE
            test_category = "DOI"
            before_val = f"doi:{doi_val.upper()}" if doi_val else ""
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 4:
            # DOI with spaces and https://dx.doi.org/
            test_category = "DOI"
            before_val = f"  https://dx.doi.org/{doi_val}  " if doi_val else ""
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 5:
            # DOI with UPPERCASE prefix
            test_category = "DOI"
            before_val = f"HTTPS://DOI.ORG/{doi_val.upper()}" if doi_val else ""
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 6:
            # Title with multiple internal spaces
            test_category = "Title"
            before_val = src.title.replace(" ", "   ")
            expected_val = PublicationNormalizer().normalize(src.model_copy(update={"title": before_val})).title_normalized or ""
            unnorm_title = before_val
        elif norm_num == 7:
            # Title with tabs and leading/trailing newlines
            test_category = "Title"
            before_val = f"\t  {src.title}  \n"
            expected_val = PublicationNormalizer().normalize(src.model_copy(update={"title": src.title})).title_normalized or ""
            unnorm_title = before_val
        elif norm_num == 8:
            # Title with unicode em-dash and en-dash
            test_category = "Title"
            before_val = src.title.replace(":", " — ").replace("-", " – ")
            expected_val = PublicationNormalizer().normalize(src.model_copy(update={"title": before_val})).title_normalized or ""
            unnorm_title = before_val
        elif norm_num == 9:
            # Title with punctuation and uppercase
            test_category = "Title"
            before_val = f"{src.title.upper()}!!!"
            expected_val = PublicationNormalizer().normalize(src.model_copy(update={"title": before_val})).title_normalized or ""
            unnorm_title = before_val
        elif norm_num == 10:
            # Title with tabs and multiple spaces
            test_category = "Title"
            before_val = f"\tA   Systematic  Review:  {src.title}\t"
            expected_val = PublicationNormalizer().normalize(src.model_copy(update={"title": before_val})).title_normalized or ""
            unnorm_title = before_val
        elif norm_num == 11:
            # Author display_name with multiple internal spaces
            test_category = "Author"
            before_val = "Smith,   John   P."
            expected_val = "Smith, John P."
            unnorm_authors = [Author(display_name=before_val)]
        elif norm_num == 12:
            # Author given_name and family_name with leading/trailing spaces
            test_category = "Author"
            before_val = "given='  Piotr  ', family=' Kowalski '"
            expected_val = "given='Piotr', family='Kowalski'"
            unnorm_authors = [Author(display_name="Piotr Kowalski", given_name="  Piotr  ", family_name=" Kowalski ")]
        elif norm_num == 13:
            # Author ORCID URL
            test_category = "Author"
            before_val = "http://orcid.org/0000-0002-1825-0097"
            expected_val = "0000-0002-1825-0097"
            unnorm_authors = [
                Author(
                    display_name="Test Author",
                    identifiers=[Identifier(type=IdentifierType.ORCID, value=before_val)],
                )
            ]
        elif norm_num == 14:
            # Author ORCID URL ending in lowercase 'x'
            test_category = "Author"
            before_val = "https://orcid.org/0000-0001-2345-678x"
            expected_val = "0000-0001-2345-678X"
            unnorm_authors = [
                Author(
                    display_name="Test Author 2",
                    identifiers=[Identifier(type=IdentifierType.ORCID, value=before_val)],
                )
            ]
        elif norm_num == 15:
            # Author display_name with tabs/newlines
            test_category = "Author"
            before_val = "\tAlefari,\n   Mudhafar\t"
            expected_val = "Alefari, Mudhafar"
            unnorm_authors = [Author(display_name=before_val)]
        elif norm_num == 16:
            # Publication ORCID identifier with http://orcid.org/
            test_category = "Publication ORCID"
            before_val = "http://orcid.org/0000-0003-1234-5678"
            expected_val = "0000-0003-1234-5678"
            unnorm_identifiers = [
                i for i in src.identifiers if i.type != IdentifierType.ORCID
            ] + [Identifier(type=IdentifierType.ORCID, value=before_val)]
        elif norm_num == 17:
            # Publication ORCID identifier with trailing slash
            test_category = "Publication ORCID"
            before_val = "https://orcid.org/0000-0003-9876-5432/"
            expected_val = "0000-0003-9876-5432"
            unnorm_identifiers = [
                i for i in src.identifiers if i.type != IdentifierType.ORCID
            ] + [Identifier(type=IdentifierType.ORCID, value=before_val)]
        elif norm_num == 18:
            # Publication DOI identifier with http://doi.org/
            test_category = "Publication DOI"
            before_val = f"http://doi.org/{doi_val}" if doi_val else ""
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 19:
            # Publication DOI identifier with doi: and uppercase
            test_category = "Publication DOI"
            before_val = f"doi:{doi_val.upper()}" if doi_val else ""
            expected_val = doi_val.lower() if doi_val else ""
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=before_val)]
        elif norm_num == 20:
            # Combined unnormalized DOI URL and Title spaces
            test_category = "Combined DOI & Title"
            before_val = f"  https://doi.org/{doi_val}  |  {src.title.upper()}  " if doi_val else ""
            expected_val = f"doi={doi_val.lower() if doi_val else ''}"
            unnorm_title = f"   {src.title.upper()}   "
            unnorm_identifiers = [Identifier(type=IdentifierType.DOI, value=f"https://doi.org/{doi_val}")]

        norm_pub = Publication(
            record_id=new_id,
            title=unnorm_title,
            title_normalized=None,  # Not normalized yet prior to running normalization process!
            abstract=src.abstract,
            authors=unnorm_authors,
            publication_year=src.publication_year,
            identifiers=unnorm_identifiers,
            venue=src.venue,
            publisher=src.publisher,
            document_type=src.document_type,
            language=src.language,
            provenance=[
                ProvenanceEntry(
                    source=SEED_TAG,
                    source_record_id=f"SEED-NORM-{norm_num:02d}",
                )
            ],
            created_at=src.created_at,
        )
        new_publications.append(norm_pub)
        normalization_manifest.append(
            {
                "case_index": norm_num,
                "category": test_category,
                "source_record_id": str(src.record_id),
                "seed_record_id": str(new_id),
                "before_value": before_val,
                "expected_after_value": expected_val,
            }
        )

    # Execute insert inside a single transaction
    try:
        with conn:
            # Fetch next position
            row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM project_publications WHERE project_id = ?",
                (PROJECT_ID,),
            ).fetchone()
            base_position = int(row[0])

            for offset, pub in enumerate(new_publications):
                document = pub.model_dump(mode="json")
                conn.execute(
                    """
                    INSERT INTO project_publications (
                        project_id, record_id, position, title, title_normalized,
                        publication_year, authors, identifiers, provenance, created_at,
                        document
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        PROJECT_ID,
                        str(pub.record_id),
                        base_position + offset,
                        pub.title,
                        pub.title_normalized,
                        pub.publication_year,
                        json.dumps(document["authors"], ensure_ascii=False),
                        json.dumps(document["identifiers"], ensure_ascii=False),
                        json.dumps(document["provenance"], ensure_ascii=False),
                        pub.created_at.isoformat(),
                        json.dumps(document, ensure_ascii=False),
                    ),
                )
    except Exception as exc:
        conn.close()
        print(f"[ERROR] Transaction failed during seed insertion: {exc}. Rollback performed.")
        sys.exit(1)

    conn.close()

    # Save manifest JSON
    manifest_data = {
        "project_id": PROJECT_ID,
        "seed_tag": SEED_TAG,
        "database_path": str(DB_PATH),
        "backup_path": str(BACKUP_PATH),
        "source_publications_count_before": len(source_pubs),
        "total_seeded_records": len(new_publications),
        "duplicate_cases_count": len(duplicate_manifest),
        "normalization_cases_count": len(normalization_manifest),
        "duplicate_cases": duplicate_manifest,
        "normalization_cases": normalization_manifest,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[SUCCESS] Seeded {len(new_publications)} records into '{PROJECT_ID}' successfully.")
    print(f"[MANIFEST] Saved manifest to: {MANIFEST_PATH}")


def run_verify() -> None:
    """Verify and report on the 35 seeded records, candidate duplicate groups, and normalization states."""
    if not DB_PATH.exists():
        print(f"[ERROR] Database file not found at {DB_PATH}")
        sys.exit(1)

    repo = SqliteProjectPublicationRepository(DB_PATH)
    all_pubs = repo.get_publications(PROJECT_ID)

    seed_pubs = [
        p for p in all_pubs
        if any(prov.source == SEED_TAG for prov in p.provenance)
    ]

    print("=" * 80)
    print("VERIFICATION REPORT — Manual Validation Dataset (v0.2.1)")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Database Path: {DB_PATH.resolve()}")
    print(f"Total Publications in Project: {len(all_pubs)}")
    print(f"Total Seeded Records Found: {len(seed_pubs)}")
    print("=" * 80)

    manifest_data = {}
    if MANIFEST_PATH.exists():
        manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    # Verify Part A: Duplicate Groups
    print("\n--- PART A: 15 CONTROLLED DUPLICATE CASES ---")
    builder = DuplicateGroupBuilder()
    groups = builder.build(all_pubs)
    print(f"Total Candidate Duplicate Groups Detected by Service: {len(groups)}")

    dup_manifest_list = manifest_data.get("duplicate_cases", [])
    for idx, case in enumerate(dup_manifest_list):
        src_id = UUID(case["source_record_id"])
        seed_id = UUID(case["seed_record_id"])
        ident_val = case["strong_identifier_value"]

        # Find matching duplicate group
        matching_group = next(
            (g for g in groups if src_id in g.publication_ids and seed_id in g.publication_ids),
            None,
        )
        status_str = f"DETECTED (Group ID: {matching_group.group_id})" if matching_group else "NOT DETECTED"
        print(
            f"Case #{idx+1:02d} | Source: {src_id} | Seed: {seed_id} | Identifier ({case['strong_identifier_type'].upper()}): {ident_val} | Status: {status_str}"
        )

    # Verify Part B: Normalization Cases
    print("\n--- PART B: 20 NORMALIZATION CASES ---")
    norm_manifest_list = manifest_data.get("normalization_cases", [])
    for idx, case in enumerate(norm_manifest_list):
        seed_id = UUID(case["seed_record_id"])
        seed_pub = next((p for p in seed_pubs if p.record_id == seed_id), None)

        if not seed_pub:
            print(f"Case #{idx+1:02d} | Seed ID: {seed_id} | [ERROR: Record not found in DB]")
            continue

        # Evaluate live normalization using PublicationNormalizer
        normalized_pub = normalize_publication(seed_pub)

        cat = case["category"]
        before_val = case["before_value"]
        expected_val = case["expected_after_value"]

        # Determine actual value in database vs live normalized
        if "DOI" in cat:
            actual_stored = next((i.value for i in seed_pub.identifiers if i.type == IdentifierType.DOI), None)
            actual_normalized = next((i.value for i in normalized_pub.identifiers if i.type == IdentifierType.DOI), None)
        elif "Title" in cat:
            actual_stored = seed_pub.title_normalized
            actual_normalized = normalized_pub.title_normalized
        elif "Author" in cat:
            actual_stored = seed_pub.authors[0].display_name if seed_pub.authors else None
            actual_normalized = normalized_pub.authors[0].display_name if normalized_pub.authors else None
        else:
            actual_stored = seed_pub.title_normalized or (seed_pub.identifiers[0].value if seed_pub.identifiers else None)
            actual_normalized = normalized_pub.title_normalized or (normalized_pub.identifiers[0].value if normalized_pub.identifiers else None)

        print(f"Case #{idx+1:02d} [{cat}] | Seed ID: {seed_id}")
        print(f"   Before Normalization: {before_val}")
        print(f"   Expected Post-Norm:   {expected_val}")
        print(f"   DB Stored TitleNorm:  {actual_stored}")
        print(f"   Live Normalized Val:  {actual_normalized}")


def run_cleanup() -> None:
    """Remove exclusively the 35 seeded records and associated seed-only review decisions."""
    if not DB_PATH.exists():
        print(f"[ERROR] Database file not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    with conn:
        # Get record_ids of seed publications
        rows = conn.execute(
            "SELECT record_id FROM project_publications WHERE project_id = ? AND provenance LIKE ?",
            (PROJECT_ID, f"%{SEED_TAG}%"),
        ).fetchall()
        seed_record_ids = {row[0] for row in rows}

        if not seed_record_ids and MANIFEST_PATH.exists():
            manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            for case in manifest_data.get("duplicate_cases", []) + manifest_data.get("normalization_cases", []):
                seed_record_ids.add(case["seed_record_id"])

        print(f"[CLEANUP] Found {len(seed_record_ids)} seed records to remove from project '{PROJECT_ID}'...")

        if seed_record_ids:
            # Delete 35 seed records
            placeholders = ",".join("?" for _ in seed_record_ids)
            conn.execute(
                f"DELETE FROM project_publications WHERE project_id = ? AND record_id IN ({placeholders})",
                (PROJECT_ID, *seed_record_ids),
            )

        # Remove manifest if present
        if MANIFEST_PATH.exists():
            MANIFEST_PATH.unlink()
            print(f"[CLEANUP] Removed manifest file: {MANIFEST_PATH}")

    conn.close()
    print("[CLEANUP] Successfully cleaned up seed data. Database restored to pre-seed state.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage controlled manual test dataset for v0.2.1.")
    parser.add_argument(
        "action",
        choices=["seed", "verify", "cleanup"],
        help="Action to perform: 'seed' (add 35 test records), 'verify' (check records/groups), 'cleanup' (remove test records).",
    )
    args = parser.parse_args()

    if args.action == "seed":
        run_seed()
    elif args.action == "verify":
        run_verify()
    elif args.action == "cleanup":
        run_cleanup()


if __name__ == "__main__":
    main()
