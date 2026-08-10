import React from 'react';
import { AlertTriangle, CheckSquare, Download, Search } from 'lucide-react';
import { SearchExecutionResult, SearchResultsImportResponse } from '../../types';
import { Card } from '../common/Card';

interface Props {
  result: SearchExecutionResult | null;
  loading: boolean;
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  importing?: boolean;
  onImport?: () => void;
  importResult?: SearchResultsImportResponse | null;
  loadingMore?: boolean;
  paginationError?: string | null;
  onLoadMore?: () => void;
}

export const SearchResultsSection: React.FC<Props> = ({
  result,
  loading,
  selectedIds,
  onSelectionChange,
  importing = false,
  onImport,
  importResult = null,
  loadingMore = false,
  paginationError = null,
  onLoadMore,
}) => {
  if (loading) {
    return (
      <Card title="Wyniki wyszukiwania">
        <div role="status" style={{ color: 'var(--text-secondary)' }}>Wyszukiwanie…</div>
      </Card>
    );
  }
  if (!result) {
    return (
      <Card title="Wyniki wyszukiwania">
        <div style={{ color: 'var(--text-secondary)' }}>Brak wykonanych wyszukiwań.</div>
      </Card>
    );
  }
  const allSelected = result.results.every((record) => selectedIds.includes(record.id));
  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Search size={18} style={{ color: 'var(--accent-primary)' }} />
          <span>Wyniki wyszukiwania</span>
        </div>
      }
      subtitle={`Znaleziono ${result.total_count} rekordów. Zwrócono ${result.returned_count}. Wybrano ${selectedIds.length}.`}
    >
      {result.provider_queries && result.provider_queries.length > 0 && (
        <div style={{ marginBottom: 12, padding: 10, borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', fontSize: '0.8rem' }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Wykonane zapytania providerów:</div>
          {result.provider_queries.map((pq) => (
            <div key={pq.provider} style={{ marginTop: 4 }}>
              <span style={{ fontWeight: 600 }}>{pq.provider}:</span> <code>{pq.rendered_query}</code>
              {pq.is_lossless === false && (
                <span style={{ marginLeft: 6, color: 'var(--status-warning-text)', fontSize: '0.75rem' }}>
                  (Dostosowano składnię/ograniczenia)
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {result.results.length === 0 && (
        <div style={{ color: 'var(--text-secondary)', marginBottom: 12 }}>
          Nie znaleziono rekordów dla tej strategii.
        </div>
      )}
      {result.provider_errors && result.provider_errors.length > 0 && (
        <div
          role="alert"
          style={{
            display: 'flex',
            gap: 8,
            marginBottom: 12,
            padding: 10,
            border: '1px solid var(--status-warning-border)',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
          }}
        >
          <AlertTriangle size={17} />
          <span>
            Część providerów nie odpowiedziała:{' '}
            {result.provider_errors.map((error) => error.provider).join(', ')}.
          </span>
        </div>
      )}
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <input
          type="checkbox"
          checked={allSelected}
          onChange={(event) => onSelectionChange(
            event.target.checked ? result.results.map((record) => record.id) : []
          )}
        />
        <CheckSquare size={15} />
        Zaznacz wszystkie widoczne rekordy
      </label>
      {onImport && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <button
            type="button"
            disabled={selectedIds.length === 0 || importing}
            onClick={onImport}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 700,
              opacity: selectedIds.length === 0 || importing ? 0.5 : 1,
            }}
          >
            <Download size={15} />
            {importing ? 'Importowanie…' : 'Importuj zaznaczone'}
          </button>
          {importResult !== null && (
            <span role="status" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Zaimportowano: {importResult.imported_count}. Pominięto istniejące:{' '}
              {importResult.skipped_count}. Working Collection:{' '}
              {importResult.working_collection_count}.
            </span>
          )}
        </div>
      )}
      {paginationError && (
        <div role="alert" style={{ color: 'var(--status-danger-text)', marginBottom: 12 }}>
          {paginationError}
        </div>
      )}
      {onLoadMore && result.has_more && (
        <button
          type="button"
          disabled={loadingMore}
          onClick={onLoadMore}
          style={{
            marginBottom: 12,
            padding: '8px 14px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-strong)',
            fontWeight: 700,
            opacity: loadingMore ? 0.55 : 1,
          }}
        >
          {loadingMore ? 'Pobieranie…' : 'Pobierz kolejne wyniki'}
        </button>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {result.results.map((record) => (
          <label
            key={record.id}
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              gap: 12,
              padding: 14,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-primary)',
              cursor: 'pointer',
            }}
          >
            <input
              aria-label={`Wybierz rekord ${record.title}`}
              type="checkbox"
              checked={selectedIds.includes(record.id)}
              onChange={(event) => onSelectionChange(
                event.target.checked
                  ? [...selectedIds, record.id]
                  : selectedIds.filter((id) => id !== record.id)
              )}
            />
            <div>
              <div style={{ fontWeight: 700 }}>{record.title}</div>
              <div style={{ marginTop: 4, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {record.authors.join(', ')} · {record.year} · Provider: {record.provider}
              </div>
              {record.doi && (
                <div style={{ marginTop: 3, fontSize: '0.78rem', color: 'var(--status-info-text)' }}>
                  DOI: {record.doi}
                </div>
              )}
            </div>
          </label>
        ))}
      </div>
    </Card>
  );
};
