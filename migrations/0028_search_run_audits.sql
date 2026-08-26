CREATE TABLE IF NOT EXISTS search_run_audits (
    search_run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    canonical_query_id TEXT NOT NULL,
    canonical_version INTEGER NOT NULL CHECK (canonical_version >= 1),
    canonical_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    physical_endpoint TEXT NOT NULL,
    physical_query TEXT NOT NULL,
    translation_lossless INTEGER NOT NULL CHECK (translation_lossless IN (0, 1)),
    translation_warnings TEXT NOT NULL CHECK (json_valid(translation_warnings)),
    retrieved_count INTEGER NOT NULL CHECK (retrieved_count >= 0),
    canonical_accepted_count INTEGER NOT NULL CHECK (canonical_accepted_count >= 0),
    canonical_rejected_count INTEGER NOT NULL CHECK (canonical_rejected_count >= 0),
    canonical_indeterminate_count INTEGER NOT NULL CHECK (canonical_indeterminate_count >= 0),
    deduplicated_count INTEGER NOT NULL CHECK (deduplicated_count >= 0),
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_run_audits_project
    ON search_run_audits(project_id, started_at);
