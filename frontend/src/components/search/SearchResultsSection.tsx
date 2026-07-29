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
}

export const SearchResultsSection: React.FC<Props> = ({
  result,
  loading,
  selectedIds,
  onSelectionChange,
  importing = false,
  onImport,
  importResult = null,
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
  if (result.results.length === 0) {
    return (
      <Card title="Wyniki wyszukiwania">
        <div style={{ color: 'var(--text-secondary)' }}>Nie znaleziono rekordów dla tej strategii.</div>
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
      subtitle={`Znaleziono ${result.result_count} rekordów. Wybrano ${selectedIds.length}.`}
    >
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
