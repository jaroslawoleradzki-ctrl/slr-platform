CREATE TABLE IF NOT EXISTS import_history (
    import_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    records_count INTEGER NOT NULL CHECK (records_count >= 0),
    status TEXT NOT NULL,
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_import_history_project_created
    ON import_history(project_id, created_at DESC);
