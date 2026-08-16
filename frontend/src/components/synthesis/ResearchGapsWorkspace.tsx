import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  ClipboardCheck,
  Link2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Target,
  Trash2,
  Unlink,
  X,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  QACriterionAssessmentSummary,
  QAProfileSummary,
  ResearchGap,
  ResearchGapDetail,
  ResearchGapEvidenceCandidate,
  ResearchGapLink,
  ResearchGapType,
  ResearchGapWorkspaceData,
  RESEARCH_GAP_LINK_TYPE_LABELS,
  RESEARCH_GAP_TYPE_LABELS,
} from '../../types/synthesis';

interface ResearchGapsWorkspaceProps {
  projectId: string;
}

const EMPTY_STATS = {
  total_gaps: 0,
  thematic_count: 0,
  mechanism_count: 0,
  methodological_count: 0,
  contextual_count: 0,
  inconsistent_evidence_count: 0,
  linked_publication_count: 0,
};

const QAProfilePanel: React.FC<{ qa: QAProfileSummary | null }> = ({ qa }) => {
  if (!qa) {
    return (
      <div
        data-testid="qa-profile-missing"
        style={{
          marginTop: '10px',
          padding: '8px 12px',
          borderRadius: 'var(--radius-md)',
          backgroundColor: 'var(--bg-surface)',
          border: '1px dashed var(--border-subtle)',
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
          fontStyle: 'italic',
        }}
      >
        No QA profile available. This artifact has not been assessed with a Phase 8 criterion-level QA assessment.
      </div>
    );
  }

  return (
    <div
      data-testid="qa-profile-present"
      style={{
        marginTop: '10px',
        padding: '12px',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '8px', color: 'var(--text-primary)' }}>
        <ClipboardCheck size={13} style={{ verticalAlign: '-2px', marginRight: '6px', color: 'var(--accent-primary)' }} />
        Criterion-Level QA Profile — {qa.reviewer_id}
      </div>
      {qa.criteria_assessments.length === 0 ? (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
          QA assessment exists but contains no criterion responses.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {qa.criteria_assessments.map((criterion: QACriterionAssessmentSummary) => (
            <div key={criterion.criterion_id} style={{ fontSize: '0.8rem' }}>
              <div style={{ color: 'var(--text-secondary)' }}>{criterion.question_text}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                <span
                  style={{
                    padding: '1px 8px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--accent-subtle)',
                    color: 'var(--accent-primary)',
                    fontWeight: 600,
                    fontSize: '0.7rem',
                    textTransform: 'uppercase',
                  }}
                >
                  {criterion.response_value}
                </span>
                {criterion.justification && (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    {criterion.justification}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ResearchGapsWorkspace: React.FC<ResearchGapsWorkspaceProps> = ({ projectId }) => {
  const [workspaceData, setWorkspaceData] = useState<ResearchGapWorkspaceData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Create/Edit Gap Modal State
  const [isGapModalOpen, setIsGapModalOpen] = useState<boolean>(false);
  const [editingGap, setEditingGap] = useState<ResearchGap | null>(null);
  const [gapFormType, setGapFormType] = useState<ResearchGapType>('thematic');
  const [gapFormTitle, setGapFormTitle] = useState<string>('');
  const [gapFormRationale, setGapFormRationale] = useState<string>('');
  const [gapFormResearcher, setGapFormResearcher] = useState<string>('lead_researcher');
  const [gapFormError, setGapFormError] = useState<string | null>(null);

  // Evidence Link Modal State
  const [isLinkModalOpen, setIsLinkModalOpen] = useState<boolean>(false);
  const [linkModalGap, setLinkModalGap] = useState<ResearchGapDetail | null>(null);
  const [candidates, setCandidates] = useState<ResearchGapEvidenceCandidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState<boolean>(false);
  const [linkActionError, setLinkActionError] = useState<string | null>(null);
  const [expandedQaTargets, setExpandedQaTargets] = useState<Set<string>>(new Set());

  const toggleQa = (key: string) => {
    setExpandedQaTargets((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await synthesisApi.getResearchGapWorkspace(projectId);
      setWorkspaceData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load research gap workspace.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenGapModal = (gap?: ResearchGap) => {
    if (gap) {
      setEditingGap(gap);
      setGapFormType(gap.gap_type);
      setGapFormTitle(gap.title);
      setGapFormRationale(gap.rationale);
      setGapFormResearcher(gap.researcher_id);
    } else {
      setEditingGap(null);
      setGapFormType('thematic');
      setGapFormTitle('');
      setGapFormRationale('');
      setGapFormResearcher('lead_researcher');
    }
    setGapFormError(null);
    setIsGapModalOpen(true);
  };

  const handleSaveGap = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gapFormTitle.trim()) {
      setGapFormError('Gap title is required.');
      return;
    }
    if (!gapFormRationale.trim()) {
      setGapFormError('Gap rationale is required. A gap must be justified by linked evidence, never by publication count alone.');
      return;
    }

    try {
      if (editingGap) {
        await synthesisApi.updateResearchGap(projectId, editingGap.gap_id, {
          gap_type: gapFormType,
          title: gapFormTitle.trim(),
          rationale: gapFormRationale.trim(),
        });
      } else {
        await synthesisApi.createResearchGap(projectId, {
          gap_type: gapFormType,
          title: gapFormTitle.trim(),
          rationale: gapFormRationale.trim(),
          researcher_id: gapFormResearcher.trim() || 'lead_researcher',
        });
      }
      setIsGapModalOpen(false);
      await loadData();
    } catch (err: any) {
      setGapFormError(err.message || 'Failed to save research gap.');
    }
  };

  const handleDeleteGap = async (gap: ResearchGap) => {
    if (!window.confirm(`Are you sure you want to delete research gap '${gap.title}'? Its evidence links will be removed but source evidence is preserved.`)) {
      return;
    }
    try {
      await synthesisApi.deleteResearchGap(projectId, gap.gap_id);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to delete research gap.');
    }
  };

  const openLinkModal = async (detail: ResearchGapDetail) => {
    setLinkModalGap(detail);
    setLinkActionError(null);
    setIsLinkModalOpen(true);
    setCandidatesLoading(true);
    try {
      const cands = await synthesisApi.getResearchGapEvidenceCandidates(projectId);
      setCandidates(cands);
    } catch (err: any) {
      setLinkActionError(err.message || 'Failed to load linkable evidence candidates.');
    } finally {
      setCandidatesLoading(false);
    }
  };

  const handleLinkEvidence = async (candidate: ResearchGapEvidenceCandidate) => {
    if (!linkModalGap) return;
    if (!candidate.traceable) {
      setLinkActionError(
        'This artifact is not traceable to an eligible COMPLETE extraction revision and cannot be linked as gap evidence.'
      );
      return;
    }
    try {
      await synthesisApi.linkResearchGapEvidence(projectId, linkModalGap.gap.gap_id, {
        link_type: candidate.link_type,
        target_id: candidate.target_id,
      });
      await refreshLinkModalGap();
      setLinkActionError(null);
    } catch (err: any) {
      setLinkActionError(err.message || 'Failed to link evidence.');
    }
  };

  const handleUnlinkEvidence = async (link: ResearchGapLink) => {
    if (!linkModalGap) return;
    try {
      await synthesisApi.unlinkResearchGapEvidence(projectId, linkModalGap.gap.gap_id, link.link_id);
      await refreshLinkModalGap();
      setLinkActionError(null);
    } catch (err: any) {
      setLinkActionError(err.message || 'Failed to unlink evidence.');
    }
  };

  const refreshLinkModalGap = async () => {
    if (!linkModalGap) return;
    const detail = await synthesisApi.getResearchGap(projectId, linkModalGap.gap.gap_id);
    setLinkModalGap(detail);
    await loadData();
  };

  if (loading && !workspaceData) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
        <div>Loading Research Gap Synthesis Workspace...</div>
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
          <span>Error loading research gap workspace</span>
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

  const stats = workspaceData?.stats || EMPTY_STATS;

  const gapTypeOrder: ResearchGapType[] = [
    'thematic',
    'mechanism',
    'methodological',
    'contextual',
    'inconsistent_evidence',
  ];

  const filteredGaps = (workspaceData?.gaps || []).filter((detail) => {
    if (!searchTerm) return true;
    const q = searchTerm.toLowerCase();
    return (
      detail.gap.title.toLowerCase().includes(q) ||
      detail.gap.rationale.toLowerCase().includes(q) ||
      detail.gap.gap_type.toLowerCase().includes(q) ||
      detail.gap.researcher_id.toLowerCase().includes(q)
    );
  });

  const typeCount = (gapType: ResearchGapType): number => {
    switch (gapType) {
      case 'thematic':
        return stats.thematic_count;
      case 'mechanism':
        return stats.mechanism_count;
      case 'methodological':
        return stats.methodological_count;
      case 'contextual':
        return stats.contextual_count;
      case 'inconsistent_evidence':
        return stats.inconsistent_evidence_count;
      default:
        return 0;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Workspace Header */}
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
            <Target size={22} style={{ color: 'var(--accent-primary)' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              Research Gap Synthesis
            </h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '6px', marginBottom: 0 }}>
            Researcher-authored analytical conclusions across 5 gap dimensions. Every gap is backed by traceable
            evidence links to eligible COMPLETE extraction revisions. Low publication count alone never establishes a gap.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            type="button"
            data-testid="add-research-gap-btn"
            onClick={() => handleOpenGapModal()}
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
            <Plus size={15} /> Add Research Gap
          </button>
          <button
            type="button"
            data-testid="refresh-research-gaps-btn"
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Total Gaps
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.total_gaps}
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
            Thematic
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
            {stats.thematic_count}
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
            Mechanism
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
            {stats.mechanism_count}
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
            Methodological
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
            {stats.methodological_count}
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
            Contextual
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
            {stats.contextual_count}
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
            Inconsistent Evidence
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--status-warning-text)' }}>
            {stats.inconsistent_evidence_count}
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
            Linked Studies
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)' }}>
            {stats.linked_publication_count}
          </div>
        </div>
      </div>

      {/* Search */}
      <div style={{ position: 'relative', maxWidth: '360px' }}>
        <Search size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
        <input
          type="text"
          data-testid="search-research-gaps-input"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search gaps..."
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

      {/* Multi-dimensional matrix view grouped by gap type */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {gapTypeOrder.map((gapType) => {
          const typeGaps = filteredGaps.filter((detail) => detail.gap.gap_type === gapType);
          return (
            <div
              key={gapType}
              data-testid={`gap-type-section-${gapType}`}
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
                  gap: '10px',
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-app)',
                }}
              >
                <Target size={16} style={{ color: 'var(--accent-primary)' }} />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                  {RESEARCH_GAP_TYPE_LABELS[gapType]}
                </span>
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: '0.8rem',
                    padding: '2px 10px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--accent-subtle)',
                    color: 'var(--accent-primary)',
                    fontWeight: 600,
                  }}
                >
                  {typeCount(gapType)} gap{typeCount(gapType) === 1 ? '' : 's'}
                </span>
              </div>

              {typeGaps.length === 0 ? (
                <div style={{ padding: '16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No {gapType.replace('_', ' ')} gaps documented yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px' }}>
                  {typeGaps.map((detail) => (
                    <div
                      key={detail.gap.gap_id}
                      data-testid={`gap-card-${detail.gap.gap_id}`}
                      style={{
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-md)',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '10px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{detail.gap.title}</span>
                            <span
                              style={{
                                fontSize: '0.7rem',
                                padding: '2px 8px',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: 'var(--bg-app)',
                                border: '1px solid var(--border-subtle)',
                                color: 'var(--text-secondary)',
                                textTransform: 'uppercase',
                                fontWeight: 600,
                              }}
                            >
                              {detail.gap.gap_type}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                            By: {detail.gap.researcher_id}
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <button
                            type="button"
                            data-testid={`manage-evidence-${detail.gap.gap_id}`}
                            onClick={() => openLinkModal(detail)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                              padding: '5px 10px',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-subtle)',
                              backgroundColor: 'var(--bg-app)',
                              color: 'var(--accent-primary)',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                              fontWeight: 500,
                            }}
                          >
                            <Link2 size={13} /> Evidence ({detail.links.length})
                          </button>
                          <button
                            type="button"
                            data-testid={`edit-gap-${detail.gap.gap_id}`}
                            onClick={() => handleOpenGapModal(detail.gap)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                              padding: '5px 10px',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-subtle)',
                              backgroundColor: 'var(--bg-app)',
                              color: 'var(--text-primary)',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                            }}
                          >
                            <Pencil size={13} /> Edit
                          </button>
                          <button
                            type="button"
                            data-testid={`delete-gap-${detail.gap.gap_id}`}
                            onClick={() => handleDeleteGap(detail.gap)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                              padding: '5px 10px',
                              borderRadius: 'var(--radius-md)',
                              border: '1px solid var(--border-subtle)',
                              backgroundColor: 'var(--bg-app)',
                              color: 'var(--status-error-text)',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                            }}
                          >
                            <Trash2 size={13} /> Delete
                          </button>
                        </div>
                      </div>

                      <div
                        style={{
                          padding: '10px 12px',
                          backgroundColor: 'var(--bg-app)',
                          borderLeft: '3px solid var(--accent-primary)',
                          borderRadius: '0 var(--radius-md) var(--radius-md) 0',
                          fontSize: '0.85rem',
                          color: 'var(--text-secondary)',
                        }}
                      >
                        {detail.gap.rationale}
                      </div>

                      {detail.links.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {detail.links.map((link) => (
                            <span
                              key={link.link_id}
                              style={{
                                fontSize: '0.75rem',
                                padding: '2px 8px',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: 'var(--accent-subtle)',
                                color: 'var(--accent-primary)',
                                fontWeight: 500,
                              }}
                            >
                              {RESEARCH_GAP_LINK_TYPE_LABELS[link.link_type]}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Create / Edit Gap Modal */}
      {isGapModalOpen && (
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
              maxWidth: '560px',
              width: '100%',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                {editingGap ? 'Edit Research Gap' : 'Create Research Gap'}
              </h3>
              <button
                type="button"
                onClick={() => setIsGapModalOpen(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            {gapFormError && (
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
                {gapFormError}
              </div>
            )}

            <form onSubmit={handleSaveGap} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
                  Gap Dimension:
                </label>
                <select
                  data-testid="gap-type-select"
                  value={gapFormType}
                  onChange={(e) => setGapFormType(e.target.value as ResearchGapType)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-app)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                  }}
                >
                  {gapTypeOrder.map((gt) => (
                    <option key={gt} value={gt}>
                      {RESEARCH_GAP_TYPE_LABELS[gt]}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
                  Title:
                </label>
                <input
                  type="text"
                  data-testid="gap-title-input"
                  value={gapFormTitle}
                  onChange={(e) => setGapFormTitle(e.target.value)}
                  placeholder="e.g. Under-studied combination of SMED and compressed air efficiency"
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
                  Rationale (researcher justification):
                </label>
                <textarea
                  data-testid="gap-rationale-input"
                  value={gapFormRationale}
                  onChange={(e) => setGapFormRationale(e.target.value)}
                  placeholder="Explain the gap based on linked evidence. Low publication count alone is never sufficient."
                  rows={4}
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

              {!editingGap && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
                    Researcher ID:
                  </label>
                  <input
                    type="text"
                    data-testid="gap-researcher-input"
                    value={gapFormResearcher}
                    onChange={(e) => setGapFormResearcher(e.target.value)}
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

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setIsGapModalOpen(false)}
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
                  data-testid="save-gap-submit-btn"
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
                  Save Research Gap
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Evidence Link Modal */}
      {isLinkModalOpen && linkModalGap && (
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
              maxWidth: '720px',
              width: '100%',
              maxHeight: '80vh',
              overflowY: 'auto',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                Supporting Evidence — {linkModalGap.gap.title}
              </h3>
              <button
                type="button"
                onClick={() => setIsLinkModalOpen(false)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            {linkActionError && (
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
                {linkActionError}
              </div>
            )}

            {/* Existing links */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '8px' }}>
                Linked Evidence ({linkModalGap.links.length})
              </div>
              {linkModalGap.links.length === 0 ? (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No evidence linked yet. Select a traceable artifact below.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {linkModalGap.links.map((link) => (
                    <div
                      key={link.link_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '10px',
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'var(--bg-app)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 600 }}>
                          {RESEARCH_GAP_LINK_TYPE_LABELS[link.link_type]}
                        </span>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Group Item: <code>{link.group_item_id}</code> | Revision:{' '}
                          <code>{link.latest_revision_id}</code>
                        </div>
                      </div>
                      <button
                        type="button"
                        data-testid={`unlink-evidence-${link.link_id}`}
                        onClick={() => handleUnlinkEvidence(link)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '5px 10px',
                          borderRadius: 'var(--radius-md)',
                          border: '1px solid var(--border-subtle)',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--status-error-text)',
                          cursor: 'pointer',
                          fontSize: '0.8rem',
                        }}
                      >
                        <Unlink size={13} /> Unlink
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Candidate artifacts */}
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '8px' }}>
                Linkable Evidence Artifacts
              </div>
              {candidatesLoading ? (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', padding: '8px 0' }}>
                  Loading candidates...
                </div>
              ) : candidates.length === 0 ? (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No linkable synthesis artifacts available yet. Build the matrix, mechanism, or context workspace first.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {candidates.map((candidate) => {
                    const alreadyLinked = linkModalGap.links.some(
                      (l) => l.link_type === candidate.link_type && l.target_id === candidate.target_id
                    );
                    const candidateKey = `${candidate.link_type}-${candidate.target_id}`;
                    const qaExpanded = expandedQaTargets.has(candidateKey);
                    return (
                      <div
                        key={candidateKey}
                        data-testid={`candidate-${candidate.target_id}`}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '10px',
                          padding: '10px 12px',
                          borderRadius: 'var(--radius-md)',
                          backgroundColor: 'var(--bg-app)',
                          border: '1px solid var(--border-subtle)',
                          fontSize: '0.85rem',
                          opacity: candidate.traceable ? 1 : 0.55,
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 600 }}>
                              {RESEARCH_GAP_LINK_TYPE_LABELS[candidate.link_type]}
                            </span>
                            <span
                              style={{
                                fontSize: '0.7rem',
                                padding: '1px 6px',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: candidate.traceable ? 'var(--status-success-bg)' : 'var(--status-warning-bg)',
                                color: candidate.traceable ? 'var(--status-success-text)' : 'var(--status-warning-text)',
                                border: '1px solid var(--border-subtle)',
                                fontWeight: 600,
                              }}
                            >
                              {candidate.traceable ? 'TRACEABLE' : 'NOT TRACEABLE'}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.8rem', marginTop: '2px' }}>{candidate.label}</div>
                          {candidate.publication_title && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {candidate.publication_title} ({candidate.publication_year || 'N/A'})
                            </div>
                          )}
                          <div style={{ marginTop: '6px' }}>
                            <button
                              type="button"
                              data-testid={`toggle-qa-${candidate.target_id}`}
                              onClick={() => toggleQa(candidateKey)}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '5px',
                                padding: '3px 8px',
                                borderRadius: 'var(--radius-sm)',
                                border: '1px solid var(--border-subtle)',
                                backgroundColor: 'var(--bg-surface)',
                                color: 'var(--text-secondary)',
                                cursor: 'pointer',
                                fontSize: '0.75rem',
                              }}
                            >
                              <ClipboardCheck size={12} />
                              {qaExpanded ? 'Hide QA Profile' : 'Show QA Profile'}
                            </button>
                            {qaExpanded && <QAProfilePanel qa={candidate.qa_profile} />}
                          </div>
                        </div>
                        {!alreadyLinked ? (
                          <button
                            type="button"
                            data-testid={`link-evidence-${candidate.target_id}`}
                            onClick={() => handleLinkEvidence(candidate)}
                            disabled={!candidate.traceable}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                              padding: '5px 10px',
                              borderRadius: 'var(--radius-md)',
                              border: 'none',
                              backgroundColor: candidate.traceable ? 'var(--accent-primary)' : 'var(--bg-surface)',
                              color: candidate.traceable ? '#ffffff' : 'var(--text-muted)',
                              cursor: candidate.traceable ? 'pointer' : 'not-allowed',
                              fontSize: '0.8rem',
                              fontWeight: 500,
                            }}
                          >
                            <Link2 size={13} /> Link
                          </button>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--status-success-text)', fontWeight: 600 }}>
                            <BookOpen size={13} style={{ verticalAlign: '-2px', marginRight: '4px' }} />
                            Linked
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
