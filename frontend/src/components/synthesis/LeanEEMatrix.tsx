import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Grid,
  Info,
  RefreshCw,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  MatrixCell,
  MatrixCellDetail,
  SynthesisMatrix,
} from '../../types/synthesis';
import { MatrixCellDetailModal } from './MatrixCellDetailModal';

interface LeanEEMatrixProps {
  projectId: string;
  onNavigateToClassifications?: () => void;
}

export const LeanEEMatrix: React.FC<LeanEEMatrixProps> = ({
  projectId,
  onNavigateToClassifications,
}) => {
  const [matrix, setMatrix] = useState<SynthesisMatrix | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Selected cell for drill-down modal
  const [selectedCell, setSelectedCell] = useState<{
    leanCatId: string;
    energyCatId: string;
  } | null>(null);
  const [cellDetail, setCellDetail] = useState<MatrixCellDetail | null>(null);
  const [cellDetailLoading, setCellDetailLoading] = useState<boolean>(false);
  const [cellDetailError, setCellDetailError] = useState<string | null>(null);

  const fetchMatrix = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await synthesisApi.getMatrix(projectId);
      setMatrix(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load analytical matrix';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchMatrix();
  }, [fetchMatrix]);

  const loadCellDetail = useCallback(
    async (leanCatId: string, energyCatId: string) => {
      setSelectedCell({ leanCatId, energyCatId });
      setCellDetailLoading(true);
      setCellDetailError(null);
      try {
        const detail = await synthesisApi.getCellDetail(projectId, leanCatId, energyCatId);
        setCellDetail(detail);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to load cell detail';
        setCellDetailError(msg);
      } finally {
        setCellDetailLoading(false);
      }
    },
    [projectId]
  );

  const handleCellClick = (cell: MatrixCell) => {
    if (cell.relation_count === 0) return;
    loadCellDetail(cell.lean_category_id, cell.energy_category_id);
  };

  const handleCloseModal = () => {
    setSelectedCell(null);
    setCellDetail(null);
    setCellDetailError(null);
  };

  const handleRelationUpdated = () => {
    fetchMatrix();
    if (selectedCell) {
      loadCellDetail(selectedCell.leanCatId, selectedCell.energyCatId);
    }
  };

  // Cell lookup map: (lean_cat_id, energy_cat_id) -> MatrixCell
  const cellMap = useMemo(() => {
    const map = new Map<string, MatrixCell>();
    if (matrix) {
      for (const cell of matrix.cells) {
        map.set(`${cell.lean_category_id}__${cell.energy_category_id}`, cell);
      }
    }
    return map;
  }, [matrix]);

  // Row and column totals
  const rowTotals = useMemo(() => {
    const totals: Record<string, { relations: number; pubs: Set<string> }> = {};
    if (matrix) {
      for (const lCat of matrix.lean_categories) {
        totals[lCat.category_id] = { relations: 0, pubs: new Set() };
      }
      for (const cell of matrix.cells) {
        if (totals[cell.lean_category_id]) {
          totals[cell.lean_category_id].relations += cell.relation_count;
        }
      }
    }
    return totals;
  }, [matrix]);

  const colTotals = useMemo(() => {
    const totals: Record<string, { relations: number; pubs: Set<string> }> = {};
    if (matrix) {
      for (const eCat of matrix.energy_categories) {
        totals[eCat.category_id] = { relations: 0, pubs: new Set() };
      }
      for (const cell of matrix.cells) {
        if (totals[cell.energy_category_id]) {
          totals[cell.energy_category_id].relations += cell.relation_count;
        }
      }
    }
    return totals;
  }, [matrix]);

  if (loading && !matrix) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px', gap: '12px' }}>
        <RefreshCw size={24} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
        <span>Calculating Lean–EE Analytical Matrix...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Matrix Header Banner */}
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
            <Grid size={22} style={{ color: 'var(--accent-primary)' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              Lean Practice × Energy Effect Analytical Matrix
            </h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '6px', marginBottom: 0 }}>
            Fundamental Synthesis Unit: <strong>Individual Lean–EE Relation</strong> ($1:N$ per study). Non-pooling guardrails enforce distinct metric integrity.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            type="button"
            data-testid="refresh-matrix-btn"
            onClick={fetchMatrix}
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
            <RefreshCw size={14} /> Refresh Matrix
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

      {/* KPI Stats */}
      {matrix && (
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
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Matrix Dimensions</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>
              {matrix.lean_categories.length} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>×</span> {matrix.energy_categories.length}
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
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Synthesized Relations</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--accent-primary)' }}>
              {matrix.total_relations}
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
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Contributing Studies</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: 'var(--status-success-text)' }}>
              {matrix.total_publications}
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
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Unclassified Relations</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: matrix.unclassified_relations_count > 0 ? 'var(--status-warning-text)' : 'var(--text-muted)' }}>
              {matrix.unclassified_relations_count}
            </div>
          </div>
        </div>
      )}

      {/* Unclassified Alert Banner */}
      {matrix && matrix.unclassified_relations_count > 0 && (
        <div
          style={{
            backgroundColor: 'rgba(234, 179, 8, 0.1)',
            border: '1px solid var(--status-warning-text)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
            fontSize: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={16} style={{ color: 'var(--status-warning-text)' }} />
            <span>
              <strong>{matrix.unclassified_relations_count}</strong> extracted Lean–EE relations have pending or unmapped source terms and are not assigned to matrix cells.
            </span>
          </div>

          {onNavigateToClassifications && (
            <button
              type="button"
              onClick={onNavigateToClassifications}
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                backgroundColor: 'var(--status-warning-text)',
                color: '#000',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: '0.75rem',
              }}
            >
              Open Classification Workspace
            </button>
          )}
        </div>
      )}

      {/* Main Matrix Grid Container */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}
      >
        {matrix && (matrix.lean_categories.length === 0 || matrix.energy_categories.length === 0) ? (
          <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Analytical Categories Not Configured
            </p>
            <p style={{ fontSize: '0.85rem', maxWidth: '500px', margin: '0 auto 16px' }}>
              The Lean–EE analytical matrix requires defined Lean Practice and Energy Effect analytical categories.
            </p>
            {onNavigateToClassifications && (
              <button
                type="button"
                onClick={onNavigateToClassifications}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  backgroundColor: 'var(--accent-primary)',
                  color: '#fff',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                }}
              >
                Go to Classification Workspace
              </button>
            )}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table
              data-testid="lean-ee-matrix-table"
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                textAlign: 'left',
                fontSize: '0.85rem',
              }}
            >
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-primary)', borderBottom: '2px solid var(--border-subtle)' }}>
                  <th
                    style={{
                      padding: '12px 16px',
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      width: '240px',
                      minWidth: '200px',
                      position: 'sticky',
                      left: 0,
                      backgroundColor: 'var(--bg-primary)',
                      zIndex: 2,
                      borderRight: '2px solid var(--border-subtle)',
                    }}
                  >
                    <div>Lean Practices (Rows)</div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--text-muted)' }}>
                      \ Energy Effects (Cols)
                    </div>
                  </th>

                  {matrix?.energy_categories.map((eCat) => (
                    <th
                      key={eCat.category_id}
                      style={{
                        padding: '12px 14px',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        minWidth: '150px',
                        textAlign: 'center',
                        borderRight: '1px solid var(--border-subtle)',
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>{eCat.name}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        <code>{eCat.category_id}</code>
                      </div>
                    </th>
                  ))}

                  <th
                    style={{
                      padding: '12px 16px',
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      width: '90px',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-primary)',
                    }}
                  >
                    Total
                  </th>
                </tr>
              </thead>

              <tbody>
                {matrix?.lean_categories.map((lCat) => {
                  const rowTotal = rowTotals[lCat.category_id]?.relations || 0;

                  return (
                    <tr
                      key={lCat.category_id}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                      }}
                    >
                      {/* Row Header (Lean Category) */}
                      <th
                        style={{
                          padding: '12px 16px',
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                          position: 'sticky',
                          left: 0,
                          backgroundColor: 'var(--bg-surface)',
                          zIndex: 1,
                          borderRight: '2px solid var(--border-subtle)',
                        }}
                      >
                        <div>{lCat.name}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                          <code>{lCat.category_id}</code>
                        </div>
                      </th>

                      {/* Matrix Intersection Cells */}
                      {matrix.energy_categories.map((eCat) => {
                        const cellKey = `${lCat.category_id}__${eCat.category_id}`;
                        const cell = cellMap.get(cellKey);
                        const relCount = cell?.relation_count || 0;
                        const pubCount = cell?.publication_count || 0;
                        const isNonEmpty = relCount > 0;

                        // Density styling
                        let cellBg = 'transparent';
                        if (relCount >= 4) {
                          cellBg = 'rgba(59, 130, 246, 0.2)';
                        } else if (relCount >= 2) {
                          cellBg = 'rgba(59, 130, 246, 0.1)';
                        } else if (relCount === 1) {
                          cellBg = 'rgba(59, 130, 246, 0.05)';
                        }

                        return (
                          <td
                            key={eCat.category_id}
                            data-testid={`matrix-cell-${lCat.category_id}-${eCat.category_id}`}
                            onClick={() => cell && handleCellClick(cell)}
                            style={{
                              padding: '10px 14px',
                              textAlign: 'center',
                              borderRight: '1px solid var(--border-subtle)',
                              backgroundColor: cellBg,
                              cursor: isNonEmpty ? 'pointer' : 'default',
                              transition: 'background-color 0.15s ease',
                            }}
                            title={
                              isNonEmpty
                                ? `${relCount} relations (${pubCount} distinct studies). Click to inspect.`
                                : 'No relations'
                            }
                          >
                            {isNonEmpty ? (
                              <div
                                style={{
                                  display: 'flex',
                                  flexDirection: 'column',
                                  alignItems: 'center',
                                  gap: '2px',
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: '1rem',
                                    fontWeight: 700,
                                    color: 'var(--accent-primary)',
                                  }}
                                >
                                  {relCount}
                                </span>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                  ({pubCount} {pubCount === 1 ? 'study' : 'studies'})
                                </span>
                              </div>
                            ) : (
                              <span style={{ color: 'var(--border-subtle)', fontSize: '0.85rem' }}>—</span>
                            )}
                          </td>
                        );
                      })}

                      {/* Row Total */}
                      <td
                        style={{
                          padding: '12px 16px',
                          textAlign: 'center',
                          fontWeight: 700,
                          color: rowTotal > 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                          backgroundColor: 'rgba(0, 0, 0, 0.02)',
                        }}
                      >
                        {rowTotal}
                      </td>
                    </tr>
                  );
                })}

                {/* Column Totals Footer Row */}
                <tr
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    borderTop: '2px solid var(--border-subtle)',
                    fontWeight: 700,
                  }}
                >
                  <th
                    style={{
                      padding: '12px 16px',
                      position: 'sticky',
                      left: 0,
                      backgroundColor: 'var(--bg-primary)',
                      zIndex: 1,
                      borderRight: '2px solid var(--border-subtle)',
                    }}
                  >
                    Total Relations
                  </th>

                  {matrix?.energy_categories.map((eCat) => {
                    const colTotal = colTotals[eCat.category_id]?.relations || 0;
                    return (
                      <td
                        key={eCat.category_id}
                        style={{
                          padding: '12px 14px',
                          textAlign: 'center',
                          borderRight: '1px solid var(--border-subtle)',
                          color: colTotal > 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                        }}
                      >
                        {colTotal}
                      </td>
                    );
                  })}

                  <td
                    style={{
                      padding: '12px 16px',
                      textAlign: 'center',
                      color: 'var(--accent-primary)',
                      fontSize: '1rem',
                    }}
                  >
                    {matrix?.total_relations || 0}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Non-pooling Methodological Guardrail Notice */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <Info size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <span>
          <strong>Methodological Non-Pooling Guardrail:</strong> Matrix cells present relation and study frequencies. Aggregating numerical effect magnitudes across distinct energy metrics (e.g. absolute consumption vs. intensity) is methodologically prohibited.
        </span>
      </div>

      {/* Cell Drill-Down Modal */}
      {selectedCell && (
        <MatrixCellDetailModal
          projectId={projectId}
          detail={cellDetail}
          loading={cellDetailLoading}
          error={cellDetailError}
          onClose={handleCloseModal}
          onRelationUpdated={handleRelationUpdated}
        />
      )}
    </div>
  );
};
