import React, { useEffect, useState } from 'react';
import { CheckCircle2, Database, LoaderCircle, Play, Save } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { ConceptGroupQueryBuilder } from '../components/search/ConceptGroupQueryBuilder';
import { SearchLimitsForm } from '../components/search/SearchLimitsForm';
import { SearchResultsSection } from '../components/search/SearchResultsSection';
import {
  EditableSearchStrategy,
  SearchExpression,
  SearchProviderId,
  SearchStrategy,
  SearchStrategyWriteRequest,
  SLRProject,
} from '../types';
import { Card } from '../components/common/Card';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Badge } from '../components/common/Badge';
import { projectApiService } from '../services/api/projectApi';

const emptyStrategy = (project?: SLRProject | null): SearchStrategyWriteRequest => ({
  name: project?.title || 'Strategia wyszukiwania',
  description: project?.description || null,
  research_questions: ['Pytanie badawcze'],
  concept_groups: [],
  group_operator: 'and',
  constraints: {
    publication_year_from: project?.searchFilters?.publicationYearFrom ?? null,
    publication_year_to: project?.searchFilters?.publicationYearTo ?? null,
    languages: project?.searchFilters?.languages ? [...project.searchFilters.languages] : [],
    publication_types: project?.searchFilters?.publicationTypes ? [...project.searchFilters.publicationTypes] : [],
    additional_limits: project?.searchFilters?.fullTextOnly ? { open_access: true } : {},
  },
  providers: project?.providers
    ? project.providers
        .filter((p) => p.connected && p.type === 'live_api' && ['openalex', 'crossref', 'semantic_scholar'].includes(p.id))
        .map((p) => p.id as SearchProviderId)
    : ['openalex'],
  queries: [],
  version: 1,
});

const editableFromResponse = (strategy: SearchStrategy): SearchStrategyWriteRequest => ({
  strategy_id: strategy.strategy_id,
  name: strategy.name || 'Strategia wyszukiwania',
  description: strategy.description,
  research_questions: strategy.research_questions.length > 0 ? [...strategy.research_questions] : ['Pytanie badawcze'],
  concept_groups: structuredClone(strategy.concept_groups),
  group_operator: strategy.group_operator,
  constraints: structuredClone(strategy.constraints),
  providers: [...strategy.providers],
  queries: structuredClone(strategy.queries),
  version: strategy.version,
  created_at: strategy.created_at,
});

const expressionFromStrategy = (
  strategy: SearchStrategyWriteRequest,
): SearchExpression | null => {
  const groupExpressions = strategy.concept_groups
    .filter((group) => group.terms.length > 0)
    .map<SearchExpression>((group) => {
      const terms: SearchExpression[] = group.terms.map((value) => ({
        node_type: 'term',
        value,
        exact_phrase: true,
      }));
      return terms.length === 1
        ? terms[0]
        : { node_type: 'group', operator: group.operator || 'or', children: terms };
    });
  if (groupExpressions.length === 0) return null;
  return groupExpressions.length === 1
    ? groupExpressions[0]
    : {
        node_type: 'group',
        operator: strategy.group_operator || 'and',
        children: groupExpressions,
      };
};

const validate = (strategy: SearchStrategyWriteRequest): string[] => {
  const errors: string[] = [];
  const { publication_year_from: from, publication_year_to: to } = strategy.constraints;
  if (strategy.concept_groups.length === 0) {
    errors.push('Dodaj co najmniej jedną grupę pojęć.');
  }
  if (strategy.concept_groups.some((group) => !group.name.trim() || group.terms.length === 0)) {
    errors.push('Każda grupa musi mieć nazwę i co najmniej jeden termin.');
  }
  if (strategy.providers.length === 0) {
    errors.push('Wybierz co najmniej jednego providera.');
  }
  if (
    (from !== null && (from < 1000 || from > 9999)) ||
    (to !== null && (to < 1000 || to > 9999))
  ) {
    errors.push('Lata muszą mieścić się w zakresie od 1000 do 9999.');
  }
  if (from !== null && to !== null && from > to) {
    errors.push('Rok początkowy nie może być późniejszy od końcowego.');
  }
  return errors;
};

