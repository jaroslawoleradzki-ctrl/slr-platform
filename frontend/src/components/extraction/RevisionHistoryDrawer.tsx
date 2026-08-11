import React from 'react';
import { X, History, Clock, User } from 'lucide-react';
import { ExtractionRevisionHistoryResponseDTO } from '../../api/extractionApi';

interface RevisionHistoryDrawerProps {
  isOpen: boolean;
  history: ExtractionRevisionHistoryResponseDTO | null;
  onClose: () => void;
}

export const RevisionHistoryDrawer: React.FC<RevisionHistoryDrawerProps> = ({
  isOpen,
  history,
  onClose,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '420px',
        backgroundColor: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-strong)',
        boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.25)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
      }}
      role="dialog"
      aria-label="Historia rewizji wydobycia danych"
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--bg-surface-elevated)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <History size={18} style={{ color: 'var(--accent-primary)' }} />
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Historia rewizji (Append-Only)
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {!history || history.revisions.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', padding: '24px' }}>
            Brak historii rewizji dla tej publikacji.
          </div>
        ) : (
          history.revisions.map((rev) => {
            const isComplete = rev.completeness_status === 'complete';
            const formattedDate = new Date(rev.created_at).toLocaleString('pl-PL', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <div
                key={rev.revision_id}
                style={{
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-primary)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Rewizja #{rev.revision_index}
                  </span>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-full)',
                      backgroundColor: isComplete ? 'var(--status-success-bg)' : 'var(--bg-surface-elevated)',
                      color: isComplete ? 'var(--status-success-text)' : 'var(--text-muted)',
                    }}
                  >
                    {isComplete ? 'COMPLETE' : 'IN_PROGRESS'}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <User size={12} /> {rev.reviewer_id}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={12} /> {formattedDate}
                  </span>
                </div>

                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Liczba pól publikacji: {rev.publication_values.length} | Liczba elementów grup: {rev.group_items.length}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
