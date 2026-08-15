import React, { useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Calculator,
  ChevronDown,
  ChevronRight,
  Quote,
  ShieldCheck,
  X,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  AnalyticalRelationDetail,
  ConvertedValue,
  MatrixCellDetail,
  RelationDirection,
} from '../../types/synthesis';

interface MatrixCellDetailModalProps {
  projectId: string;
  detail: MatrixCellDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onRelationUpdated?: () => void;
}

const SUPPORTED_ENERGY_UNITS = ['J', 'kJ', 'MJ', 'GJ', 'Wh', 'kWh', 'MWh'];

export const MatrixCellDetailModal: React.FC<MatrixCellDetailModalProps> = ({
  projectId,
  detail,
  loading,
  error,
  onClose,
  onRelationUpdated,
}) => {
  const [expandedQaRelId, setExpandedQaRelId] = useState<string | null>(null);
  const [conversionTargetUnit, setConversionTargetUnit] = useState<Record<string, string>>({});
  const [conversionPreviews, setConversionPreviews] = useState<Record<string, ConvertedValue | null>>({});
  const [conversionLoading, setConversionLoading] = useState<Record<string, boolean>>({});
  const [conversionErrors, setConversionErrors] = useState<Record<string, string | null>>({});
  const [conversionSuccess, setConversionSuccess] = useState<Record<string, string | null>>({});

  if (!detail && !loading && !error) return null;

  const toggleQaAccordion = (relId: string) => {
    setExpandedQaRelId((prev) => (prev === relId ? null : relId));
  };

  const handleUnitSelectChange = (relId: string, unit: string) => {
    setConversionTargetUnit((prev) => ({ ...prev, [relId]: unit }));
    setConversionPreviews((prev) => ({ ...prev, [relId]: null }));
    setConversionErrors((prev) => ({ ...prev, [relId]: null }));
    setConversionSuccess((prev) => ({ ...prev, [relId]: null }));
  };

  const handlePreviewConversion = async (rel: AnalyticalRelationDetail) => {
    const relId = rel.relation.relation_id;
    const targetUnit = conversionTargetUnit[relId] || 'kWh';
    setConversionLoading((prev) => ({ ...prev, [relId]: true }));
    setConversionErrors((prev) => ({ ...prev, [relId]: null }));
    setConversionSuccess((prev) => ({ ...prev, [relId]: null }));

    try {
      const preview = await synthesisApi.convertUnit(projectId, relId, targetUnit);
      setConversionPreviews((prev) => ({ ...prev, [relId]: preview }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Conversion calculation failed';
      setConversionErrors((prev) => ({ ...prev, [relId]: msg }));
    } finally {
      setConversionLoading((prev) => ({ ...prev, [relId]: false }));
    }
  };

  const handleSaveConversion = async (rel: AnalyticalRelationDetail) => {
    const relId = rel.relation.relation_id;
    const targetUnit = conversionTargetUnit[relId] || 'kWh';
    setConversionLoading((prev) => ({ ...prev, [relId]: true }));
    setConversionErrors((prev) => ({ ...prev, [relId]: null }));

    try {
      await synthesisApi.saveConvertedUnit(projectId, relId, targetUnit);
      setConversionSuccess((prev) => ({ ...prev, [relId]: 'Converted value saved successfully' }));
      if (onRelationUpdated) {
        onRelationUpdated();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save converted value';
      setConversionErrors((prev) => ({ ...prev, [relId]: msg }));
    } finally {
      setConversionLoading((prev) => ({ ...prev, [relId]: false }));
    }
  };

  const getDirectionBadge = (dir: RelationDirection) => {
    switch (dir) {
      case 'positive':
        return (
          <span
            style={{
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(34, 197, 94, 0.15)',
              color: 'var(--status-success-text)',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            + Positive (Efficiency Improvement)
          </span>
        );
      case 'negative':
        return (
          <span
            style={{
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              color: 'var(--status-error-text)',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            - Negative (Degradation)
          </span>
        );
      case 'no_effect':
        return (
          <span
            style={{
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(156, 163, 175, 0.15)',
              color: 'var(--text-secondary)',
              fontSize: '0.75rem',
              fontWeight: 500,
            }}
          >
            0 No Effect
          </span>
        );
      case 'mixed':
        return (
          <span
            style={{
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(234, 179, 8, 0.15)',
              color: 'var(--status-warning-text)',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            ~ Mixed
          </span>
        );
      default:
        return (
          <span
            style={{
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(156, 163, 175, 0.15)',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
            }}
          >
            ? Cannot Determine
          </span>
        );
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '24px',
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
          maxWidth: '900px',
          width: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            backgroundColor: 'var(--bg-primary)',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span
                style={{
                  backgroundColor: 'var(--accent-primary)',
                  color: '#fff',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                }}
              >
                Matrix Cell Detail
              </span>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>
                {detail ? `${detail.lean_category.name} × ${detail.energy_category.name}` : 'Loading Cell Detail...'}
              </h3>
            </div>
            {detail && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '6px', marginBottom: 0 }}>
                <strong>{detail.relation_count}</strong> individual Lean–EE relations across{' '}
                <strong>{detail.publication_count}</strong> distinct empirical studies.
              </p>
            )}
          </div>

          <button
            type="button"
            data-testid="close-cell-modal-btn"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <X size={22} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {loading && (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading cell relations and quality assessment profiles...
            </div>
          )}

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

          {detail && (
            <>
              {/* Evidence Distribution Banner */}
              <div
                style={{
                  backgroundColor: 'var(--bg-primary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '12px 16px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Direction Distribution
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
                    {Object.entries(detail.direction_distribution).map(([dir, count]) => (
                      <span
                        key={dir}
                        style={{
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-subtle)',
                          padding: '2px 8px',
                          borderRadius: '10px',
                          fontSize: '0.75rem',
                        }}
                      >
                        {dir}: <strong>{count}</strong>
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Evidence Character
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
                    {Object.entries(detail.evidence_character_distribution).map(([char, count]) => (
                      <span
                        key={char}
                        style={{
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-subtle)',
                          padding: '2px 8px',
                          borderRadius: '10px',
                          fontSize: '0.75rem',
                        }}
                      >
                        {char}: <strong>{count}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Relations List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Contributing Relations ({detail.relations.length})
                </div>

                {detail.relations.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No analytical relations mapped to this cell.
                  </div>
                ) : (
                  detail.relations.map((item, idx) => {
                    const rel = item.relation;
                    const relId = rel.relation_id;
                    const isQaExpanded = expandedQaRelId === relId;
                    const preview = conversionPreviews[relId];
                    const isConvLoading = conversionLoading[relId] || false;
                    const convErr = conversionErrors[relId];
                    const convSuccess = conversionSuccess[relId];
                    const selectedTargetUnit = conversionTargetUnit[relId] || 'kWh';
                    const hasConvertibleMagnitude = rel.magnitude !== null && !!rel.original_unit;

                    return (
                      <div
                        key={relId}
                        style={{
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-lg)',
                          padding: '16px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '12px',
                        }}
                      >
                        {/* Relation Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                                #{idx + 1} Relation
                              </span>
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                (group_item_id: <code>{rel.group_item_id.substring(0, 8)}...</code>)
                              </span>
                            </div>
                            <div style={{ fontSize: '0.95rem', fontWeight: 600, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <BookOpen size={16} style={{ color: 'var(--text-muted)' }} />
                              <span>{item.publication_title || `Publication ${rel.publication_id.substring(0, 8)}...`}</span>
                              {item.publication_year && (
                                <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                  ({item.publication_year})
                                </span>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {getDirectionBadge(rel.direction)}
                            <span
                              style={{
                                padding: '3px 8px',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: 'var(--bg-primary)',
                                border: '1px solid var(--border-subtle)',
                                fontSize: '0.75rem',
                                color: 'var(--text-secondary)',
                                textTransform: 'capitalize',
                              }}
                            >
                              {rel.evidence_character}
                            </span>
                          </div>
                        </div>

                        {/* Source Evidence Grid */}
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                            gap: '12px',
                            backgroundColor: 'var(--bg-primary)',
                            padding: '12px',
                            borderRadius: 'var(--radius-md)',
                            fontSize: '0.85rem',
                          }}
                        >
                          <div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                              1. Extracted Practice (Evidence)
                            </div>
                            <div style={{ fontWeight: 600, marginTop: '2px' }}>{rel.source_practice}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <ArrowRight size={12} /> {detail.lean_category.name}
                            </div>
                          </div>

                          <div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                              2. Extracted Effect Indicator (Evidence)
                            </div>
                            <div style={{ fontWeight: 600, marginTop: '2px' }}>{rel.source_effect}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <ArrowRight size={12} /> {detail.energy_category.name}
                            </div>
                          </div>

                          <div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                              3. Extracted Magnitude & Unit
                            </div>
                            <div style={{ fontWeight: 600, marginTop: '2px' }}>
                              {rel.magnitude !== null ? `${rel.magnitude} ${rel.original_unit || ''}` : 'Not quantitatively reported'}
                            </div>
                            {rel.converted_value && (
                              <div style={{ fontSize: '0.75rem', color: 'var(--status-success-text)', marginTop: '2px' }}>
                                Transformed: <strong>{rel.converted_value.transformed_value} {rel.converted_value.transformed_unit}</strong>
                                <span style={{ color: 'var(--text-muted)' }}> ({rel.converted_value.conversion_rule})</span>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Provenance Quote */}
                        {item.source_quote && (
                          <div
                            style={{
                              backgroundColor: 'rgba(59, 130, 246, 0.05)',
                              borderLeft: '3px solid var(--accent-primary)',
                              padding: '8px 12px',
                              borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                              fontSize: '0.8rem',
                              color: 'var(--text-secondary)',
                              display: 'flex',
                              gap: '8px',
                              alignItems: 'flex-start',
                            }}
                          >
                            <Quote size={16} style={{ color: 'var(--accent-primary)', flexShrink: 0, marginTop: '2px' }} />
                            <div>
                              <em>"{item.source_quote}"</em>
                              {(item.source_page || item.source_section) && (
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                                  Locator: {item.source_page ? `p. ${item.source_page}` : ''}{item.source_section ? `, section: ${item.source_section}` : ''}
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Hybrid Unit Conversion Tool */}
                        {hasConvertibleMagnitude && (
                          <div
                            style={{
                              border: '1px solid var(--border-subtle)',
                              borderRadius: 'var(--radius-md)',
                              padding: '10px 14px',
                              backgroundColor: 'var(--bg-primary)',
                              fontSize: '0.8rem',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                                <Calculator size={14} style={{ color: 'var(--accent-primary)' }} />
                                <span>Hybrid Unit Conversion Helper</span>
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Target Unit:</label>
                                <select
                                  value={selectedTargetUnit}
                                  onChange={(e) => handleUnitSelectChange(relId, e.target.value)}
                                  style={{
                                    padding: '4px 8px',
                                    borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-subtle)',
                                    backgroundColor: 'var(--bg-surface)',
                                    fontSize: '0.8rem',
                                  }}
                                >
                                  {SUPPORTED_ENERGY_UNITS.map((u) => (
                                    <option key={u} value={u}>
                                      {u}
                                    </option>
                                  ))}
                                </select>

                                <button
                                  type="button"
                                  disabled={isConvLoading}
                                  onClick={() => handlePreviewConversion(item)}
                                  style={{
                                    padding: '4px 10px',
                                    borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--accent-primary)',
                                    backgroundColor: 'transparent',
                                    color: 'var(--accent-primary)',
                                    cursor: 'pointer',
                                    fontSize: '0.75rem',
                                    fontWeight: 600,
                                  }}
                                >
                                  Preview Calculation
                                </button>
                              </div>
                            </div>

                            {convErr && (
                              <div style={{ color: 'var(--status-error-text)', fontSize: '0.75rem' }}>{convErr}</div>
                            )}

                            {convSuccess && (
                              <div style={{ color: 'var(--status-success-text)', fontSize: '0.75rem', fontWeight: 600 }}>
                                {convSuccess}
                              </div>
                            )}

                            {preview && (
                              <div
                                style={{
                                  backgroundColor: 'var(--bg-surface)',
                                  padding: '8px 12px',
                                  borderRadius: 'var(--radius-sm)',
                                  border: '1px dashed var(--accent-primary)',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  flexWrap: 'wrap',
                                  gap: '8px',
                                }}
                              >
                                <div>
                                  <div>
                                    Preview: <strong>{preview.transformed_value} {preview.transformed_unit}</strong>
                                  </div>
                                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                    Rule: {preview.conversion_rule}
                                  </div>
                                </div>

                                <button
                                  type="button"
                                  disabled={isConvLoading}
                                  onClick={() => handleSaveConversion(item)}
                                  style={{
                                    padding: '4px 12px',
                                    borderRadius: 'var(--radius-sm)',
                                    border: 'none',
                                    backgroundColor: 'var(--accent-primary)',
                                    color: '#fff',
                                    cursor: 'pointer',
                                    fontSize: '0.75rem',
                                    fontWeight: 600,
                                  }}
                                >
                                  Save Converted Value
                                </button>
                              </div>
                            )}
                          </div>
                        )}

                        {/* QA Profile Accordion */}
                        <div>
                          <button
                            type="button"
                            onClick={() => toggleQaAccordion(relId)}
                            style={{
                              background: 'none',
                              border: 'none',
                              padding: 0,
                              color: 'var(--accent-primary)',
                              fontSize: '0.8rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            {isQaExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                            <ShieldCheck size={14} />
                            <span>
                              {item.qa_profile ? `QA Profile (${item.qa_profile.criteria_assessments.length} criteria)` : 'QA Profile (Unavailable)'}
                            </span>
                          </button>

                          {isQaExpanded && (
                            <div
                              style={{
                                marginTop: '8px',
                                backgroundColor: 'var(--bg-primary)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: 'var(--radius-md)',
                                padding: '12px',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '8px',
                                fontSize: '0.8rem',
                              }}
                            >
                              {!item.qa_profile || item.qa_profile.criteria_assessments.length === 0 ? (
                                <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                  No Phase 8 Quality Assessment recorded for this publication. (Explicitly unweighted)
                                </div>
                              ) : (
                                item.qa_profile.criteria_assessments.map((qaItem, qaIdx) => (
                                  <div
                                    key={qaItem.criterion_id}
                                    style={{
                                      padding: '8px',
                                      backgroundColor: 'var(--bg-surface)',
                                      borderRadius: 'var(--radius-sm)',
                                      border: '1px solid var(--border-subtle)',
                                    }}
                                  >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                                      <div style={{ fontWeight: 600 }}>
                                        QA{qaIdx + 1}: {qaItem.question_text}
                                      </div>
                                      <span
                                        style={{
                                          padding: '2px 6px',
                                          borderRadius: 'var(--radius-sm)',
                                          backgroundColor:
                                            qaItem.response_value.toUpperCase() === 'YES'
                                              ? 'rgba(34, 197, 94, 0.15)'
                                              : qaItem.response_value.toUpperCase() === 'NO'
                                              ? 'rgba(239, 68, 68, 0.15)'
                                              : 'rgba(156, 163, 175, 0.15)',
                                          color:
                                            qaItem.response_value.toUpperCase() === 'YES'
                                              ? 'var(--status-success-text)'
                                              : qaItem.response_value.toUpperCase() === 'NO'
                                              ? 'var(--status-error-text)'
                                              : 'var(--text-muted)',
                                          fontSize: '0.7rem',
                                          fontWeight: 700,
                                          whiteSpace: 'nowrap',
                                        }}
                                      >
                                        {qaItem.response_value}
                                      </span>
                                    </div>
                                    {qaItem.justification && (
                                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px' }}>
                                        <em>Justification: {qaItem.justification}</em>
                                      </div>
                                    )}
                                  </div>
                                ))
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
