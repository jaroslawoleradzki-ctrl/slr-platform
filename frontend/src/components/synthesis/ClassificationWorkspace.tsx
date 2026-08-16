import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Edit2,
  FolderPlus,
  HelpCircle,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  X,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  Category,
  ClassifiedSourceTerm,
  TerminologyClassificationWorkspace,
  TermType,
} from '../../types/synthesis';

interface ClassificationWorkspaceProps {
  projectId: string;
}

export const ClassificationWorkspace: React.FC<ClassificationWorkspaceProps> = ({ projectId }) => {
  const [workspace, setWorkspace] = useState<TerminologyClassificationWorkspace | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'lean' | 'energy'>('lean');
  const [filterText, setFilterText] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'unmapped' | 'pending' | 'approved'>('all');
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState<string>('reviewer-1');

  // Category management modal state
  const [showCategoryModal, setShowCategoryModal] = useState<boolean>(false);
  const [categoryFormId, setCategoryFormId] = useState<string>('');
  const [categoryFormName, setCategoryFormName] = useState<string>('');
  const [categoryFormDesc, setCategoryFormDesc] = useState<string>('');
  const [categoryFormOrder, setCategoryFormOrder] = useState<number>(0);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  const fetchWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await synthesisApi.getWorkspace(projectId);
      setWorkspace(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load classification workspace';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchWorkspace();
  }, [fetchWorkspace]);

  const handleCategorySelectChange = async (
    termType: TermType,
    sourceValue: string,
    analyticalCategoryId: string
  ) => {
    if (!analyticalCategoryId) return;
    const saveKey = `${termType}_${sourceValue}`;
    setSavingKey(saveKey);
    try {
      await synthesisApi.setTermMapping(projectId, {
        term_type: termType,
        source_value: sourceValue,
        analytical_category_id: analyticalCategoryId,
      });
      await fetchWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save mapping';
      setError(msg);
    } finally {
      setSavingKey(null);
    }
  };

  const handleApproveMapping = async (termType: TermType, sourceValue: string) => {
    const saveKey = `${termType}_${sourceValue}`;
    setSavingKey(saveKey);
    try {
      await synthesisApi.approveTermMapping(projectId, {
        term_type: termType,
        source_value: sourceValue,
        reviewer_id: reviewerId,
      });
      await fetchWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to approve mapping';
      setError(msg);
    } finally {
      setSavingKey(null);
    }
  };

  const handleSaveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    setCategoryError(null);
    try {
      const termType: TermType = activeTab === 'lean' ? 'lean_practice' : 'energy_effect';
      if (editingCategory) {
        if (termType === 'lean_practice') {
          await synthesisApi.updateLeanCategory(projectId, editingCategory.category_id, {
            name: categoryFormName,
            description: categoryFormDesc || null,
            display_order: categoryFormOrder,
          });
        } else {
          await synthesisApi.updateEnergyCategory(projectId, editingCategory.category_id, {
            name: categoryFormName,
            description: categoryFormDesc || null,
            display_order: categoryFormOrder,
          });
        }
      } else {
        if (termType === 'lean_practice') {
          await synthesisApi.createLeanCategory(projectId, {
            category_id: categoryFormId,
            name: categoryFormName,
            description: categoryFormDesc || null,
            display_order: categoryFormOrder,
          });
        } else {
          await synthesisApi.createEnergyCategory(projectId, {
            category_id: categoryFormId,
            name: categoryFormName,
            description: categoryFormDesc || null,
            display_order: categoryFormOrder,
          });
        }
      }
      setShowCategoryModal(false);
      resetCategoryForm();
      await fetchWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save category';
      setCategoryError(msg);
    }
  };

  const handleDeleteCategory = async (categoryId: string) => {
    if (!window.confirm(`Delete analytical category '${categoryId}'?`)) return;
    try {
      const termType: TermType = activeTab === 'lean' ? 'lean_practice' : 'energy_effect';
      if (termType === 'lean_practice') {
        await synthesisApi.deleteLeanCategory(projectId, categoryId);
      } else {
        await synthesisApi.deleteEnergyCategory(projectId, categoryId);
      }
      await fetchWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete category';
      setError(msg);
    }
  };

  const resetCategoryForm = () => {
    setCategoryFormId('');
    setCategoryFormName('');
    setCategoryFormDesc('');
    setCategoryFormOrder(0);
    setEditingCategory(null);
    setCategoryError(null);
  };

  const openCreateModal = () => {
    resetCategoryForm();
    setShowCategoryModal(true);
  };

  const openEditModal = (cat: Category) => {
    setEditingCategory(cat);
    setCategoryFormId(cat.category_id);
    setCategoryFormName(cat.name);
    setCategoryFormDesc(cat.description || '');
    setCategoryFormOrder(cat.display_order);
    setShowCategoryModal(true);
  };

  const currentTerms: ClassifiedSourceTerm[] = useMemo(() => {
    if (!workspace) return [];
    return activeTab === 'lean' ? workspace.lean_terms : workspace.energy_terms;
  }, [workspace, activeTab]);

  const currentCategories: Category[] = useMemo(() => {
    if (!workspace) return [];
    return activeTab === 'lean' ? workspace.lean_categories : workspace.energy_categories;
  }, [workspace, activeTab]);

  const filteredTerms = useMemo(() => {
    return currentTerms.filter((term) => {
      const matchesSearch =
        term.source_value.toLowerCase().includes(filterText.toLowerCase()) ||
        (term.analytical_category_name || '').toLowerCase().includes(filterText.toLowerCase());

      if (!matchesSearch) return false;

      if (statusFilter === 'unmapped') {
        return !term.analytical_category_id;
      }
      if (statusFilter === 'pending') {
        return !!term.analytical_category_id && term.approval_state === 'pending';
      }
      if (statusFilter === 'approved') {
        return term.approval_state === 'approved';
      }
      return true;
    });
  }, [currentTerms, filterText, statusFilter]);

  if (loading && !workspace) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px', gap: '12px' }}>
        <RefreshCw size={24} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
        <span>Loading Terminology Classification Workspace...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Workspace Header Banner */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Tag size={22} style={{ color: 'var(--accent-primary)' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Terminology Classification Workspace</h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '6px', marginBottom: 0 }}>
            Methodological Invariant: <strong>Source Term (Phase 9 Evidence)</strong> is permanently preserved and distinct from{' '}
            <strong>Analytical Category (Researcher Interpretation)</strong>.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            Reviewer:
            <input
              type="text"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              style={{
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                width: '120px',
              }}
            />
          </label>

          <button
            type="button"
            onClick={fetchWorkspace}
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

      {error && (
        <div
          style={{
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid var(--status-error-text)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            color: 'var(--status-error-text)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.85rem',
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Summary KPI Stats */}
      {workspace && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Lean Practice Terms</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>{workspace.stats.total_lean_terms}</div>
          </div>
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Energy Effect Terms</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>{workspace.stats.total_energy_terms}</div>
          </div>
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Classified / Mapped</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
              {workspace.stats.mapped_count} / {workspace.stats.total_terms}{' '}
              <span style={{ fontSize: '0.85rem', fontWeight: 400 }}>
                ({workspace.stats.total_terms > 0 ? Math.round((workspace.stats.mapped_count / workspace.stats.total_terms) * 100) : 0}%)
              </span>
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
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Approved Mappings</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--status-success-text)' }}>
              {workspace.stats.approved_count} / {workspace.stats.total_terms}{' '}
              <span style={{ fontSize: '0.85rem', fontWeight: 400 }}>
                ({workspace.stats.total_terms > 0 ? Math.round((workspace.stats.approved_count / workspace.stats.total_terms) * 100) : 0}%)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main Workspace Tabs and Actions */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}
      >
        {/* Navigation Tabs Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid var(--border-subtle)',
            padding: '8px 16px',
            backgroundColor: 'var(--bg-primary)',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              data-testid="lean-tab-btn"
              onClick={() => setActiveTab('lean')}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                backgroundColor: activeTab === 'lean' ? 'var(--bg-surface)' : 'transparent',
                color: activeTab === 'lean' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'lean' ? 600 : 400,
                cursor: 'pointer',
                fontSize: '0.9rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: activeTab === 'lean' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              <span>1. Lean Practices</span>
              <span
                style={{
                  backgroundColor: 'var(--bg-primary)',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  fontSize: '0.75rem',
                }}
              >
                {workspace?.stats.total_lean_terms || 0}
              </span>
            </button>

            <button
              type="button"
              data-testid="energy-tab-btn"
              onClick={() => setActiveTab('energy')}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                backgroundColor: activeTab === 'energy' ? 'var(--bg-surface)' : 'transparent',
                color: activeTab === 'energy' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'energy' ? 600 : 400,
                cursor: 'pointer',
                fontSize: '0.9rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: activeTab === 'energy' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              <span>2. Energy Effects</span>
              <span
                style={{
                  backgroundColor: 'var(--bg-primary)',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  fontSize: '0.75rem',
                }}
              >
                {workspace?.stats.total_energy_terms || 0}
              </span>
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              onClick={openCreateModal}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                backgroundColor: 'var(--accent-primary)',
                color: '#fff',
                fontSize: '0.8rem',
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              <Plus size={14} /> Manage Categories ({currentCategories.length})
            </button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div
          style={{
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            borderBottom: '1px solid var(--border-subtle)',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '240px' }}>
            <Search size={16} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder={`Filter ${activeTab === 'lean' ? 'Lean practice' : 'Energy effect'} source terms...`}
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
              }}
            />
            {filterText && (
              <button
                type="button"
                onClick={() => setFilterText('')}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'all' | 'unmapped' | 'pending' | 'approved')}
              style={{
                padding: '6px 10px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
              }}
            >
              <option value="all">All Terms ({currentTerms.length})</option>
              <option value="unmapped">Unmapped</option>
              <option value="pending">Pending Approval</option>
              <option value="approved">Approved</option>
            </select>
          </div>
        </div>

        {/* Source Term Mapping Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--bg-primary)', borderBottom: '1px solid var(--border-subtle)' }}>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', width: '38%' }}>
                  1. Extracted Source Term (Evidence)
                </th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', width: '32%' }}>
                  2. Normalized Analytical Category (Interpretation)
                </th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', width: '15%' }}>
                  3. Approval Status
                </th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-muted)', width: '15%', textAlign: 'right' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredTerms.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    {currentTerms.length === 0
                      ? 'No extracted source terms discovered in Phase 9 extraction revisions.'
                      : 'No terms match the search or filter criteria.'}
                  </td>
                </tr>
              ) : (
                filteredTerms.map((term) => {
                  const saveKey = `${term.term_type}_${term.source_value}`;
                  const isSaving = savingKey === saveKey;
                  const isApproved = term.approval_state === 'approved';
                  const isMapped = !!term.analytical_category_id;

                  return (
                    <tr
                      key={saveKey}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        backgroundColor: isApproved ? 'rgba(34, 197, 94, 0.02)' : 'transparent',
                      }}
                    >
                      {/* 1. Verbatim Extracted Source Term */}
                      <td style={{ padding: '12px 16px', verticalAlign: 'middle' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{term.source_value}</span>
                          <span
                            title={`${term.occurrence_count} occurrences across ${term.publication_count} studies`}
                            style={{
                              backgroundColor: 'var(--bg-primary)',
                              border: '1px solid var(--border-subtle)',
                              padding: '2px 6px',
                              borderRadius: '10px',
                              fontSize: '0.7rem',
                              color: 'var(--text-muted)',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {term.occurrence_count}x ({term.publication_count} studies)
                          </span>
                        </div>
                      </td>

                      {/* 2. Analytical Category Mapping Selector */}
                      <td style={{ padding: '12px 16px', verticalAlign: 'middle' }}>
                        <select
                          value={term.analytical_category_id || ''}
                          disabled={isSaving || currentCategories.length === 0}
                          onChange={(e) =>
                            handleCategorySelectChange(term.term_type, term.source_value, e.target.value)
                          }
                          style={{
                            width: '100%',
                            padding: '6px 10px',
                            borderRadius: 'var(--radius-md)',
                            border: isMapped
                              ? '1px solid var(--accent-primary)'
                              : '1px solid var(--border-subtle)',
                            backgroundColor: 'var(--bg-primary)',
                            color: isMapped ? 'var(--text-primary)' : 'var(--text-muted)',
                            fontSize: '0.85rem',
                          }}
                        >
                          <option value="">-- Select Analytical Category --</option>
                          {currentCategories.map((cat) => (
                            <option key={cat.category_id} value={cat.category_id}>
                              {cat.name}
                            </option>
                          ))}
                        </select>
                      </td>

                      {/* 3. Approval Status Badge */}
                      <td style={{ padding: '12px 16px', verticalAlign: 'middle' }}>
                        {!isMapped ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 8px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: 'rgba(156, 163, 175, 0.15)',
                              color: 'var(--text-muted)',
                              fontSize: '0.75rem',
                              fontWeight: 500,
                            }}
                          >
                            <HelpCircle size={12} /> Unmapped
                          </span>
                        ) : isApproved ? (
                          <span
                            title={`Approved by ${term.approved_by || 'reviewer'}`}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 8px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: 'rgba(34, 197, 94, 0.15)',
                              color: 'var(--status-success-text)',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                            }}
                          >
                            <CheckCircle2 size={12} /> Approved
                          </span>
                        ) : (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 8px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: 'rgba(234, 179, 8, 0.15)',
                              color: 'var(--status-warning-text)',
                              fontSize: '0.75rem',
                              fontWeight: 500,
                            }}
                          >
                            <Clock size={12} /> Pending Approval
                          </span>
                        )}
                      </td>

                      {/* 4. Action Buttons */}
                      <td style={{ padding: '12px 16px', verticalAlign: 'middle', textAlign: 'right' }}>
                        {isMapped && !isApproved && (
                          <button
                            type="button"
                            disabled={isSaving}
                            onClick={() => handleApproveMapping(term.term_type, term.source_value)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '4px 10px',
                              borderRadius: 'var(--radius-md)',
                              border: 'none',
                              backgroundColor: 'var(--status-success-text)',
                              color: '#fff',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            <CheckCircle2 size={12} /> Approve
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Category Management Modal */}
      {showCategoryModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
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
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border-subtle)',
              maxWidth: '640px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FolderPlus size={20} style={{ color: 'var(--accent-primary)' }} />
                <h3 style={{ fontSize: '1.1rem', margin: 0 }}>
                  Manage {activeTab === 'lean' ? 'Lean Practice' : 'Energy Effect'} Categories
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCategoryModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {categoryError && (
              <div
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  color: 'var(--status-error-text)',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.85rem',
                }}
              >
                {categoryError}
              </div>
            )}

            {/* Category Form */}
            <form onSubmit={handleSaveCategory} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Category ID *</label>
                  <input
                    type="text"
                    required
                    disabled={!!editingCategory}
                    placeholder="e.g. 5s"
                    value={categoryFormId}
                    onChange={(e) => setCategoryFormId(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: editingCategory ? 'var(--bg-primary)' : 'var(--bg-surface)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Category Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 5S & Visual Management"
                    value={categoryFormName}
                    onChange={(e) => setCategoryFormName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--bg-surface)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Description (Optional)</label>
                <input
                  type="text"
                  placeholder="Analytical definition or scope..."
                  value={categoryFormDesc}
                  onChange={(e) => setCategoryFormDesc(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  Display Order:
                  <input
                    type="number"
                    value={categoryFormOrder}
                    onChange={(e) => setCategoryFormOrder(parseInt(e.target.value, 10) || 0)}
                    style={{
                      width: '60px',
                      padding: '4px 6px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '0.85rem',
                    }}
                  />
                </label>

                <div style={{ display: 'flex', gap: '8px' }}>
                  {editingCategory && (
                    <button
                      type="button"
                      onClick={resetCategoryForm}
                      style={{
                        padding: '6px 12px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-subtle)',
                        backgroundColor: 'transparent',
                        color: 'var(--text-primary)',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel Edit
                    </button>
                  )}
                  <button
                    type="submit"
                    style={{
                      padding: '6px 14px',
                      borderRadius: 'var(--radius-md)',
                      border: 'none',
                      backgroundColor: 'var(--accent-primary)',
                      color: '#fff',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {editingCategory ? 'Update Category' : 'Add Category'}
                  </button>
                </div>
              </div>
            </form>

            <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle)', margin: '8px 0' }} />

            {/* List of Existing Categories */}
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
                Existing Categories ({currentCategories.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '240px', overflowY: 'auto' }}>
                {currentCategories.map((cat) => (
                  <div
                    key={cat.category_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 12px',
                      backgroundColor: 'var(--bg-primary)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{cat.name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        <code>{cat.category_id}</code>
                        {cat.description ? ` — ${cat.description}` : ''}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => openEditModal(cat)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--accent-primary)',
                          cursor: 'pointer',
                          padding: '4px',
                        }}
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteCategory(cat.category_id)}
                        style={{
                          background: 'none',
                          border: 'none',
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
