-- Migration 0026: Synthesis Snapshots (Task 10.7)

-- Immutable, reproducible synthesis snapshot artifacts.
-- Append-only: snapshots are created once and never updated or deleted
-- through the application. Project hard-deletes cascade to snapshots.
CREATE TABLE IF NOT EXISTS synthesis_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    actor TEXT NOT NULL,
    extraction_dataset_hash TEXT NOT NULL,
    classification_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_synthesis_snapshot_project_version UNIQUE (project_id, version)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_snapshots_proj ON synthesis_snapshots(project_id, version);
