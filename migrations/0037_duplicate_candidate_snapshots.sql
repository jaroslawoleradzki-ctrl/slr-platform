-- Immutable snapshots of duplicate candidate group membership.  Dynamic
-- groups may change as imports arrive; decisions are keyed by deterministic
-- group_id and this table preserves the membership observed at review time.

CREATE TABLE IF NOT EXISTS duplicate_candidate_group_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    publication_ids_json TEXT NOT NULL CHECK (json_valid(publication_ids_json)),
    match_type TEXT,
    match_reason TEXT,
    status TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE (project_id, group_id, publication_ids_json)
);

CREATE INDEX IF NOT EXISTS idx_duplicate_candidate_snapshots_project
    ON duplicate_candidate_group_snapshots(project_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_duplicate_candidate_snapshots_group
    ON duplicate_candidate_group_snapshots(project_id, group_id);
