import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock,
  Plus,
  Quote,
  RefreshCw,
  SlidersHorizontal,
  Tag,
  Trash2,
  X,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  ContextCategory,
  ContextImpact,
  ContextWorkspaceData,
} from '../../types/synthesis';

interface ContextWorkspaceProps {
  projectId: string;
}

const IMPACT_OPTIONS: ContextImpact[] = ['ENABLE', 'STRENGTHEN', 'WEAKEN', 'CONDITION'];

export const ContextWorkspace: React.FC<ContextWorkspaceProps> = ({ projectId }) => {
  const [workspaceData, setWorkspaceData] = useState<ContextWorkspaceData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Category Modal State
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState<boolean>(false);
  const [editingCategory, setEditingCategory] = useState<ContextCategory | null>(null);
  const [categoryFormId, setCategoryFormId] = useState<string>('');
  const [categoryFormName, setCategoryFormName] = useState<string>('');
  const [categoryFormDesc, setCategoryFormDesc] = useState<string>('');
  const [categoryFormError, setCategoryFormError] = useState<string | null>(null);

  // Assignment action state
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingSave, setPendingSave] = useState<Record<string, boolean>>({});

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setActionError(null);
      const data = await synthesisApi.getContextWorkspace(projectId);
      setWorkspaceData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load context synthesis workspace.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const stats = workspaceData?.stats || {
    context_evidence_count: 0,
    distinct_publication_count: 0,
    distinct_analytical_relation_count: 0,
    distinct_mechanism_pathway_count: 0,
  };

  const handleOpenCategoryModal = (cat?: ContextCategory) => {
    if (cat) {
      setEditingCategory(cat);
      setCategoryFormId(cat.category_id);
      setCategoryFormName(cat.name);
      setCategoryFormDesc(cat.description || '');
    } else {
      setEditingCategory(null);
      setCategoryFormId('');
      setCategoryFormName('');
      setCategoryFormDesc('');
    }
    setCategoryFormError(null);
    setIsCategoryModalOpen(true);
  };

  const handleSaveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!categoryFormName.trim()) {
      setCategoryFormError('Category name is required.');
      return;
    }

    try {
      if (editingCategory) {
        await synthesisApi.updateContextCategory(projectId, editingCategory.category_id, {
          name: categoryFormName.trim(),
          description: categoryFormDesc.trim() || null,
        });
      } else {
        const id = categoryFormId.trim() || categoryFormName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
        await synthesisApi.createContextCategory(projectId, {
          category_id: id,
          name: categoryFormName.trim(),
          description: categoryFormDesc.trim() || null,
        });
      }
      setIsCategoryModalOpen(false);
      await loadData();
    } catch (err: any) {
      setCategoryFormError(err.message || 'Failed to save context category.');
    }
  };

  const handleDeleteCategory = async (categoryId: string) => {
    if (!window.confirm(`Are you sure you want to delete context category '${categoryId}'? Linked assignments will be unclassified.`)) {
      return;
    }
    try {
      await synthesisApi.deleteContextCategory(projectId, categoryId);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to delete context category.');
    }
  };

  const handleSaveAssignment = async (
    assignmentId: string,
    categoryId: string,
    impact: ContextImpact
  ) => {
    setPendingSave((prev) => ({ ...prev, [assignmentId]: true }));
    setActionError(null);
    try {
      const assignment = workspaceData?.assignments.find((a) => a.assignment_id === assignmentId);
      if (!assignment) {
        throw new Error('Assignment not found.');
      }
      if (categoryId) {
        await synthesisApi.remapContextAssignment(projectId, assignmentId, {
          category_id: categoryId,
          context_impact: impact,
        });
      } else {
        // Clearing the category unassigns the link entirely.
        if (!window.confirm('Remove this context assignment?')) {
          return;
        }
        await synthesisApi.unassignContext(projectId, assignmentId);
      }
      await loadData();
    } catch (err: any) {
      setActionError(err.message || 'Failed to save context assignment.');
    } finally {
      setPendingSave((prev) => ({ ...prev, [assignmentId]: false }));
    }
  };

  const handleUnassign = async (assignmentId: string) => {
    if (!window.confirm('Remove this context assignment?')) {
      return;
    }
    setActionError(null);
    try {
      await synthesisApi.unassignContext(projectId, assignmentId);
      await loadData();
    } catch (err: any) {
      setActionError(err.message || 'Failed to unassign context.');
    }
  };

  const filteredAssignments = useMemo(() => {
    if (!workspaceData) return [];
    return workspaceData.assignments;
  }, [workspaceData]);

  if (loading && !workspaceData) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
        <div>Loading Context Synthesis Workspace...</div>
      </div>
    );
  }

  if (error && !workspaceData) {
    return (
      <div
        style={{
          padding: '24px',
          backgroundColor: 'var(--status-error-bg)',
          border: '1px solid var(--status-error-border)',
          borderRadius: 'var(--radius-lg)',
          color: 'var(--status-error-text)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
          <AlertCircle size={20} />
          <span>Error loading context synthesis workspace</span>
        </div>
        <p style={{ marginTop: '8px', fontSize: '0.9rem' }}>{error}</p>
        <button
          onClick={loadData}
          style={{
            marginTop: '12px',
            padding: '6px 12px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
          }}
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Workspace Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <SlidersHorizontal size={22} style={{ color: 'var(--accent-primary)' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-primary)' }}>
              Context Synthesis & Moderating Factors
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Researcher-controlled classification of contextual evidence per analytical relation.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            data-testid="add-context-category-btn"
            onClick={() => handleOpenCategoryModal()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: 'var(--accent-primary)',
              color: '#ffffff',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
            }}
          >
            <Plus size={15} /> Add Context Category
          </button>
          <button
            type="button"
            data-testid="refresh-context-btn"
            onClick={loadData}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '0.85rem',
            }}
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {actionError && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--status-error-bg)',
            border: '1px solid var(--status-error-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--status-error-text)',
            fontSize: '0.85rem',
          }}
        >
          {actionError}
        </div>
      )}

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Context Evidence
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.context_evidence_count}
          </div>
        </div>
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Publications
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.distinct_publication_count}
          </div>
        </div>
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Relations
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.distinct_analytical_relation_count}
          </div>
        </div>
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Categorized
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.distinct_mechanism_pathway_count}
          </div>
        </div>
      </div>

      {/* Context Categories Vocabulary */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <Tag size={16} style={{ color: 'var(--accent-primary)' }} />
          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
            Context Taxonomy ({workspaceData?.categories?.length ?? 0})
          </span>
        </div>
        {!workspaceData?.categories || workspaceData.categories.length === 0 ? (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0' }}>
            No context categories defined yet. Click "Add Context Category" to start building your moderating-factor taxonomy.
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {workspaceData.categories.map((cat) => (
              <div
                key={cat.category_id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-app)',
                  fontSize: '0.85rem',
                }}
              >
                <span style={{ fontWeight: 500 }}>{cat.name}</span>
                <button
                  type="button"
                  onClick={() => handleOpenCategoryModal(cat)}
                  style={{
                    border: 'none',
                    background: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '2px',
                    fontSize: '0.75rem',
                  }}
                  title="Edit category"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteCategory(cat.category_id)}
                  style={{
                    border: 'none',
                    background: 'none',
                    color: 'var(--status-error-text)',
                    cursor: 'pointer',
                    padding: '2px',
                  }}
                  title="Delete category"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Assignments */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '16px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <BookOpen size={16} style={{ color: 'var(--accent-primary)' }} />
          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
            Context Assignments
          </span>
          <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {filteredAssignments.length} evidence item(s)
          </span>
        </div>

        {filteredAssignments.length === 0 ? (
          <div style={{ padding: '16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            No contextual evidence has been assigned yet. Create context categories and assign evidence once
            analytical relations exist.
          </div>
        ) : (
          <div>
            {filteredAssignments.map((assignment) => (
              <div
                key={assignment.assignment_id}
                data-testid={`context-assignment-${assignment.assignment_id}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ flex: '1 1 240px', minWidth: '200px' }}>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                    {assignment.source_context_text || (
                      <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        No moderating conditions extracted for this relation
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    <Quote size={11} style={{ verticalAlign: 'middle', marginRight: '2px' }} />
                    relation {assignment.analytical_relation_id.slice(0, 8)} &middot; pub{' '}
                    {assignment.publication_id.slice(0, 8)}
                  </div>
                </div>

                <select
                  data-testid={`context-category-${assignment.assignment_id}`}
                  value={assignment.analytical_context_category_id || ''}
                  onChange={(e) => {
                    void handleSaveAssignment(assignment.assignment_id, e.target.value, assignment.context_impact);
                  }}
                  style={{
                    padding: '6px 8px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    maxWidth: '220px',
                  }}
                >
                  <option value="">-- Select Context Factor --</option>
                  {(workspaceData?.categories || []).map((cat) => (
                    <option key={cat.category_id} value={cat.category_id}>
                      {cat.name}
                    </option>
                  ))}
                </select>

                <select
                  data-testid={`context-impact-${assignment.assignment_id}`}
                  value={assignment.context_impact}
                  onChange={(e) => {
                    void handleSaveAssignment(
                      assignment.assignment_id,
                      assignment.analytical_context_category_id || '',
                      e.target.value as ContextImpact
                    );
                  }}
                  style={{
                    padding: '6px 8px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                  }}
                >
                  {IMPACT_OPTIONS.map((impact) => (
                    <option key={impact} value={impact}>
                      {impact}
                    </option>
                  ))}
                </select>

                {pendingSave[assignment.assignment_id] && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Saving...</span>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
                  {assignment.analytical_context_category_id ? (
                    <span
                      data-testid={`context-state-${assignment.assignment_id}`}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--status-success-bg)',
                        color: 'var(--status-success-text)',
                      }}
                    >
                      <CheckCircle2 size={12} />
                      {assignment.approval_state}
                    </span>
                  ) : (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--status-warning-bg)',
                        color: 'var(--status-warning-text)',
                      }}
                    >
                      <Clock size={12} />
                      unassigned
                    </span>
                  )}
                  <button
                    type="button"
                    data-testid={`unassign-context-${assignment.assignment_id}`}
                    onClick={() => handleUnassign(assignment.assignment_id)}
                    title="Unassign context evidence"
                    style={{
                      border: 'none',
                      background: 'none',
                      color: 'var(--status-error-text)',
                      cursor: 'pointer',
                      padding: '4px',
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Category Modal */}
      {isCategoryModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              padding: '24px',
              maxWidth: '480px',
              width: '100%',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '16px',
              }}
            >
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--text-primary)' }}>
                {editingCategory ? 'Edit Context Category' : 'Add Context Category'}
              </h3>
              <button
                type="button"
                onClick={() => setIsCategoryModalOpen(false)}
                style={{ border: 'none', background: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveCategory} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {!editingCategory && (
                <div>
                  <label
                    htmlFor="context-category-id-input"
                    style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}
                  >
                    Category ID
                  </label>
                  <input
                    id="context-category-id-input"
                    data-testid="context-category-id-input"
                    value={categoryFormId}
                    onChange={(e) => setCategoryFormId(e.target.value)}
                    placeholder="e.g. market_competition"
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--bg-surface)',
                      color: 'var(--text-primary)',
                      fontSize: '0.9rem',
                    }}
                  />
                </div>
              )}
              <div>
                <label
                  htmlFor="context-category-name-input"
                  style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}
                >
                  Name
                </label>
                <input
                  id="context-category-name-input"
                  data-testid="context-category-name-input"
                  value={categoryFormName}
                  onChange={(e) => setCategoryFormName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    fontSize: '0.9rem',
                  }}
                />
              </div>
              <div>
                <label
                  htmlFor="context-category-desc-input"
                  style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}
                >
                  Description
                </label>
                <textarea
                  id="context-category-desc-input"
                  data-testid="context-category-desc-input"
                  value={categoryFormDesc}
                  onChange={(e) => setCategoryFormDesc(e.target.value)}
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    fontSize: '0.9rem',
                    resize: 'vertical',
                  }}
                />
              </div>
              {categoryFormError && (
                <div style={{ color: 'var(--status-error-text)', fontSize: '0.8rem' }}>{categoryFormError}</div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '4px' }}>
                <button
                  type="button"
                  onClick={() => setIsCategoryModalOpen(false)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="save-context-category-submit-btn"
                  style={{
                    padding: '6px 16px',
                    borderRadius: 'var(--radius-md)',
                    border: 'none',
                    backgroundColor: 'var(--accent-primary)',
                    color: '#ffffff',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  {editingCategory ? 'Save Changes' : 'Create Category'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};