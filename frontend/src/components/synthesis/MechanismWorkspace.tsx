import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  GitFork,
  Plus,
  Quote,
  RefreshCw,
  Search,
  ShieldCheck,
  Tag,
  Trash2,
  X,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  Category,
  MechanismWorkspaceData,
} from '../../types/synthesis';

interface MechanismWorkspaceProps {
  projectId: string;
}

export const MechanismWorkspace: React.FC<MechanismWorkspaceProps> = ({ projectId }) => {
  const [workspaceData, setWorkspaceData] = useState<MechanismWorkspaceData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'unmapped' | 'approved' | 'synthesis'>('all');

  // Category Modal State
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState<boolean>(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [categoryFormId, setCategoryFormId] = useState<string>('');
  const [categoryFormName, setCategoryFormName] = useState<string>('');
  const [categoryFormDesc, setCategoryFormDesc] = useState<string>('');
  const [categoryFormError, setCategoryFormError] = useState<string | null>(null);

  // Expanded QA profile accordion lookup
  const [expandedQA, setExpandedQA] = useState<Record<string, boolean>>({});

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await synthesisApi.getMechanismWorkspace(projectId);
      setWorkspaceData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load mechanism synthesis workspace.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Category Creation / Edit
  const handleOpenCategoryModal = (cat?: Category) => {
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
        await synthesisApi.updateMechanismCategory(projectId, editingCategory.category_id, {
          name: categoryFormName.trim(),
          description: categoryFormDesc.trim() || null,
        });
      } else {
        const id = categoryFormId.trim() || categoryFormName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
        await synthesisApi.createMechanismCategory(projectId, {
          category_id: id,
          name: categoryFormName.trim(),
          description: categoryFormDesc.trim() || null,
        });
      }
      setIsCategoryModalOpen(false);
      await loadData();
    } catch (err: any) {
      setCategoryFormError(err.message || 'Failed to save mechanism category.');
    }
  };

  const handleDeleteCategory = async (categoryId: string) => {
    if (!window.confirm(`Are you sure you want to delete mechanism category '${categoryId}'? Linked pathways will be unclassified.`)) {
      return;
    }
    try {
      await synthesisApi.deleteMechanismCategory(projectId, categoryId);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to delete mechanism category.');
    }
  };

  // Handle Pathway Assignment
  const handleAssignCategory = async (
    pathwayId: string,
    categoryId: string | null,
    isReviewSynthesized: boolean
  ) => {
    try {
      await synthesisApi.assignMechanismPathway(projectId, pathwayId, {
        category_id: categoryId || null,
        is_review_synthesized: isReviewSynthesized,
      });
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to assign mechanism category.');
    }
  };

  // Handle Pathway Approval
  const handleApprovePathway = async (pathwayId: string) => {
    try {
      await synthesisApi.approveMechanismPathway(projectId, pathwayId, 'lead_researcher');
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to approve mechanism pathway.');
    }
  };

  // Filtered Pathways
  const filteredPathways = useMemo(() => {
    if (!workspaceData) return [];
    return workspaceData.pathways.filter((item) => {
      const p = item.pathway;
      const matchesSearch =
        !searchTerm ||
        (p.source_mechanism_text && p.source_mechanism_text.toLowerCase().includes(searchTerm.toLowerCase())) ||
        item.source_practice.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.source_effect.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (item.publication_title && item.publication_title.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (item.analytical_mechanism_category_name &&
          item.analytical_mechanism_category_name.toLowerCase().includes(searchTerm.toLowerCase()));

      if (!matchesSearch) return false;

      if (activeFilter === 'unmapped') return !p.analytical_mechanism_category_id;
      if (activeFilter === 'approved') return p.approval_state === 'approved';
      return true;
    });
  }, [workspaceData, searchTerm, activeFilter]);

  if (loading && !workspaceData) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
        <div>Loading Mechanism Synthesis Workspace...</div>
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
          <span>Error loading mechanism synthesis workspace</span>
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

  const stats = workspaceData?.stats || {
    total_pathways: 0,
    mapped_count: 0,
    unmapped_count: 0,
    approved_count: 0,
    total_publications: 0,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Workspace Header & KPI Badges */}
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
            <GitFork size={22} style={{ color: 'var(--accent-primary)' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              Mechanism Synthesis & Impact Pathways
            </h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '6px', marginBottom: 0 }}>
            Deterministic researcher synthesis explaining <strong>HOW</strong> Lean practices influence energy outcomes.
            Source mechanism evidence ($E10$) remains distinct and immutable from analytical interpretation.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            type="button"
            data-testid="add-mechanism-category-btn"
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
            <Plus size={15} /> Add Mechanism Category
          </button>
          <button
            type="button"
            data-testid="refresh-mechanisms-btn"
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
            Total Pathways
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.total_pathways}
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
            Mapped Categories
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
            {stats.mapped_count}
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
            Approved Classifications
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--status-success-text)' }}>
            {stats.approved_count}
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
            Unmapped Evidence
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--status-warning-text)' }}>
            {stats.unmapped_count}
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
            Contributing Studies
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.total_publications}
          </div>
        </div>
      </div>

      {/* Categories Vocabulary Bar */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Tag size={16} style={{ color: 'var(--accent-primary)' }} />
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
              Analytical Mechanism Categories ({workspaceData?.categories.length || 0})
            </span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Researcher-managed taxonomy for mechanism synthesis
          </span>
        </div>

        {(!workspaceData?.categories || workspaceData.categories.length === 0) ? (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0' }}>
            No mechanism categories defined yet. Click "Add Mechanism Category" to start building your analytical taxonomy.
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

      {/* Filter Tabs & Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            type="button"
            data-testid="filter-all-btn"
            onClick={() => setActiveFilter('all')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: activeFilter === 'all' ? 'var(--accent-primary)' : 'var(--bg-surface)',
              color: activeFilter === 'all' ? '#ffffff' : 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
            }}
          >
            All Evidence ({workspaceData?.pathways.length || 0})
          </button>
          <button
            type="button"
            data-testid="filter-unmapped-btn"
            onClick={() => setActiveFilter('unmapped')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: activeFilter === 'unmapped' ? 'var(--accent-primary)' : 'var(--bg-surface)',
              color: activeFilter === 'unmapped' ? '#ffffff' : 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
            }}
          >
            Unmapped ({stats.unmapped_count})
          </button>
          <button
            type="button"
            data-testid="filter-approved-btn"
            onClick={() => setActiveFilter('approved')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: activeFilter === 'approved' ? 'var(--accent-primary)' : 'var(--bg-surface)',
              color: activeFilter === 'approved' ? '#ffffff' : 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
            }}
          >
            Approved ({stats.approved_count})
          </button>
          <button
            type="button"
            data-testid="filter-synthesis-btn"
            onClick={() => setActiveFilter('synthesis')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: activeFilter === 'synthesis' ? 'var(--accent-primary)' : 'var(--bg-surface)',
              color: activeFilter === 'synthesis' ? '#ffffff' : 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
            }}
          >
            Synthesis Chains ({workspaceData?.synthesis_chains.length || 0})
          </button>
        </div>

        <div style={{ position: 'relative', minWidth: '240px' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
          <input
            type="text"
            data-testid="search-mechanisms-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search mechanism text or terms..."
            style={{
              width: '100%',
              padding: '7px 12px 7px 32px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
            }}
          />
        </div>
      </div>

      {/* Synthesis Chains View */}
      {activeFilter === 'synthesis' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {(!workspaceData?.synthesis_chains || workspaceData.synthesis_chains.length === 0) ? (
            <div
              style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-muted)',
              }}
            >
              No approved mechanism synthesis chains yet. Assign mechanism categories to pathways and approve them to synthesize chains.
            </div>
          ) : (
            workspaceData.synthesis_chains.map((chain, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '20px',
                }}
              >
                {/* Visual Chain Header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
                  <span
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-app)',
                      border: '1px solid var(--border-subtle)',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                    }}
                  >
                    Lean: {chain.lean_category_name}
                  </span>
                  <ArrowRight size={16} style={{ color: 'var(--accent-primary)' }} />
                  <span
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--accent-primary)',
                      color: '#ffffff',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                    }}
                  >
                    Mechanism: {chain.mechanism_category_name}
                  </span>
                  <ArrowRight size={16} style={{ color: 'var(--accent-primary)' }} />
                  <span
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-app)',
                      border: '1px solid var(--border-subtle)',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                    }}
                  >
                    Energy: {chain.energy_category_name}
                  </span>

                  <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px', fontSize: '0.85rem' }}>
                    <span><strong>{chain.pathway_count}</strong> pathways</span>
                    <span><strong>{chain.publication_count}</strong> studies</span>
                    <span><strong>{chain.relation_count}</strong> relations</span>
                  </div>
                </div>

                {/* Evidence items in this chain */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {chain.pathways.map((item) => (
                    <div
                      key={item.pathway.pathway_id}
                      style={{
                        padding: '12px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--bg-app)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600 }}>{item.publication_title || 'Untitled Publication'} ({item.publication_year || 'N/A'})</span>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor: item.pathway.is_review_synthesized ? 'var(--status-warning-bg)' : 'var(--bg-surface)',
                            color: item.pathway.is_review_synthesized ? 'var(--status-warning-text)' : 'var(--text-secondary)',
                            border: '1px solid var(--border-subtle)',
                          }}
                        >
                          {item.pathway.is_review_synthesized ? 'REVIEW_SYNTHESIZED' : 'SOURCE_REPORTED'}
                        </span>
                      </div>
                      {item.pathway.source_mechanism_text && (
                        <div style={{ fontStyle: 'italic', marginTop: '6px', color: 'var(--text-secondary)' }}>
                          "{item.pathway.source_mechanism_text}"
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Pathways List View */}
      {activeFilter !== 'synthesis' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {filteredPathways.length === 0 ? (
            <div
              style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-muted)',
              }}
            >
              No mechanism evidence matching the current filter.
            </div>
          ) : (
            filteredPathways.map((item) => {
              const p = item.pathway;
              const isApproved = p.approval_state === 'approved';
              const isQAExpanded = !!expandedQA[p.pathway_id];

              return (
                <div
                  key={p.pathway_id}
                  data-testid={`pathway-card-${p.pathway_id}`}
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '14px',
                  }}
                >
                  {/* Card Header: Study & Status */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <BookOpen size={16} style={{ color: 'var(--accent-primary)' }} />
                        <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                          {item.publication_title || 'Untitled Publication'}
                        </span>
                        {item.publication_year && (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                            ({item.publication_year})
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        Relation ID: <code style={{ fontSize: '0.75rem' }}>{p.analytical_relation_id}</code> | Group Item: <code style={{ fontSize: '0.75rem' }}>{p.group_item_id}</code>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          padding: '3px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: p.is_review_synthesized ? 'var(--status-warning-bg)' : 'var(--bg-app)',
                          color: p.is_review_synthesized ? 'var(--status-warning-text)' : 'var(--text-secondary)',
                          border: '1px solid var(--border-subtle)',
                          fontWeight: 500,
                        }}
                      >
                        {p.is_review_synthesized ? 'REVIEW_SYNTHESIZED' : 'SOURCE_REPORTED'}
                      </span>

                      <span
                        style={{
                          fontSize: '0.75rem',
                          padding: '3px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: isApproved ? 'var(--status-success-bg)' : 'var(--status-warning-bg)',
                          color: isApproved ? 'var(--status-success-text)' : 'var(--status-warning-text)',
                          border: '1px solid var(--border-subtle)',
                          fontWeight: 600,
                        }}
                      >
                        {p.approval_state.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Empirical Relation Context */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                      gap: '12px',
                      backgroundColor: 'var(--bg-app)',
                      padding: '12px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Lean Practice (E4)
                      </div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', marginTop: '2px' }}>
                        {item.source_practice}
                      </div>
                      {item.analytical_lean_category_name && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--accent-primary)', marginTop: '2px' }}>
                          Category: {item.analytical_lean_category_name}
                        </div>
                      )}
                    </div>

                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Energy Effect (E5)
                      </div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', marginTop: '2px' }}>
                        {item.source_effect}
                      </div>
                      {item.analytical_energy_category_name && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--accent-primary)', marginTop: '2px' }}>
                          Category: {item.analytical_energy_category_name}
                        </div>
                      )}
                    </div>

                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Evidence Character (E9)
                      </div>
                      <div style={{ fontSize: '0.85rem', marginTop: '2px' }}>
                        {item.evidence_character.toUpperCase()} ({item.direction.toUpperCase()})
                      </div>
                    </div>
                  </div>

                  {/* Verbatim Source Mechanism Evidence (E10) */}
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      <Quote size={14} style={{ color: 'var(--accent-primary)' }} />
                      <span style={{ fontWeight: 600 }}>SOURCE MECHANISM EVIDENCE (E10) — IMMUTABLE</span>
                    </div>
                    <div
                      style={{
                        padding: '12px 14px',
                        backgroundColor: 'var(--bg-app)',
                        borderLeft: '3px solid var(--accent-primary)',
                        borderRadius: '0 var(--radius-md) var(--radius-md) 0',
                        fontSize: '0.9rem',
                        fontStyle: 'italic',
                        color: item.pathway.source_mechanism_text ? 'var(--text-primary)' : 'var(--text-muted)',
                      }}
                    >
                      {item.pathway.source_mechanism_text || 'No explicit source mechanism text extracted in study.'}
                    </div>
                  </div>

                  {/* Analytical Classification & Researcher Action Bar */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '16px',
                      flexWrap: 'wrap',
                      paddingTop: '10px',
                      borderTop: '1px solid var(--border-subtle)',
                    }}
                  >
                    <div style={{ flex: '1', minWidth: '220px' }}>
                      <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                        Analytical Mechanism Category:
                      </label>
                      <select
                        data-testid={`select-category-${p.pathway_id}`}
                        value={p.analytical_mechanism_category_id || ''}
                        onChange={(e) =>
                          handleAssignCategory(p.pathway_id, e.target.value || null, p.is_review_synthesized)
                        }
                        style={{
                          width: '100%',
                          padding: '6px 10px',
                          borderRadius: 'var(--radius-md)',
                          border: '1px solid var(--border-subtle)',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          fontSize: '0.85rem',
                        }}
                      >
                        <option value="">-- Select Analytical Mechanism --</option>
                        {workspaceData?.categories.map((cat) => (
                          <option key={cat.category_id} value={cat.category_id}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '18px' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={p.is_review_synthesized}
                          onChange={(e) =>
                            handleAssignCategory(
                              p.pathway_id,
                              p.analytical_mechanism_category_id,
                              e.target.checked
                            )
                          }
                        />
                        Review Synthesized
                      </label>
                    </div>

                    <div style={{ marginLeft: 'auto', marginTop: '18px' }}>
                      {!isApproved ? (
                        <button
                          type="button"
                          data-testid={`approve-pathway-${p.pathway_id}`}
                          disabled={!p.analytical_mechanism_category_id}
                          onClick={() => handleApprovePathway(p.pathway_id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 14px',
                            borderRadius: 'var(--radius-md)',
                            border: 'none',
                            backgroundColor: p.analytical_mechanism_category_id ? 'var(--status-success-bg)' : 'var(--bg-app)',
                            color: p.analytical_mechanism_category_id ? 'var(--status-success-text)' : 'var(--text-muted)',
                            cursor: p.analytical_mechanism_category_id ? 'pointer' : 'not-allowed',
                            fontSize: '0.85rem',
                            fontWeight: 600,
                          }}
                        >
                          <Check size={14} /> Approve Pathway
                        </button>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--status-success-text)', fontSize: '0.85rem', fontWeight: 600 }}>
                          <CheckCircle2 size={16} /> Approved
                        </div>
                      )}
                    </div>
                  </div>

                  {/* QA Profile Accordion Toggle */}
                  <div>
                    <button
                      type="button"
                      onClick={() => setExpandedQA((prev) => ({ ...prev, [p.pathway_id]: !prev[p.pathway_id] }))}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 8px',
                        border: 'none',
                        background: 'none',
                        color: 'var(--accent-primary)',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                      }}
                    >
                      <ShieldCheck size={14} />
                      <span>{isQAExpanded ? 'Hide QA Profile' : 'Show QA Criterion Profile (Phase 8)'}</span>
                      {isQAExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>

                    {isQAExpanded && (
                      <div
                        style={{
                          marginTop: '8px',
                          padding: '12px',
                          backgroundColor: 'var(--bg-app)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-md)',
                          fontSize: '0.8rem',
                        }}
                      >
                        {!item.qa_profile ? (
                          <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            QA assessment unavailable for this study.
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                              Reviewer: {item.qa_profile.reviewer_id} (Criterion-Level Assessments)
                            </div>
                            {item.qa_profile.criteria_assessments.map((crit, cIdx) => (
                              <div key={cIdx} style={{ paddingLeft: '8px', borderLeft: '2px solid var(--border-subtle)' }}>
                                <div style={{ fontWeight: 500 }}>{crit.question_text}</div>
                                <div style={{ color: 'var(--accent-primary)', marginTop: '2px' }}>
                                  Response: <strong>{crit.response_value}</strong>
                                </div>
                                {crit.justification && (
                                  <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '2px' }}>
                                    Justification: {crit.justification}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Category Creation / Edit Modal */}
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                {editingCategory ? 'Edit Mechanism Category' : 'Create Mechanism Category'}
              </h3>
              <button
                type="button"
                onClick={() => setIsCategoryModalOpen(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            {categoryFormError && (
              <div
                style={{
                  padding: '8px 12px',
                  backgroundColor: 'var(--status-error-bg)',
                  border: '1px solid var(--status-error-border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--status-error-text)',
                  fontSize: '0.85rem',
                  marginBottom: '14px',
                }}
              >
                {categoryFormError}
              </div>
            )}

            <form onSubmit={handleSaveCategory} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {!editingCategory && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
                    Category Identifier (slug):
                  </label>
                  <input
                    type="text"
                    data-testid="category-id-input"
                    value={categoryFormId}
                    onChange={(e) => setCategoryFormId(e.target.value)}
                    placeholder="e.g. idle_time_reduction"
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--bg-app)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                    }}
                  />
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
                  Category Name:
                </label>
                <input
                  type="text"
                  data-testid="category-name-input"
                  value={categoryFormName}
                  onChange={(e) => setCategoryFormName(e.target.value)}
                  placeholder="e.g. Idle-Time Reduction"
                  required
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-app)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
                  Description (optional):
                </label>
                <textarea
                  data-testid="category-desc-input"
                  value={categoryFormDesc}
                  onChange={(e) => setCategoryFormDesc(e.target.value)}
                  placeholder="Describe the physical/operational causal mechanism..."
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-app)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setIsCategoryModalOpen(false)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-app)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="save-category-submit-btn"
                  style={{
                    padding: '6px 16px',
                    borderRadius: 'var(--radius-md)',
                    border: 'none',
                    backgroundColor: 'var(--accent-primary)',
                    color: '#ffffff',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                  }}
                >
                  Save Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
