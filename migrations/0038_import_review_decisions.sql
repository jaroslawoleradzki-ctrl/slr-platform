-- v0.7.4: append-only import review decisions.
-- The import_history row, warnings, source records, and skip-audit rows remain
-- immutable audit evidence. This table records the explicit reviewer decision
-- and the exact active publications removed by a safe rejection.

CREATE TABLE IF NOT EXISTS import_review_decisions (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reviewer_id TEXT NOT NULL,
    rationale TEXT,
    decided_at TEXT NOT NULL,
    import_status_at_decision TEXT NOT NULL,
    warning_snapshot_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(warning_snapshot_json)),
    affected_source_record_ids_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(affected_source_record_ids_json)),
    affected_publication_ids_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(affected_publication_ids_json)),
    removed_publication_snapshots_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(removed_publication_snapshots_json)),
    deleted_publication_count INTEGER NOT NULL DEFAULT 0 CHECK (deleted_publication_count >= 0),
    retained_source_record_count INTEGER NOT NULL DEFAULT 0 CHECK (retained_source_record_count >= 0),
    prisma_treatment TEXT NOT NULL,
    UNIQUE (project_id, import_id)
);

CREATE INDEX IF NOT EXISTS idx_import_review_decisions_project
    ON import_review_decisions(project_id, decided_at);
CREATE INDEX IF NOT EXISTS idx_import_review_decisions_decision
    ON import_review_decisions(project_id, decision);
