-- Migration 0009: Projects Table and Dynamic Backfill for Existing Project Data

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    protocol_version TEXT NOT NULL DEFAULT '1.0',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- Dynamic backfill of DISTINCT project_id from all existing domain tables.
-- Uses project_id as neutral default title when inserting unrecorded existing project IDs.
INSERT OR IGNORE INTO projects (project_id, title, description, protocol_version, status, created_at, updated_at)
SELECT 
    project_id,
    project_id AS title,
    NULL AS description,
    '1.0' AS protocol_version,
    'active' AS status,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM (
    SELECT project_id FROM search_strategies WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
    UNION
    SELECT project_id FROM import_history WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
    UNION
    SELECT project_id FROM normalization_executions WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
    UNION
    SELECT project_id FROM project_publications WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
    UNION
    SELECT project_id FROM duplicate_review_decisions WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
    UNION
    SELECT project_id FROM screening_criteria WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
    UNION
    SELECT project_id FROM screening_decisions WHERE project_id IS NOT NULL AND TRIM(project_id) != ''
);
