CREATE TABLE import_history_new (
    import_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'file',
    filename TEXT,
    format TEXT,
    provider TEXT,
    query TEXT,
    records_count INTEGER NOT NULL CHECK (records_count >= 0),
    total_available INTEGER,
    status TEXT NOT NULL,
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    fingerprint TEXT
);

INSERT INTO import_history_new (
    import_id, project_id, source_type, filename, format, records_count,
    status, warnings, created_at
)
SELECT import_id, project_id, 'file', filename, format, records_count,
       status, warnings, created_at
FROM import_history;

DROP TABLE import_history;
ALTER TABLE import_history_new RENAME TO import_history;

CREATE INDEX IF NOT EXISTS idx_import_history_project_created
    ON import_history(project_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_import_history_project_fingerprint
    ON import_history(project_id, fingerprint)
    WHERE fingerprint IS NOT NULL;
