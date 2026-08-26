CREATE TABLE IF NOT EXISTS search_run_checkpoints (
    search_run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    cursor TEXT,
    pages_fetched INTEGER NOT NULL DEFAULT 0 CHECK (pages_fetched >= 0),
    fetched_count INTEGER NOT NULL DEFAULT 0 CHECK (fetched_count >= 0),
    canonical_accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (canonical_accepted_count >= 0),
    canonical_rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (canonical_rejected_count >= 0),
    canonical_indeterminate_count INTEGER NOT NULL DEFAULT 0 CHECK (canonical_indeterminate_count >= 0),
    deduplicated_count INTEGER NOT NULL DEFAULT 0 CHECK (deduplicated_count >= 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'partial', 'cancelled', 'failed', 'complete')),
    resumable INTEGER NOT NULL CHECK (resumable IN (0, 1)),
    plan_metadata TEXT CHECK (plan_metadata IS NULL OR json_valid(plan_metadata)),
    warnings TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(warnings)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_run_checkpoints_project
    ON search_run_checkpoints(project_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_search_run_checkpoints_job
    ON search_run_checkpoints(job_id, provider);
