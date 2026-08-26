import React from 'react';
import {
  AlertTriangle,
  CheckSquare,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  FileText,
  Search,
} from 'lucide-react';
import {
  FetchAllStatusResult,
  ProviderQuery,
  SearchExecutionResult,
  SearchResultsImportResponse,
} from '../../types';
import { Card } from '../common/Card';
import { FetchAllProgressPanel, ghostButtonStyle } from './FetchAllProgressPanel';

const PROVIDER_LABELS: Record<string, string> = {
  openalex: 'OpenAlex',
  crossref: 'Crossref',
  semantic_scholar: 'Semantic Scholar',
};

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
  onResumeFetchAll?: () => void;
}

/** Collapsible query definition: canonical query stays visible in one line,
 * full provider queries are available on demand; lossless warnings stay visible always. */
const QueryPreview: React.FC<{ result: SearchExecutionResult }> = ({ result }) => {
  const [expanded, setExpanded] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const providerQueries = result.provider_queries ?? [];
  const adjustedProviders = providerQueries.filter((pq) => pq.is_lossless === false);
  const fullText =
    providerQueries.length > 0
      ? providerQueries
          .map((pq) => `${PROVIDER_LABELS[pq.provider] ?? pq.provider}: ${pq.rendered_query}`)
          .join('\n')
      : result.rendered_query;

  const copyQuery = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(fullText);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = fullText;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — silently ignore
    }
  };

  return (
    <div
      data-testid="query-preview"
      style={{
        marginBottom: 12,
        padding: '8px 12px',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--bg-primary)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.78rem', fontWeight: 700 }}>
          <FileText size={13} style={{ color: 'var(--accent-primary)' }} />
          Zapytanie
        </span>
        {adjustedProviders.map((pq) => (
          <span
            key={`warn-${pq.provider}`}
            style={{
              fontSize: '0.7rem',
              color: 'var(--status-warning-text)',
              border: '1px solid var(--status-warning-border)',
              backgroundColor: 'var(--status-warning-bg)',
              borderRadius: 'var(--radius-full)',
              padding: '1px 8px',
            }}
          >
            {PROVIDER_LABELS[pq.provider] ?? pq.provider}: dostosowano składnię/ograniczenia
          </span>
        ))}
        <span style={{ flex: 1 }} />
        <button type="button" onClick={() => void copyQuery()} style={{ ...ghostButtonStyle, padding: '3px 9px' }}>
          <Copy size={11} style={{ marginRight: 4, verticalAlign: -1 }} />
          {copied ? 'Skopiowano' : 'Kopiuj'}
        </button>
        <button
          type="button"
          data-testid="query-preview-toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((prev) => !prev)}
          style={{ ...ghostButtonStyle, padding: '3px 9px' }}
        >
          {expanded ? (
            <>
              <ChevronUp size={11} style={{ marginRight: 4, verticalAlign: -1 }} />Ukryj
            </>
          ) : (
            <>
              <ChevronDown size={11} style={{ marginRight: 4, verticalAlign: -1 }} />
              Pokaż pełne zapytania
            </>
          )}
        </button>
      </div>

      {!expanded && (
        <code
          data-testid="query-preview-summary"
          title={result.rendered_query}
          style={{
            display: 'block',
            marginTop: 6,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {result.rendered_query}
        </code>
      )}

      {expanded && (
        <div data-testid="query-preview-details" style={{ marginTop: 6 }}>
          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700, color: 'var(--text-muted)' }}>
            Canonical query
          </div>
          <pre style={{ margin: '2px 0 8px', padding: 8, borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface)', fontSize: '0.76rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {result.rendered_query}
          </pre>
          {providerQueries.map((pq) => (
            <ProviderQueryLine key={pq.provider} query={pq} />
          ))}
        </div>
      )}
    </div>
  );
};

const ProviderQueryLine: React.FC<{ query: ProviderQuery }> = ({ query }) => (
  <div>
    <div style={{ marginTop: 4, fontSize: '0.75rem', fontWeight: 600 }}>
      {PROVIDER_LABELS[query.provider] ?? query.provider}
      {query.is_lossless === false && (
        <span style={{ marginLeft: 6, color: 'var(--status-warning-text)', fontSize: '0.72rem' }}>
          (Dostosowano składnię/ograniczenia)
        </span>
      )}
    </div>
    <pre style={{ margin: '2px 0 6px', padding: 8, borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface)', fontSize: '0.76rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {query.rendered_query}
    </pre>
  </div>
);

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
  onResumeFetchAll,
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

  const executedAt = new Date(result.executed_at);
  const executedAtLabel = Number.isNaN(executedAt.getTime())
    ? result.executed_at
    : executedAt.toLocaleString('pl-PL');

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Search size={18} style={{ color: 'var(--accent-primary)' }} />
          <span>Wyniki wyszukiwania</span>
        </div>
      }
      subtitle={`Wykonano: ${executedAtLabel} · Providerzy: ${result.providers.join(', ')}`}
    >
      {/* ── 1. Query / search definition ─────────────────────────────────── */}
      <QueryPreview result={result} />

      {/* ── 2. Provider retrieval status & retrieval actions ─────────────── */}
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

      {(onFetchAll || fetchAllJob) && (
        <FetchAllProgressPanel
          progress={fetchAllJob}
          starting={fetchAllStarting}
          onCancel={onCancelFetchAll}
          onResume={onResumeFetchAll}
        />
      )}

      {fetchAllError && (
        <div role="alert" style={{ color: 'var(--status-error-text)', marginBottom: 12 }}>
          {fetchAllError}
        </div>
      )}

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
            flexWrap: 'wrap',
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
            flexWrap: 'wrap',
          }}
        >
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Providerzy mogą udostępniać mniej wyników niż deklarowana łączna liczba
            trafień (<strong>{result.total_count}</strong>). Pełne pobieranie działa w tle.
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

      {/* ── 3. Result statistics ─────────────────────────────────────────── */}
      <div
        data-testid="result-stats"
        style={{
          display: 'flex',
          gap: 10,
          flexWrap: 'wrap',
          marginBottom: 12,
        }}
      >
        <StatCell value={result.total_count.toLocaleString('pl-PL')} label="Znaleziono w providerach" />
        <StatCell value={totalLoaded.toLocaleString('pl-PL')} label="Pobrane rekordy" />
        <StatCell value={selectedIds.length.toLocaleString('pl-PL')} label="Wybrane do importu" accent />
      </div>

      {paginationError && (
        <div role="alert" style={{ color: 'var(--status-error-text)', marginBottom: 12 }}>
          {paginationError}
        </div>
      )}

      {result.results.length === 0 && (
        <div style={{ color: 'var(--text-secondary)', marginBottom: 12 }}>
          Nie znaleziono rekordów dla tej strategii.
        </div>
      )}

      {/* ── 4. Selection & actions ───────────────────────────────────────── */}
      {result.results.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            marginBottom: 12,
            padding: '10px 12px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface-elevated)',
          }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 16 }}>
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

            {onImport && (
              <>
                <span style={{ flex: 1 }} />
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
              </>
            )}
          </div>
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            Zakres zaznaczenia: „widoczne” dotyczy bieżącej strony listy, „pobrane” — wszystkich
            wczytanych rekordów ({totalLoaded}); pełny zestaw zgłoszony przez providerów wymaga
            akcji „Pobierz wszystkie dostępne”.
          </div>
          {importResult !== null && (
            <div role="status" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Zaimportowano: {importResult.imported_count}. Pominięto istniejące:{' '}
              {importResult.skipped_count}. Working Collection:{' '}
              {importResult.working_collection_count}.
            </div>
          )}
        </div>
      )}

      {/* ── 5. Result list ───────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-testid="record-list">
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

      {/* ── 6. Local pagination (bound to the record list above) ────────── */}
      {totalLocalPages > 1 && (
        <div
          data-testid="local-pagination"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            flexWrap: 'wrap',
            marginTop: 12,
            padding: '8px 12px',
            backgroundColor: 'var(--bg-surface-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
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
    </Card>
  );
};

const StatCell: React.FC<{ value: string; label: string; accent?: boolean }> = ({
  value,
  label,
  accent = false,
}) => (
  <div
    style={{
      minWidth: 150,
      padding: '8px 14px',
      borderRadius: 'var(--radius-md)',
      border: accent ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
      backgroundColor: accent ? 'var(--accent-subtle)' : 'var(--bg-primary)',
    }}
  >
    <div style={{ fontSize: '1.05rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
      {value}
    </div>
    <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', fontWeight: 600 }}>
      {label}
    </div>
  </div>
);