export const SearchStrategyPage: React.FC = () => {
  const {
    activeProject,
    executeSearchStrategy,
    searchExecutionResult,
    loadMoreSearchResults,
    searchLoadingMore,
    searchPaginationError,
    selectedSearchResultIds,
    setSelectedSearchResultIds,
    importSelectedSearchResults,
    lastSearchImportResult,
  } = useProject();

  const [strategy, setStrategy] = useState<SearchStrategyWriteRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  useEffect(() => {
    if (!activeProject) return;
    let current = true;
    setLoading(true);
    setLoadError(null);
    setSaved(false);
    projectApiService
      .getSearchStrategy(activeProject.id)
      .then((response) => {
        if (!current) return;
        setStrategy(response ? editableFromResponse(response) : emptyStrategy(activeProject));
        setNotFound(response === null);
        setDirty(false);
      })
      .catch((error: unknown) => {
        if (!current) return;
        setStrategy(emptyStrategy(activeProject));
        setLoadError(error instanceof Error ? error.message : 'Nie udało się pobrać strategii.');
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [activeProject?.id]);

  const update = (next: SearchStrategyWriteRequest) => {
    setStrategy(next);
    setDirty(true);
    setSaved(false);
    setSaveError(null);
    setExecutionError(null);
  };

  const saveStrategy = async (): Promise<boolean> => {
    if (!activeProject || !strategy || saving) return false;
    const errors = validate(strategy);
    setValidationErrors(errors);
    setSaveError(null);
    if (errors.length > 0) return false;

    const expression = expressionFromStrategy(strategy);
    const payload: SearchStrategyWriteRequest = {
      ...strategy,
      name: strategy.name || 'Strategia wyszukiwania',
      description: strategy.description || null,
      research_questions: strategy.research_questions.length > 0 ? strategy.research_questions : ['Pytanie badawcze'],
      concept_groups: strategy.concept_groups.map((group) => ({
        ...group,
        name: group.name.trim(),
        terms: group.terms.map((term) => term.trim()),
      })),
      queries: [
        {
          name: `${strategy.name || 'Strategia wyszukiwania'} — general Boolean query`,
          expression: expression || { node_type: 'term', value: '' },
          version: strategy.version,
        },
      ],
    };

    setSaving(true);
    try {
      const response = await projectApiService.saveSearchStrategy(activeProject.id, payload);
      setStrategy(editableFromResponse(response));
      setDirty(false);
      setSaved(true);
      setNotFound(false);
      return true;
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Nie udało się zapisać strategii.');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleSearch = async () => {
    setExecutionError(null);
    const saveSuccess = await saveStrategy();
    if (!saveSuccess || !strategy) return;

    const editableStrategy: EditableSearchStrategy = {
      providers: strategy.providers,
      conceptGroups: strategy.concept_groups.map((g) => ({
        id: g.group_id,
        name: g.name,
        terms: g.terms,
      })),
      filters: {
        publicationYearFrom: strategy.constraints.publication_year_from,
        publicationYearTo: strategy.constraints.publication_year_to,
        languages: strategy.constraints.languages,
        publicationTypes: strategy.constraints.publication_types,
        fullTextOnly: Boolean(strategy.constraints.additional_limits?.open_access),
      },
    };

    setExecuting(true);
    try {
      await executeSearchStrategy(editableStrategy);
    } catch (error) {
      setExecutionError(error instanceof Error ? error.message : 'Błąd podczas wykonywania wyszukiwania.');
    } finally {
      setExecuting(false);
    }
  };

  if (!activeProject) return null;
  if (loading) return <LoadingSpinner label="Ładowanie strategii wyszukiwania…" />;
  if (!strategy) return null;

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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>Działania strategii</span>
            <span data-testid="save-state" role="status">
              <Badge
                variant={
                  saving
                    ? 'in_progress'
                    : dirty
                      ? 'pending_action'
                      : saved
                        ? 'completed'
                        : 'pending'
                }
              >
                {saving
                  ? 'Zapisywanie…'
                  : dirty
                    ? 'Niezapisane zmiany'
                    : saved
                      ? 'Zapisano poprawnie'
                      : 'Brak niezapisanych zmian'}
              </Badge>
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 3 }}>
            Zapisz formularz lub wykonaj wyszukiwanie w połączonych bazach.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button
            type="button"
            data-variant="secondary"
            disabled={saving || executing || Boolean(loadError)}
            onClick={() => void saveStrategy()}
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
              opacity: saving || executing || loadError ? 0.55 : 1,
            }}
          >
            {saving ? <LoaderCircle size={16} /> : <Save size={16} />}
            {saving ? 'Zapisywanie…' : 'Zapisz'}
          </button>
          <button
            type="button"
            data-variant="primary"
            disabled={saving || executing || Boolean(loadError)}
            onClick={() => void handleSearch()}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '9px 18px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 700,
              opacity: saving || executing || loadError ? 0.55 : 1,
            }}
          >
            {executing ? <LoaderCircle size={16} /> : <Play size={16} />}
            {executing ? 'Wyszukiwanie…' : 'Szukaj'}
          </button>
        </div>
      </div>

      {loadError && <ErrorAlert title="Nie udało się pobrać strategii" message={loadError} />}
      {notFound && !loadError && (
        <div
          role="status"
          style={{
            padding: 14,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-info-border)',
            backgroundColor: 'var(--status-info-bg)',
            color: 'var(--status-info-text)',
            fontSize: '0.85rem',
          }}
        >
          Ten projekt nie ma jeszcze zapisanej strategii. Rozpocznij od pustego formularza.
        </div>
      )}
      {validationErrors.length > 0 && (
        <ErrorAlert
          title="Popraw strategię przed wykonaniem"
          message={validationErrors.join(' ')}
        />
      )}
      {saveError && <ErrorAlert title="Nie udało się zapisać strategii" message={saveError} />}
      {executionError && <ErrorAlert title="Nie udało się wykonać wyszukiwania" message={executionError} />}
      {saved && !saveError && !executionError && (
        <div
          role="status"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: 14,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-success-border)',
            backgroundColor: 'var(--status-success-bg)',
            color: 'var(--status-success-text)',
            fontWeight: 600,
          }}
        >
          <CheckCircle2 size={18} /> Strategia została zapisana.
        </div>
      )}

      <ConceptGroupQueryBuilder
        groups={strategy.concept_groups}
        groupOperator={strategy.group_operator}
        onGroupsChange={(concept_groups) => update({ ...strategy, concept_groups })}
        onGroupOperatorChange={(group_operator) => update({ ...strategy, group_operator })}
        disabled={saving || executing}
      />

      <SearchLimitsForm
        constraints={strategy.constraints}
        onChange={(constraints) => update({ ...strategy, constraints })}
        disabled={saving || executing}
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
        <fieldset
          disabled={saving || executing}
          data-testid="provider-selector"
          style={{
            border: 0,
            padding: 0,
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 12,
          }}
        >
          {((activeProject.providers && activeProject.providers.length > 0)
            ? activeProject.providers.filter((provider) => provider.type === 'live_api').map((p) => ({
                id: p.id as SearchProviderId,
                name: p.name,
                supported: p.connected && ['openalex', 'crossref', 'semantic_scholar'].includes(p.id),
              }))
            : [
                { id: 'openalex' as SearchProviderId, name: 'OpenAlex', supported: true },
                { id: 'crossref' as SearchProviderId, name: 'Crossref', supported: true },
                { id: 'semantic_scholar' as SearchProviderId, name: 'Semantic Scholar', supported: true },
              ]
          ).map((provider) => (
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
                color: provider.supported ? 'var(--text-primary)' : 'var(--text-muted)',
                cursor: provider.supported ? 'pointer' : 'not-allowed',
                opacity: provider.supported ? 1 : 0.65,
              }}
            >
              <input
                type="checkbox"
                aria-label={provider.name}
                checked={strategy.providers.includes(provider.id)}
                disabled={!provider.supported || saving || executing}
                onChange={(event) =>
                  update({
                    ...strategy,
                    providers: event.target.checked
                      ? [...strategy.providers, provider.id]
                      : strategy.providers.filter((id) => id !== provider.id),
                  })
                }
              />
              <span>{provider.name}</span>
              {!provider.supported && <span style={{ fontSize: '0.7rem' }}>(niedostępny)</span>}
            </label>
          ))}
        </fieldset>
      </Card>

      <SearchResultsSection
        result={searchExecutionResult}
        loading={executing}
        selectedIds={selectedSearchResultIds}
        onSelectionChange={setSelectedSearchResultIds}
        importing={importing}
        importResult={lastSearchImportResult}
        loadingMore={searchLoadingMore}
        paginationError={searchPaginationError}
        onLoadMore={() => void loadMoreSearchResults()}
        onImport={async () => {
          setImporting(true);
          setExecutionError(null);
          try {
            await importSelectedSearchResults();
          } catch (error) {
            setExecutionError(error instanceof Error ? error.message : 'Nie udało się zaimportować rekordów.');
          } finally {
            setImporting(false);
          }
        }}
      />
    </div>
  );
};
