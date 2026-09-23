-- Durable idempotency ledger for the deliberately operator-controlled corpus reconciliation.
CREATE TABLE IF NOT EXISTS corpus_reconciliation_runs (
    reconciliation_id TEXT PRIMARY KEY,
    request_fingerprint TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    target_ids TEXT NOT NULL CHECK (json_valid(target_ids)),
    status TEXT NOT NULL CHECK (status IN ('complete')),
    removed_count INTEGER NOT NULL CHECK (removed_count >= 0),
    active_count_after INTEGER NOT NULL CHECK (active_count_after >= 0),
    derived_state_rebuild_required INTEGER NOT NULL DEFAULT 1,
    actor TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_corpus_reconciliation_runs_project
    ON corpus_reconciliation_runs(project_id, completed_at DESC);
