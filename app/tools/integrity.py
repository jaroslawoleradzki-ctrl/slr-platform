from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.domain.integrity_audit import (
    IntegrityAuditReport,
    IntegrityAuditStatus,
    IntegrityCheckLevel,
)
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import (
    SqliteImportHistoryRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.services.integrity_audit_service import ProjectIntegrityAuditService


def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser for integrity audit CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m app.tools.integrity",
        description="SLR Platform Data Integrity Audit CLI — Run diagnostic checks on a project without GUI.",
    )
    parser.add_argument(
        "project_id",
        metavar="PROJECT_ID",
        help="Target project ID (e.g. lean_energy, ai_architecture).",
    )
    parser.add_argument(
        "-d",
        "--db-path",
        default=None,
        help="Path to SQLite database file. Defaults to SLR_DATABASE_PATH environment variable or data/slr-platform.db.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON report instead of formatted terminal text.",
    )
    return parser


def format_text_report(report: IntegrityAuditReport, db_path: Path) -> str:
    """Format an IntegrityAuditReport into human-readable terminal text."""
    ok_count = sum(1 for c in report.checks if c.level is IntegrityCheckLevel.OK)
    warning_count = sum(1 for c in report.checks if c.level is IntegrityCheckLevel.WARNING)
    error_count = sum(1 for c in report.checks if c.level is IntegrityCheckLevel.ERROR)

    lines: list[str] = [
        "=" * 80,
        "SLR Platform — Data Integrity Audit Report",
        "=" * 80,
        f"Project ID:    {report.project_id}",
        f"Database Path: {db_path}",
        f"Audit Status:  {report.status.value}",
        "",
        "Evaluated Checks:",
        "-" * 80,
    ]

    for check in report.checks:
        if check.level is IntegrityCheckLevel.OK:
            tag = "[PASS]"
        elif check.level is IntegrityCheckLevel.WARNING:
            tag = "[WARN]"
        else:
            tag = "[FAIL]"

        lines.append(f"{tag:<7} {check.code:<28} — {check.message}")
        if check.context and check.level is not IntegrityCheckLevel.OK:
            lines.append(f"        Context: {check.context}")

    lines.extend(
        [
            "",
            "Summary:",
            "-" * 80,
            f"Total Checks:   {len(report.checks)}",
            f"Passed (OK):    {ok_count}",
            f"Warnings:       {warning_count}",
            f"Errors:         {error_count}",
            f"Overall Status: {report.status.value}",
            "=" * 80,
        ]
    )

    return "\n".join(lines)


def format_json_report(report: IntegrityAuditReport, db_path: Path) -> str:
    """Format an IntegrityAuditReport into JSON string."""
    data = report.model_dump(mode="json")
    data["database_path"] = str(db_path)
    return json.dumps(data, indent=2)


def run_cli(args: list[str] | None = None) -> int:
    """Run CLI argument parsing, execute integrity audit, print report, and return exit code."""
    parser = build_parser()
    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    project_id = parsed_args.project_id
    raw_db_path = parsed_args.db_path or os.getenv("SLR_DATABASE_PATH", "data/slr-platform.db")
    db_path = Path(raw_db_path)

    # Instantiate repositories pointing to target SQLite database
    pub_repo = SqliteProjectPublicationRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    norm_repo = SqliteNormalizationExecutionRepository(db_path)
    decision_repo = SqliteDuplicateReviewDecisionRepository(db_path)

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)

    if parsed_args.output_json:
        output = format_json_report(report, db_path)
    else:
        output = format_text_report(report, db_path)

    print(output)

    if report.status is IntegrityAuditStatus.ERROR:
        return 1
    return 0


def main() -> None:
    """CLI entry point for python -m app.tools.integrity."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
