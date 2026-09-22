import React, { useCallback, useEffect, useState } from 'react';
import {
  Search,
  X,
  RotateCcw,
  Trash2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  ImportedRecord,
  PreScreeningRemovalReason,
  PRE_SCREENING_REMOVAL_REASON_LABELS,
} from '../../types';
import { projectApiService } from '../../services/api/projectApi';
import { Modal } from '../common/Modal';
import { Badge } from '../common/Badge';

interface ImportedRecordsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  importId: string;
  importTitle: string;
  onCountsUpdated?: () => void;
}

const PAGE_SIZE = 20;

export const ImportedRecordsModal: React.FC<ImportedRecordsModalProps> = ({
  isOpen,
  onClose,
  projectId,
  importId,
  importTitle,
  onCountsUpdated,
}) => {
  const [records, setRecords] = useState<ImportedRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [offset, setOffset] = useState<number>(0);
  const [counts, setCounts] = useState<{
    total_imported: number;
    retained_count: number;
    removed_count: number;
  }>({ total_imported: 0, retained_count: 0, removed_count: 0 });

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'retained' | 'removed'>('all');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedAbstracts, setExpandedAbstracts] = useState<Set<string>>(new Set());

  // Removal dialog state
  const [recordToRemove, setRecordToRemove] = useState<ImportedRecord | null>(null);
  const [removalReason, setRemovalReason] = useState<PreScreeningRemovalReason>('clearly_outside_scope');
  const [removalNotes, setRemovalNotes] = useState<string>('');
  const [removalError, setRemovalError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const fetchRecords = useCallback(
    async (pageOffset: number, search: string, filter: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await projectApiService.getImportedRecords(projectId, importId, {
          search: search.trim() || undefined,
          status_filter: filter !== 'all' ? filter : undefined,
          offset: pageOffset,
          limit: PAGE_SIZE,
        });
        setRecords(res.items);
        setTotal(res.total);
        setCounts({
          total_imported: res.total_imported,
          retained_count: res.retained_count,
          removed_count: res.removed_count,
        });
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Nie udało się pobrać rekordów.');
      } finally {
        setLoading(false);
      }
    },
    [projectId, importId],
  );

  useEffect(() => {
    if (isOpen) {
      setOffset(0);
      setSearchQuery('');
      setStatusFilter('all');
      void fetchRecords(0, '', 'all');
    }
  }, [isOpen, fetchRecords]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    void fetchRecords(0, searchQuery, statusFilter);
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setOffset(0);
    void fetchRecords(0, '', statusFilter);
  };

  const handleFilterChange = (newFilter: 'all' | 'retained' | 'removed') => {
    setStatusFilter(newFilter);
    setOffset(0);
    void fetchRecords(0, searchQuery, newFilter);
  };

  const handlePrevPage = () => {
    const newOffset = Math.max(0, offset - PAGE_SIZE);
    setOffset(newOffset);
    void fetchRecords(newOffset, searchQuery, statusFilter);
  };

  const handleNextPage = () => {
    const newOffset = offset + PAGE_SIZE;
    if (newOffset < total) {
      setOffset(newOffset);
      void fetchRecords(newOffset, searchQuery, statusFilter);
    }
  };

  const toggleAbstract = (recordId: string) => {
    setExpandedAbstracts((prev) => {
      const next = new Set(prev);
      if (next.has(recordId)) {
        next.delete(recordId);
      } else {
        next.add(recordId);
      }
      return next;
    });
  };

  const handleOpenRemovalDialog = (record: ImportedRecord) => {
    setRecordToRemove(record);
    setRemovalReason('clearly_outside_scope');
    setRemovalNotes('');
    setRemovalError(null);
  };

  const handleConfirmRemoval = async () => {
    if (!recordToRemove) return;
    if (removalReason === 'other' && !removalNotes.trim()) {
      setRemovalError('Podanie notatki jest wymagane w przypadku wyboru powodu "Inny".');
      return;
    }

    setActionInProgress(recordToRemove.record_id);
    setRemovalError(null);
    try {
      await projectApiService.removeImportedRecord(projectId, importId, recordToRemove.record_id, {
        reason: removalReason,
        notes: removalNotes.trim() || undefined,
        reviewer_id: 'default_reviewer',
      });
      setRecordToRemove(null);
      void fetchRecords(offset, searchQuery, statusFilter);
      if (onCountsUpdated) onCountsUpdated();
    } catch (err: unknown) {
      setRemovalError(err instanceof Error ? err.message : 'Nie udało się usunąć rekordu.');
    } finally {
      setActionInProgress(null);
    }
  };

  const handleRestoreRecord = async (record: ImportedRecord) => {
    setActionInProgress(record.record_id);
    try {
      await projectApiService.restoreImportedRecord(projectId, importId, record.record_id, {
        reviewer_id: 'default_reviewer',
      });
      void fetchRecords(offset, searchQuery, statusFilter);
      if (onCountsUpdated) onCountsUpdated();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Nie udało się przywrócić rekordu.');
    } finally {
      setActionInProgress(null);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Przegląd Zaimportowanych Rekordów (Pre-Screening Corpus Review)"
      maxWidth="950px"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Source metadata & PRISMA Invariant note */}
        <div
          style={{
            backgroundColor: 'var(--bg-primary)',
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Źródło / Import: <span style={{ color: 'var(--accent-primary)' }}>{importTitle}</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              ID: {importId}
            </div>
          </div>

          <div
            style={{
              fontSize: '0.78rem',
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-surface)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              borderLeft: '3px solid var(--accent-primary)',
            }}
          >
            <strong>Reguła PRISMA:</strong> Rekordy usunięte na tym etapie nie są wliczane do puli formalnego screeningu (Title/Abstract) i nie zniekształcają wskaźnika &quot;records screened&quot;.
          </div>

          {/* Counts summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginTop: '4px' }}>
            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Łącznie pobrano</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                {counts.total_imported}
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: 'var(--status-success-text)' }}>
                Zachowane do Screeningu
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--status-success-text)' }}>
                {counts.retained_count}
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: 'var(--status-error-text)' }}>
                Usunięte przed Screeningiem
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--status-error-text)' }}>
                {counts.removed_count}
              </div>
            </div>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <form
            onSubmit={handleSearchSubmit}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '1 1 300px' }}
          >
            <div style={{ position: 'relative', width: '100%' }}>
              <input
                type="text"
                placeholder="Szukaj po tytule, autorach, DOI..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 32px 8px 32px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-strong)',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                }}
              />
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={handleClearSearch}
                  style={{
                    position: 'absolute',
                    right: '10px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                  title="Wyczyść wyszukiwanie"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <button
              type="submit"
              style={{
                padding: '8px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--accent-primary)',
                color: '#fff',
                fontSize: '0.85rem',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Szukaj
            </button>
          </form>

          {/* Status Filters */}
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '4px' }}>Status:</span>
            {(['all', 'retained', 'removed'] as const).map((filterVal) => {
              const isActive = statusFilter === filterVal;
              const labels: Record<string, string> = {
                all: `Wszystkie (${counts.total_imported})`,
                retained: `Zachowane (${counts.retained_count})`,
                removed: `Usunięte (${counts.removed_count})`,
              };
              return (
                <button
                  key={filterVal}
                  type="button"
                  onClick={() => handleFilterChange(filterVal)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    fontWeight: isActive ? 600 : 400,
                    backgroundColor: isActive ? 'var(--accent-primary)' : 'var(--bg-surface-elevated)',
                    color: isActive ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                  }}
                >
                  {labels[filterVal]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div
            role="alert"
            style={{
              padding: '10px 14px',
              backgroundColor: 'var(--status-error-bg)',
              color: 'var(--status-error-text)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
            }}
          >
            {error}
          </div>
        )}

        {/* Records List */}
        <div
          style={{
            maxHeight: '440px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            paddingRight: '4px',
          }}
        >
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Ładowanie rekordów...
            </div>
          ) : records.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '40px',
                color: 'var(--text-muted)',
                fontSize: '0.9rem',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              Brak rekordów spełniających wybrane kryteria wyszukiwania.
            </div>
          ) : (
            records.map((record) => {
              const isRemoved = record.pre_screening_status === 'removed';
              const isExpanded = expandedAbstracts.has(record.record_id);
              const isBusy = actionInProgress === record.record_id;

              return (
                <div
                  key={record.record_id}
                  style={{
                    backgroundColor: isRemoved ? 'var(--bg-primary)' : 'var(--bg-surface)',
                    border: isRemoved ? '1px solid var(--border-subtle)' : '1px solid var(--border-strong)',
                    opacity: isRemoved ? 0.85 : 1,
                    borderRadius: 'var(--radius-md)',
                    padding: '14px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    position: 'relative',
                  }}
                >
                  {/* Top line: Status Badge & Actions */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                    <div>
                      {isRemoved ? (
                        <Badge variant="pending_action" icon={<AlertCircle size={12} />}>
                          Usunięty z pre-screeningu
                        </Badge>
                      ) : (
                        <Badge variant="completed" icon={<CheckCircle2 size={12} />}>
                          Zachowany do Screeningu
                        </Badge>
                      )}
                    </div>

                    <div>
                      {isRemoved ? (
                        <button
                          type="button"
                          onClick={() => handleRestoreRecord(record)}
                          disabled={isBusy}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-strong)',
                            backgroundColor: 'var(--bg-surface)',
                            color: 'var(--accent-primary)',
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            cursor: isBusy ? 'not-allowed' : 'pointer',
                          }}
                        >
                          <RotateCcw size={14} />
                          {isBusy ? 'Przywracanie...' : 'Przywróć (Undo)'}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleOpenRemovalDialog(record)}
                          disabled={isBusy}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-subtle)',
                            backgroundColor: 'var(--bg-surface-elevated)',
                            color: 'var(--status-error-text)',
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            cursor: isBusy ? 'not-allowed' : 'pointer',
                          }}
                        >
                          <Trash2 size={14} />
                          Usuń z korpusu
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Title */}
                  <div
                    style={{
                      fontSize: '0.95rem',
                      fontWeight: 600,
                      color: isRemoved ? 'var(--text-muted)' : 'var(--text-primary)',
                      textDecoration: isRemoved ? 'line-through' : 'none',
                    }}
                  >
                    {record.title}
                  </div>

                  {/* Authors & Year & Journal */}
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    <span>{record.authors.length > 0 ? record.authors.join('; ') : 'Brak danych o autorach'}</span>
                    {record.publication_year && <span>• ({record.publication_year})</span>}
                    {record.venue_name && <span>• <em>{record.venue_name}</em></span>}
                    {record.doi && (
                      <span>
                        •{' '}
                        <a
                          href={`https://doi.org/${record.doi}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'var(--accent-primary)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                        >
                          DOI: {record.doi} <ExternalLink size={11} />
                        </a>
                      </span>
                    )}
                  </div>

                  {/* Removal audit info if removed */}
                  {isRemoved && record.removal_reason && (
                    <div
                      style={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '8px 12px',
                        fontSize: '0.78rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        marginTop: '4px',
                      }}
                    >
                      <div>
                        <strong>Powód usunięcia:</strong>{' '}
                        <span style={{ color: 'var(--status-error-text)' }}>
                          {PRE_SCREENING_REMOVAL_REASON_LABELS[record.removal_reason] ?? record.removal_reason}
                        </span>
                      </div>
                      {record.removal_notes && (
                        <div>
                          <strong>Notatka:</strong> {record.removal_notes}
                        </div>
                      )}
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Oznaczone przez: {record.reviewer_id ?? 'użytkownika'}{' '}
                        {record.decided_at ? `(${new Date(record.decided_at).toLocaleString('pl-PL')})` : ''}
                      </div>
                    </div>
                  )}

                  {/* Expandable abstract */}
                  {record.abstract && (
                    <div style={{ marginTop: '2px' }}>
                      <button
                        type="button"
                        onClick={() => toggleAbstract(record.record_id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--accent-primary)',
                          fontSize: '0.75rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          cursor: 'pointer',
                          padding: 0,
                        }}
                      >
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? 'Ukryj abstrakt' : 'Pokaż abstrakt'}
                      </button>
                      {isExpanded && (
                        <div
                          style={{
                            marginTop: '6px',
                            fontSize: '0.8rem',
                            color: 'var(--text-secondary)',
                            backgroundColor: 'var(--bg-primary)',
                            padding: '10px 12px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-subtle)',
                            whiteSpace: 'pre-wrap',
                          }}
                        >
                          {record.abstract}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Pagination Bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            paddingTop: '8px',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Łącznie znaleziono: <strong>{total}</strong> rekordów • Strona {currentPage} z {totalPages}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={handlePrevPage}
              disabled={offset === 0 || loading}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-strong)',
                backgroundColor: 'var(--bg-surface)',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                cursor: offset === 0 || loading ? 'not-allowed' : 'pointer',
                opacity: offset === 0 || loading ? 0.5 : 1,
              }}
            >
              Poprzednia
            </button>
            <button
              type="button"
              onClick={handleNextPage}
              disabled={offset + PAGE_SIZE >= total || loading}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-strong)',
                backgroundColor: 'var(--bg-surface)',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                cursor: offset + PAGE_SIZE >= total || loading ? 'not-allowed' : 'pointer',
                opacity: offset + PAGE_SIZE >= total || loading ? 0.5 : 1,
              }}
            >
              Następna
            </button>
          </div>
        </div>
      </div>

      {/* Controlled Removal Modal */}
      {recordToRemove && (
        <Modal
          isOpen={true}
          onClose={() => setRecordToRemove(null)}
          title="Usuń Rekord przed Screeningiem"
          maxWidth="500px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Usuwasz rekord z korpusu przed formalnym etapem screeningu. Rekord pozostanie zarchiwizowany w bazie i audytowalny.
            </div>

            <div
              style={{
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
                backgroundColor: 'var(--bg-primary)',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              {recordToRemove.title}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Wybierz powód wykluczenia:
              </label>
              <select
                value={removalReason}
                onChange={(e) => setRemovalReason(e.target.value as PreScreeningRemovalReason)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-strong)',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                }}
              >
                {Object.entries(PRE_SCREENING_REMOVAL_REASON_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Notatka / Uzasadnienie {removalReason === 'other' ? '(wymagane)' : '(opcjonalnie)'}:
              </label>
              <textarea
                rows={3}
                value={removalNotes}
                onChange={(e) => setRemovalNotes(e.target.value)}
                placeholder={
                  removalReason === 'other'
                    ? 'Opisz powód usunięcia rekordu...'
                    : 'Opcjonalne szczegóły dla zespołu badawczego...'
                }
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-strong)',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                  resize: 'vertical',
                }}
              />
            </div>

            {removalError && (
              <div
                role="alert"
                style={{
                  color: 'var(--status-error-text)',
                  fontSize: '0.8rem',
                  backgroundColor: 'var(--status-error-bg)',
                  padding: '8px',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                {removalError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
              <button
                type="button"
                onClick={() => setRecordToRemove(null)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-strong)',
                  backgroundColor: 'var(--bg-surface)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Anuluj
              </button>
              <button
                type="button"
                onClick={handleConfirmRemoval}
                disabled={actionInProgress !== null}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  backgroundColor: 'var(--status-error-text)',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: actionInProgress !== null ? 'not-allowed' : 'pointer',
                }}
              >
                {actionInProgress !== null ? 'Usuwanie...' : 'Zatwierdź usunięcie'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </Modal>
  );
};
