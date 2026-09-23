"""Operator-facing controlled reconciliation command; defaults to dry-run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.services.production_reconciliation_service import (
    ProductionReconciliationService,
    ReconciliationRequest,
    ReconciliationSafetyError,
)


def run_cli(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Allow-list-only production corpus reconciliation")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--import-id", required=True)
    parser.add_argument("--allow-list", required=True, help="JSON array of record UUIDs")
    parser.add_argument("--expected-target-count", required=True, type=int)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--backup-verified", action="store_true")
    ns = parser.parse_args(args)
    request = ReconciliationRequest(
        ns.project,
        UUID(ns.import_id),
        tuple(UUID(value) for value in json.loads(Path(ns.allow_list).read_text())),
        ns.expected_target_count,
        ns.actor,
    )
    try:
        service = ProductionReconciliationService(ns.db_path)
        report = (
            service.execute(request, backup_acknowledged=ns.backup_verified) if ns.execute else service.dry_run(request)
        )
        print(json.dumps(report.as_dict(), indent=2))
        return 0
    except ReconciliationSafetyError as exc:
        print(
            json.dumps({"status": "refused", "code": exc.code, "message": str(exc), "details": exc.details}, indent=2)
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(run_cli())
