-- Migration 0021: Analytical Relations Persistence (Task 10.3)

CREATE TABLE IF NOT EXISTS synthesis_analytical_relations (
    relation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    publication_id TEXT NOT NULL,
    latest_revision_id TEXT NOT NULL,
    group_item_id TEXT NOT NULL,
    item_index INTEGER NOT NULL DEFAULT 1,
    source_practice TEXT NOT NULL,
    analytical_lean_category_id TEXT,
    source_effect TEXT NOT NULL,
    analytical_energy_category_id TEXT,
    direction TEXT NOT NULL CHECK (direction IN ('positive', 'negative', 'no_effect', 'mixed', 'cannot_determine')),
    magnitude REAL,
    original_unit TEXT,
    transformed_value REAL,
    transformed_unit TEXT,
    conversion_rule TEXT,
    evidence_character TEXT NOT NULL CHECK (evidence_character IN ('empirical', 'qualitative', 'estimated', 'postulated')),
    context_summary TEXT,
    approval_state TEXT NOT NULL CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_synthesis_relation_group_item UNIQUE (project_id, group_item_id)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_relations_proj_cats ON synthesis_analytical_relations(project_id, analytical_lean_category_id, analytical_energy_category_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_relations_pub ON synthesis_analytical_relations(project_id, publication_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_relations_group_item ON synthesis_analytical_relations(project_id, group_item_id);
