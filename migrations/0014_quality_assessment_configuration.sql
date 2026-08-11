-- Migration 0014: Quality Assessment Project Configuration & Tool Lifecycle

-- 1. Add is_active lifecycle metadata column to quality_assessment_tools
ALTER TABLE quality_assessment_tools ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1));

-- 2. Active quality assessment template configuration for a project
CREATE TABLE IF NOT EXISTS project_quality_assessment_configurations (
    project_id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL REFERENCES quality_assessment_tools(tool_id) ON DELETE RESTRICT,
    template_id TEXT NOT NULL REFERENCES quality_assessment_templates(template_id) ON DELETE RESTRICT,
    configured_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_project_qa_config_tool_tmpl
ON project_quality_assessment_configurations(tool_id, template_id);
