CREATE TABLE IF NOT EXISTS normalization_executions (
    project_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    processed_records INTEGER NOT NULL CHECK (processed_records >= 0),
    clean_records INTEGER NOT NULL CHECK (clean_records >= 0),
    warnings_count INTEGER NOT NULL CHECK (warnings_count >= 0),
    errors_count INTEGER NOT NULL CHECK (errors_count >= 0),
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    audit_trail TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(audit_trail)),
    rules_applied TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(rules_applied)),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_normalization_executions_completed_at
    ON normalization_executions(completed_at DESC);
