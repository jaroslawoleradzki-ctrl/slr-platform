import React, { useState } from 'react';
import { Search, ExternalLink, Filter, CheckCircle2, Clock, FileX, AlertCircle } from 'lucide-react';
import {
  ExtractionCompletenessStatus,
  ExtractionEligibilityStatus,
} from '../../api/extractionApi';

export interface ExtractionPublicationRow {
  publication_id: string;
  title?: string | null;
  authors?: string[];
  publication_year?: number | null;
  extraction_status: ExtractionCompletenessStatus;
  latest_revision_index?: number | null;
  latest_reviewer_id?: string | null;
  latest_updated_at?: string | null;
  is_eligible: boolean;
  eligibility_status: ExtractionEligibilityStatus;
  eligibility_reason?: string | null;
}

interface ExtractionTableViewProps {
  records: ExtractionPublicationRow[];
  isLoading: boolean;
  onSelectPublication: (publicationId: string) => void;
}

export const ExtractionTableView: React.FC<ExtractionTableViewProps> = ({
  records,
  isLoading,
  onSelectPublication,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filteredRecords = records.filter((rec) => {
    // Status filter
    if (statusFilter !== 'all' && rec.extraction_status !== statusFilter) {
      return false;
    }
    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const titleMatch = rec.title?.toLowerCase().includes(q) ?? false;
      const authorsMatch = rec.authors?.some((a) => a.toLowerCase().includes(q)) ?? false;
      const idMatch = rec.publication_id.toLowerCase().includes(q);
      if (!titleMatch && !authorsMatch && !idMatch) return false;
    }
    return true;
  });

  const renderStatusBadge = (status: ExtractionCompletenessStatus) => {
    switch (status) {
      case 'complete':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--status-success-bg)',
              color: 'var(--status-success-text)',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            <CheckCircle2 size={12} /> Zakończone
          </span>
        );
      case 'in_progress':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--status-info-bg)',
              color: 'var(--accent-primary)',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            <Clock size={12} /> W trakcie
          </span>
        );
      case 'needs_review':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--status-warning-bg)',
              color: 'var(--status-warning-text)',
              fontSize: '0.75rem',
              fontWeight: 600,
            }}
          >
            <AlertCircle size={12} /> Do weryfikacji
          </span>
        );
      case 'not_started':
      default:
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-surface-elevated)',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
              fontWeight: 500,
            }}
          >
            <FileX size={12} /> Nie rozpoczęto
          </span>
        );
    }
  };

  if (isLoading) {
    return (
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        Ładowanie zestawienia publikacji...
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
      }}
    >
      {/* Controls Header: Search & Filter */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          backgroundColor: 'var(--bg-surface-elevated)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '240px' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: '360px' }}>
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
            <input
              type="text"
              placeholder="Szukaj po tytule lub autorze..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 12px 6px 32px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
              }}
              aria-label="Szukaj publikacji"
            />
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={16} style={{ color: 'var(--text-muted)' }} />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
            aria-label="Filtruj według statusu ekstrakcji"
          >
            <option value="all">Wszystkie statusy</option>
            <option value="not_started">Nie rozpoczęto</option>
            <option value="in_progress">W trakcie (Draft)</option>
            <option value="complete">Zakończone (Complete)</option>
            <option value="needs_review">Do weryfikacji (Needs Review)</option>
          </select>
        </div>
      </div>

      {/* Summary Table */}
      {filteredRecords.length === 0 ? (
        <div
          style={{
            padding: '40px',
            textAlign: 'center',
            color: 'var(--text-muted)',
            fontSize: '0.9rem',
          }}
        >
          {records.length === 0
            ? 'Brak zakwalifikowanych publikacji do ekstrakcji w tym projekcie.'
            : 'Brak wyników spełniających podane kryteria wyszukiwania.'}
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                <th style={{ padding: '12px 16px' }}>Publikacja</th>
                <th style={{ padding: '12px 16px', width: '80px' }}>Rok</th>
                <th style={{ padding: '12px 16px', width: '140px' }}>Status Ekstrakcji</th>
                <th style={{ padding: '12px 16px', width: '150px' }}>Kwalifikowalność</th>
                <th style={{ padding: '12px 16px', width: '110px' }}>Wersja (Rev)</th>
                <th style={{ padding: '12px 16px', width: '130px' }}>Recenzent</th>
                <th style={{ padding: '12px 16px', width: '140px' }}>Ostatnia zmiana</th>
                <th style={{ padding: '12px 16px', width: '120px', textAlign: 'right' }}>Akcja</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((rec) => (
                <tr
                  key={rec.publication_id}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    transition: 'background-color 0.15s ease',
                  }}
                >
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
                      {rec.title || rec.publication_id}
                    </div>
                    {rec.authors && rec.authors.length > 0 && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {rec.authors.join(', ')}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                    {rec.publication_year || '—'}
                  </td>
                  <td style={{ padding: '12px 16px' }}>{renderStatusBadge(rec.extraction_status)}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span
                      title={rec.eligibility_reason || rec.eligibility_status}
                      style={{
                        color: rec.is_eligible ? 'var(--status-success-text)' : 'var(--status-warning-text)',
                        fontWeight: 600,
                        fontSize: '0.75rem',
                      }}
                    >
                      {rec.is_eligible ? 'Kwalifikowalna' : `Zablokowana: ${rec.eligibility_status}`}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                    {rec.latest_revision_index !== null && rec.latest_revision_index !== undefined
                      ? `Rev #${rec.latest_revision_index}`
                      : '—'}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                    {rec.latest_reviewer_id || '—'}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {rec.latest_updated_at
                      ? new Date(rec.latest_updated_at).toLocaleString('pl-PL', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '—'}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <button
                      type="button"
                      disabled={!rec.is_eligible}
                      onClick={() => onSelectPublication(rec.publication_id)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '6px 12px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-subtle)',
                        backgroundColor: 'var(--bg-primary)',
                        color: rec.is_eligible ? 'var(--accent-primary)' : 'var(--text-muted)',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: rec.is_eligible ? 'pointer' : 'not-allowed',
                      }}
                      title={rec.is_eligible ? 'Otwórz formularz ekstrakcji dla tej publikacji' : rec.eligibility_reason || 'Publikacja zablokowana'}
                      aria-label={
                        rec.is_eligible
                          ? `Otwórz formularz ekstrakcji dla ${rec.title || rec.publication_id}`
                          : `Publikacja ${rec.title || rec.publication_id} jest zablokowana`
                      }
                    >
                      {rec.is_eligible ? 'Workspace' : 'Zablokowana'} <ExternalLink size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
