import React, { useEffect, useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { ConceptGroupQueryBuilder } from '../components/search/ConceptGroupQueryBuilder';
import { SearchLimitsForm } from '../components/search/SearchLimitsForm';
import { EditableSearchStrategy } from '../types';
import { CheckCircle2, Database, LoaderCircle, Play, RotateCcw } from 'lucide-react';
import { Card } from '../components/common/Card';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { SearchResultsSection } from '../components/search/SearchResultsSection';

const validate = (strategy: EditableSearchStrategy): string[] => {
  const errors: string[] = [];
  const { publicationYearFrom: from, publicationYearTo: to } = strategy.filters;
  if (
    from === null
    || to === null
    || from < 1000
    || from > 9999
    || to < 1000
    || to > 9999
    || from > to
  ) {
    errors.push('Zakres lat musi zawierać pełne lata od 1000 do 9999, a rok początkowy nie może być późniejszy od końcowego.');
  }
  if (strategy.providers.length === 0) errors.push('Wybierz co najmniej jednego providera.');
  if (strategy.conceptGroups.length === 0) errors.push('Dodaj co najmniej jedną grupę pojęć.');
  if (strategy.conceptGroups.some((group) => !group.name.trim())) errors.push('Nazwa grupy nie może być pusta.');
  if (strategy.conceptGroups.some((group) => group.terms.length === 0 || group.terms.some((term) => !term.trim()))) {
    errors.push('Każda grupa musi zawierać niepuste terminy.');
  }
  return errors;
};

export const SearchStrategyPage: React.FC = () => {
  const {
    activeProject,
    currentSearchStrategy,
    lastExecutedSearchStrategy,
    searchExecutionResult,
    selectedSearchResultIds,
    setCurrentSearchStrategy,
    setSelectedSearchResultIds,
    executeSearchStrategy,
    importSelectedSearchResults,
    lastSearchImportResult,
  } = useProject();
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (activeProject && !currentSearchStrategy) {
      setCurrentSearchStrategy({
        filters: structuredClone(activeProject.searchFilters),
        providers: activeProject.providers
          .filter((provider) =>
            provider.connected
            && provider.type === 'live_api'
            && ['openalex', 'crossref'].includes(provider.id)
          )
          .map((provider) => provider.id),
        conceptGroups: structuredClone(activeProject.conceptGroups),
      });
    }
  }, [activeProject, currentSearchStrategy, setCurrentSearchStrategy]);

  if (!activeProject || !currentSearchStrategy) return null;

  const run = async (strategy: EditableSearchStrategy) => {
    const validationErrors = validate(strategy);
    setErrors(validationErrors);
    setApiError(null);
    if (validationErrors.length) return;
    setSubmitting(true);
    try {
      await executeSearchStrategy(strategy);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Nieznany błąd API.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          1. Definicja Strategii Wyszukiwania (Search Strategy & Query)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          Zbuduj zapytanie Boolean z wykorzystaniem grup pojęć. Ustaw filtry i wybierz działających providerów.
        </p>
      </div>

      <div
        data-testid="search-strategy-action-bar"
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          padding: 12,
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-strong)',
          backgroundColor: 'var(--bg-surface)',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>Działania strategii</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Wykonaj bieżący formularz lub powtórz ostatnią poprawnie zweryfikowaną strategię.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button
            type="button"
            data-variant="secondary"
            disabled={submitting || !lastExecutedSearchStrategy}
            onClick={() => lastExecutedSearchStrategy && run(lastExecutedSearchStrategy)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '9px 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
              backgroundColor: 'var(--bg-surface-elevated)',
              color: 'var(--text-primary)',
              fontWeight: 600,
              opacity: submitting || !lastExecutedSearchStrategy ? 0.5 : 1,
            }}
          >
            <RotateCcw size={15} />
            Powtórz
          </button>
          <button
            type="button"
            data-variant="primary"
            disabled={submitting || !currentSearchStrategy}
            onClick={() => run(currentSearchStrategy)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '9px 18px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 700,
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? <LoaderCircle size={16} /> : <Play size={16} />}
            {submitting ? 'Wykonywanie…' : 'Wykonaj'}
          </button>
        </div>
      </div>

      {errors.length > 0 && (
        <ErrorAlert title="Popraw strategię przed wykonaniem" message={errors.join(' ')} />
      )}
      {apiError && <ErrorAlert title="Nie udało się zweryfikować strategii" message={apiError} />}
      {searchExecutionResult && (
        <div
          role="status"
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            padding: 14,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-success-border)',
            backgroundColor: 'var(--status-success-bg)',
            color: 'var(--status-success-text)',
          }}
        >
          <CheckCircle2 size={19} style={{ flexShrink: 0 }} />
          <div>
            <div style={{ fontWeight: 700 }}>
              Strategia została poprawnie zweryfikowana i przygotowana do wykonania.
            </div>
            <div style={{ marginTop: 3, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Autorytatywne zapytanie backendu: {searchExecutionResult.rendered_query}
            </div>
          </div>
        </div>
      )}

      <ConceptGroupQueryBuilder
        groups={currentSearchStrategy.conceptGroups}
        onGroupsChange={(conceptGroups) => setCurrentSearchStrategy({ ...currentSearchStrategy, conceptGroups })}
      />
      <SearchLimitsForm
        filters={currentSearchStrategy.filters}
        onFiltersChange={(filters) => setCurrentSearchStrategy({ ...currentSearchStrategy, filters })}
      />
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Providerzy wyszukiwania</span>
          </div>
        }
        subtitle="Do requestu zostaną dołączone wyłącznie zaznaczone i obsługiwane źródła."
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {activeProject.providers.filter((provider) => provider.type === 'live_api').map((provider) => {
            const supported = provider.connected && ['openalex', 'crossref'].includes(provider.id);
            return (
              <label
                key={provider.id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-strong)',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  color: supported ? 'var(--text-primary)' : 'var(--text-muted)',
                  cursor: supported ? 'pointer' : 'not-allowed',
                  opacity: supported ? 1 : 0.65,
                }}
              >
                <input
                  type="checkbox"
                  checked={currentSearchStrategy.providers.includes(provider.id)}
                  disabled={!supported}
                  onChange={(event) => setCurrentSearchStrategy({
                    ...currentSearchStrategy,
                    providers: event.target.checked
                      ? [...currentSearchStrategy.providers, provider.id]
                      : currentSearchStrategy.providers.filter((id) => id !== provider.id),
                  })}
                />
                <span>{provider.name}</span>
                {!supported && <span style={{ fontSize: '0.7rem' }}>(niedostępny)</span>}
              </label>
            );
          })}
        </div>
      </Card>
      <SearchResultsSection
        result={searchExecutionResult}
        loading={submitting}
        selectedIds={selectedSearchResultIds}
        onSelectionChange={setSelectedSearchResultIds}
        importing={importing}
        importResult={lastSearchImportResult}
        onImport={async () => {
          setImporting(true);
          setApiError(null);
          try {
            await importSelectedSearchResults();
          } catch (error) {
            setApiError(error instanceof Error ? error.message : 'Nie udało się zaimportować rekordów.');
          } finally {
            setImporting(false);
          }
        }}
      />
    </div>
  );
};
