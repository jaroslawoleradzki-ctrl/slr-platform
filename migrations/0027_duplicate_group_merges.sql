ALTER TABLE project_publications ADD COLUMN superseded_by TEXT DEFAULT NULL;
CREATE INDEX IF NOT EXISTS idx_project_publications_superseded ON project_publications(project_id, superseded_by);
CREATE TABLE IF NOT EXISTS duplicate_group_merges (
    project_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    canonical_record_id TEXT NOT NULL,
    merged_publication_ids TEXT NOT NULL CHECK (json_valid(merged_publication_ids)),
    merged_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'merged' CHECK (status IN ('merged', 'reverted')),
    pre_merge_snapshots TEXT NOT NULL CHECK (json_valid(pre_merge_snapshots)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, group_id)
);
CREATE INDEX IF NOT EXISTS idx_duplicate_group_merges_project ON duplicate_group_merges(project_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_group_merges_canonical ON duplicate_group_merges(project_id, canonical_record_id);
