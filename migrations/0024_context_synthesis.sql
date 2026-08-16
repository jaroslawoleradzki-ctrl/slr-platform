-- Migration 0024: Context Synthesis (Task 10.5)

CREATE TABLE IF NOT EXISTS synthesis_context_categories (
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    category_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, category_id)
);

CREATE TABLE IF NOT EXISTS synthesis_relation_context_links (
    link_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    analytical_relation_id TEXT NOT NULL,
    group_item_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    latest_revision_id TEXT NOT NULL,
    source_context_text TEXT NOT NULL,
    analytical_context_category_id TEXT,
    context_impact TEXT NOT NULL CHECK (context_impact IN ('ENABLE', 'STRENGTHEN', 'WEAKEN', 'CONDITION')),
    approval_state TEXT NOT NULL CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    approved_by TEXT,
    approved_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_synthesis_relation_context UNIQUE (project_id, analytical_relation_id),
    CONSTRAINT fk_synthesis_context_link_category FOREIGN KEY (project_id, analytical_context_category_id)
        REFERENCES synthesis_context_categories (project_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_context_categories_proj ON synthesis_context_categories(project_id, display_order);
CREATE INDEX IF NOT EXISTS idx_synthesis_context_links_proj ON synthesis_relation_context_links(project_id, context_impact);
CREATE INDEX IF NOT EXISTS idx_synthesis_context_links_rel ON synthesis_relation_context_links(project_id, analytical_relation_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_context_links_pub ON synthesis_relation_context_links(project_id, publication_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_context_links_category ON synthesis_relation_context_links(project_id, analytical_context_category_id);