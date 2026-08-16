-- Migration 0022: Mechanism Synthesis Persistence (Task 10.4)

CREATE TABLE IF NOT EXISTS synthesis_mechanism_categories (
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    category_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, category_id)
);

CREATE TABLE IF NOT EXISTS synthesis_mechanism_pathways (
    pathway_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    analytical_relation_id TEXT NOT NULL,
    group_item_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    latest_revision_id TEXT NOT NULL,
    source_mechanism_text TEXT,
    analytical_mechanism_category_id TEXT,
    is_review_synthesized INTEGER NOT NULL DEFAULT 0,
    approval_state TEXT NOT NULL CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    approved_by TEXT,
    approved_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_synthesis_mechanism_pathway UNIQUE (project_id, analytical_relation_id)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_mechanism_categories_proj ON synthesis_mechanism_categories(project_id, display_order);
CREATE INDEX IF NOT EXISTS idx_synthesis_mechanism_pathways_proj ON synthesis_mechanism_pathways(project_id, analytical_mechanism_category_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_mechanism_pathways_rel ON synthesis_mechanism_pathways(project_id, analytical_relation_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_mechanism_pathways_group_item ON synthesis_mechanism_pathways(project_id, group_item_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_mechanism_pathways_pub ON synthesis_mechanism_pathways(project_id, publication_id);
