import React from 'react';
import { AlertTriangle, CheckSquare, Download, Search } from 'lucide-react';
import { FetchAllStatusResult, SearchExecutionResult, SearchResultsImportResponse } from '../../types';
import { Card } from '../common/Card';
import { FetchAllProgressPanel } from './FetchAllProgressPanel';

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
  fetchAllJob?: FetchAllStatusResult | null;
  fetchAllStarting?: boolean;
  fetchAllError?: string | null;
  onFetchAll?: () => void;
  onCancelFetchAll?: () => void;
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
  fetchAllJob = null,
  fetchAllStarting = false,
  fetchAllError = null,
  onFetchAll,
  onCancelFetchAll,
}) => {
  const [currentPage, setCurrentPage] = React.useState(1);
  const pageSize = 20;

  const totalLoaded = result ? result.results.length : 0;
  const totalLocalPages = Math.max(1, Math.ceil(totalLoaded / pageSize));
  const fetchAllActive = fetchAllJob?.status === 'running' || (fetchAllStarting && !fetchAllJob);

  React.useEffect(() => {
    setCurrentPage((prev) => Math.min(Math.max(1, prev), totalLocalPages));
  }, [totalLoaded, totalLocalPages]);

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

  const startIndex = (currentPage - 1) * pageSize;
  const visibleRecords = result.results.slice(startIndex, startIndex + pageSize);
  const allSelectedOnPage = visibleRecords.length > 0 && visibleRecords.every((record) => selectedIds.includes(record.id));
  const allSelectedInTotal = result.results.length > 0 && result.results.every((record) => selectedIds.includes(record.id));

  const togglePageSelection = (checked: boolean) => {
    const pageIds = visibleRecords.map((r) => r.id);
    if (checked) {
      onSelectionChange(Array.from(new Set([...selectedIds, ...pageIds])));
    } else {
      onSelectionChange(selectedIds.filter((id) => !pageIds.includes(id)));
    }
  };

  const toggleAllSelection = (checked: boolean) => {
    if (checked) {
      onSelectionChange(result.results.map((r) => r.id));
    } else {
      onSelectionChange([]);
    }
  };

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

      {result.results.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={allSelectedOnPage}
              onChange={(event) => togglePageSelection(event.target.checked)}
            />
            <CheckSquare size={15} />
            <span>Zaznacz wszystkie widoczne rekordy{totalLocalPages > 1 ? ` (strona ${currentPage})` : ''}</span>
          </label>

          {totalLocalPages > 1 && (
            <button
              type="button"
              onClick={() => toggleAllSelection(!allSelectedInTotal)}
              style={{
                fontSize: '0.78rem',
                color: 'var(--accent-primary)',
                background: 'none',
                border: 'none',
                padding: 0,
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              {allSelectedInTotal ? 'Odznacz wszystkie pobrane rekordy' : `Zaznacz wszystkie pobrane (${totalLoaded})`}
            </button>
          )}
        </div>
      )}

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

      {fetchAllError && (
        <div role="alert" style={{ color: 'var(--status-danger-text)', marginBottom: 12 }}>
          {fetchAllError}
        </div>
      )}

      {/* Fetch-all progress (v0.6.5): background retrieval of every available page */}
      {(onFetchAll || fetchAllJob) && (
        <FetchAllProgressPanel
          progress={fetchAllJob}
          starting={fetchAllStarting}
          onCancel={onCancelFetchAll}
        />
      )}

      {/* Fetch-all trigger (v0.6.5): retrieve every page each provider exposes */}
      {onFetchAll && !fetchAllActive && (
        <div
          style={{
            marginBottom: 12,
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
            border: '1px dashed var(--border-strong)',
            backgroundColor: 'var(--bg-surface-elevated)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Pobrano <strong>{totalLoaded}</strong> rekordów. Providerzy mogą udostępniać
            mniej wyników niż deklarowana łączna liczba trafień.
          </div>
          <button
            type="button"
            disabled={loadingMore}
            onClick={onFetchAll}
            data-testid="fetch-all-button"
            style={{
              padding: '7px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.82rem',
              opacity: loadingMore ? 0.55 : 1,
              cursor: loadingMore ? 'wait' : 'pointer',
            }}
          >
            Pobierz wszystkie dostępne
          </button>
        </div>
      )}

      {/* Provider Load More Section (Fetching additional batches from external API) */}
      {onLoadMore && result.has_more && !fetchAllActive && (
        <div
          style={{
            marginBottom: 12,
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
            border: '1px dashed var(--border-strong)',
            backgroundColor: 'var(--bg-surface-elevated)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Pobrano <strong>{totalLoaded}</strong> z <strong>{result.total_count}</strong> znalezionych w providerach.
          </div>
          <button
            type="button"
            disabled={loadingMore}
            onClick={onLoadMore}
            style={{
              padding: '7px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.82rem',
              opacity: loadingMore ? 0.55 : 1,
              cursor: loadingMore ? 'wait' : 'pointer',
            }}
          >
            {loadingMore ? 'Pobieranie…' : 'Pobierz kolejne wyniki'}
          </button>
        </div>
      )}

      {/* Local Pagination Bar (Navigation over already loaded records) */}
      {totalLocalPages > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            backgroundColor: 'var(--bg-surface-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            marginBottom: 12,
          }}
        >
          <button
            type="button"
            aria-label="Poprzednia strona"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            style={{
              padding: '5px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              fontWeight: 600,
              fontSize: '0.8rem',
              opacity: currentPage <= 1 ? 0.4 : 1,
              cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            ← Poprzednia
          </button>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Strona {currentPage} z {totalLocalPages} (rekordy {startIndex + 1}–{Math.min(startIndex + pageSize, totalLoaded)} z {totalLoaded})
          </span>
          <button
            type="button"
            aria-label="Następna strona"
            disabled={currentPage >= totalLocalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalLocalPages, p + 1))}
            style={{
              padding: '5px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              fontWeight: 600,
              fontSize: '0.8rem',
              opacity: currentPage >= totalLocalPages ? 0.4 : 1,
              cursor: currentPage >= totalLocalPages ? 'not-allowed' : 'pointer',
            }}
          >
            Następna →
          </button>
        </div>
      )}

      {/* Record list for visible local page */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {visibleRecords.map((record) => (
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
