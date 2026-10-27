#!/usr/bin/env python3
"""Proportionate migration-safety guard for SLR Platform CI.

Rules:
- an existing migration file may not be modified, renamed, or deleted;
- an added migration may contain destructive SQL only when it carries the
  explicit marker ``migration-safety: approved-destructive``.

The check compares the current commit with a base ref. It does not connect to
any database and does not execute SQL.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_BASE_REF = "origin/development"
MIGRATION_DIR = "migrations"
APPROVAL_MARKER = "migration-safety: approved-destructive"

DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("DROP TABLE", re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)),
    ("DROP COLUMN", re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE)),
    ("ALTER TABLE ... DROP", re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bDROP\b", re.IGNORECASE)),
    ("DROP INDEX", re.compile(r"\bDROP\s+INDEX\b", re.IGNORECASE)),
    ("TRUNCATE", re.compile(r"\bTRUNCATE\b", re.IGNORECASE)),
    ("DELETE FROM", re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)),
)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _changed_migrations(base_ref: str) -> list[tuple[str, str]]:
    output = _git("diff", "--name-status", f"{base_ref}...HEAD", "--", MIGRATION_DIR)
    changes: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0]
        path = fields[-1]
        changes.append((status, path))
    return changes


def _destructive_hits(text: str) -> list[str]:
    return [name for name, pattern in DESTRUCTIVE_PATTERNS if pattern.search(text)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default=DEFAULT_BASE_REF,
        help=f"Git ref to compare against (default: {DEFAULT_BASE_REF})",
    )
    args = parser.parse_args(argv)

    try:
        changes = _changed_migrations(args.base_ref)
    except RuntimeError as exc:
        print(f"migration-safety: ERROR: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    for status, path in changes:
        if status.startswith(("M", "D", "R")):
            change_name = {"M": "modified", "D": "deleted", "R": "renamed"}.get(status[0], "changed")
            errors.append(
                f"{path}: existing migration was {change_name}; add a new numbered migration instead"
            )
            continue
        if not status.startswith(("A", "C")):
            errors.append(f"{path}: unexpected migration change status {status!r}")
            continue

        source = Path(path)
        if not source.is_file():
            errors.append(f"{path}: added migration is missing from the worktree")
            continue
        text = source.read_text(encoding="utf-8")
        hits = _destructive_hits(text)
        if hits and APPROVAL_MARKER not in text:
            errors.append(
                f"{path}: potentially destructive SQL ({', '.join(hits)}); "
                f"add the marker '{APPROVAL_MARKER}: <reason>' after explicit approval"
            )

    if errors:
        print("migration-safety: FAILED", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if not changes:
        print("migration-safety: PASSED (no migration changes)")
    else:
        print(f"migration-safety: PASSED ({len(changes)} migration change(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
