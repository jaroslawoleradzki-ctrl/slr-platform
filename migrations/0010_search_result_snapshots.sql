CREATE TABLE IF NOT EXISTS search_result_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    search_run_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    source_id TEXT NOT NULL,
    publication_document TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (project_id, search_run_id, publication_id)
);

CREATE INDEX IF NOT EXISTS idx_search_result_snapshots_project_run
    ON search_result_snapshots(project_id, search_run_id);

CREATE INDEX IF NOT EXISTS idx_search_result_snapshots_project_source
    ON search_result_snapshots(project_id, provider, source_id);
