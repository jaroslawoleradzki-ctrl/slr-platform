import { useState } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SearchResultsSection } from '../src/components/search/SearchResultsSection';
import { FetchAllStatusResult, SearchExecutionResult } from '../src/types';

const result: SearchExecutionResult = {
  project_id: 'lean_energy',
  status: 'validated',
  rendered_query: '("Lean")',
  providers: ['openalex', 'crossref'],
  publication_year_from: 2020,
  publication_year_to: 2026,
  executed_at: '2026-07-29T12:00:00Z',
  total_count: 20,
  returned_count: 2,
  next_cursor: 'next-page',
  has_more: true,
  results: [
    {
      id: 'one',
      title: 'Lean energy result',
      authors: ['Anna Kowalska', 'Michael Smith'],
      year: 2021,
      provider: 'openalex',
      source_id: 'W1',
      doi: '10.1000/lean',
    },
    {
      id: 'two',
      title: 'Result without DOI',
      authors: ['Laura Chen'],
      year: 2023,
      provider: 'crossref',
      source_id: '10.1000/two',
      doi: null,
    },
  ],
};

const SelectableResults = () => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  return (
    <SearchResultsSection
      result={result}
      loading={false}
      selectedIds={selectedIds}
      onSelectionChange={setSelectedIds}
    />
  );
};

const fetchAllRunning: FetchAllStatusResult = {
  job_id: 'job-1',
  project_id: 'lean_energy',
  status: 'running',
  started_at: '2026-08-25T10:00:00Z',
  finished_at: null,
  providers: [
    {
      provider: 'openalex',
      status: 'complete',
      fetched_count: 1840,
      kept_count: 1840,
      pages_fetched: 19,
      total_reported: 1840,
      limit_reached: false,
      message: null,
    },
    {
      provider: 'semantic_scholar',
      status: 'running',
      fetched_count: 412,
      kept_count: 380,
      pages_fetched: 5,
      total_reported: 1000,
      limit_reached: false,
      message: null,
    },
  ],
  fetched_total: 2252,
  kept_total: 2220,
  message: null,
  result: null,
};

describe('SearchResultsSection', () => {
  it('renders initial, loading and empty states', () => {
    const { rerender } = render(
      <SearchResultsSection result={null} loading={false} selectedIds={[]} onSelectionChange={() => undefined} />
    );
    expect(screen.getByText('Brak wykonanych wyszukiwań.')).toBeInTheDocument();
    rerender(
      <SearchResultsSection result={null} loading selectedIds={[]} onSelectionChange={() => undefined} />
    );
    expect(screen.getByRole('status')).toHaveTextContent('Wyszukiwanie');
    rerender(
      <SearchResultsSection
        result={{ ...result, total_count: 0, returned_count: 0, results: [] }}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
      />
    );
    expect(screen.getByText('Nie znaleziono rekordów dla tej strategii.')).toBeInTheDocument();
  });

  it('renders record fields and omits an empty DOI', () => {
    render(<SelectableResults />);
    const stats = screen.getByTestId('result-stats');
    expect(within(stats).getByText('20')).toBeInTheDocument();          // found in providers
    expect(within(stats).getByText('Znaleziono w providerach')).toBeInTheDocument();
    expect(within(stats).getByText('2')).toBeInTheDocument();           // loaded records
    expect(within(stats).getByText('Pobrane rekordy')).toBeInTheDocument();
    expect(within(stats).getByText('0')).toBeInTheDocument();           // selected
    expect(within(stats).getByText('Wybrane do importu')).toBeInTheDocument();
    expect(screen.getByText('Lean energy result')).toBeInTheDocument();
    expect(screen.getByText(/Anna Kowalska, Michael Smith · 2021 · Provider: openalex/)).toBeInTheDocument();
    expect(screen.getByText('DOI: 10.1000/lean')).toBeInTheDocument();
    expect(screen.getByText('Result without DOI')).toBeInTheDocument();
    expect(screen.queryByText('DOI:', { exact: true })).not.toBeInTheDocument();
  });

  it('shows and triggers cursor pagination while preserving the loaded count', () => {
    const onLoadMore = vi.fn();
    render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        onLoadMore={onLoadMore}
      />,
    );

    const button = screen.getByRole('button', { name: 'Pobierz kolejne wyniki' });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onLoadMore).toHaveBeenCalledOnce();
  });

  it('shows and triggers the fetch-all button next to cursor pagination (v0.6.5)', () => {
    const onFetchAll = vi.fn();
    render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        onLoadMore={() => undefined}
        onFetchAll={onFetchAll}
      />,
    );

    const fetchAllButton = screen.getByRole('button', { name: 'Pobierz wszystkie dostępne' });
    expect(fetchAllButton).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pobierz kolejne wyniki' })).toBeInTheDocument();
    fireEvent.click(fetchAllButton);
    expect(onFetchAll).toHaveBeenCalledOnce();
  });

  it('disables both triggers while a fetch-all job is running and offers cancellation', () => {
    const onFetchAll = vi.fn();
    const onCancel = vi.fn();
    render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        loadingMore={false}
        onLoadMore={() => undefined}
        fetchAllJob={fetchAllRunning}
        onFetchAll={onFetchAll}
        onCancelFetchAll={onCancel}
      />,
    );

    expect(screen.getByTestId('fetch-all-progress')).toBeInTheDocument();
    expect(screen.queryByTestId('fetch-all-button')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Pobierz kolejne wyniki' })).not.toBeInTheDocument();
    const cancelButton = screen.getByRole('button', { name: 'Anuluj pobieranie' });
    fireEvent.click(cancelButton);
    expect(onCancel).toHaveBeenCalledOnce();
    expect(screen.getByText(/Łącznie pobrano:\s*2\s*252/u)).toBeInTheDocument();
    expect(screen.getByText(/Po lokalnych filtrach:\s*2\s*220/u)).toBeInTheDocument();

    // Provider rows: Provider | Status | Pobrano | Zgłoszono
    const openalexRow = screen.getByTestId('fetch-all-provider-row-openalex');
    expect(within(openalexRow).getByText('OpenAlex')).toBeInTheDocument();
    expect(within(openalexRow).getByText('Zakończono')).toBeInTheDocument();
    // fetched "1 840" plus reported "~1 840"
    expect(within(openalexRow).getAllByText(/1\s*840/u)).toHaveLength(2);
    expect(within(openalexRow).getAllByText(/~/u)).toHaveLength(1);

    const s2Row = screen.getByTestId('fetch-all-provider-row-semantic_scholar');
    expect(within(s2Row).getByText('Pobieranie…')).toBeInTheDocument();
    expect(within(s2Row).getByText(/^412$/u)).toBeInTheDocument();
    expect(within(s2Row).getByText(/~1\s*000/u)).toBeInTheDocument();
  });

  it('communicates partial provider failure after the fetch-all job finishes', () => {
    const finishedWithPartial: FetchAllStatusResult = {
      ...fetchAllRunning,
      status: 'completed',
      providers: [
        fetchAllRunning.providers[0],
        {
          provider: 'semantic_scholar',
          status: 'partial',
          fetched_count: 412,
          kept_count: 380,
          pages_fetched: 5,
          total_reported: 1000,
          limit_reached: true,
          message: 'Stopped by the fetch-all safety limit.',
        },
      ],
      message: 'Fetch-all finished with incomplete provider coverage; see per-provider statuses.',
    };
    render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        fetchAllJob={finishedWithPartial}
        onFetchAll={() => undefined}
      />,
    );

    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0);
    expect(screen.getByText(/Niekompletne dane: Semantic Scholar — częściowo/)).toBeInTheDocument();
    expect(screen.getByText(/osiągnięto limit możliwy do pobrania z API/)).toBeInTheDocument();
    expect(screen.getByText('Pobieranie wszystkich dostępnych wyników zakończone.')).toBeInTheDocument();
  });

  it('hides pagination when there are no more results and disables it while loading', () => {
    const onLoadMore = vi.fn();
    const { rerender } = render(
      <SearchResultsSection
        result={{ ...result, has_more: false, next_cursor: null }}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        onLoadMore={onLoadMore}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Pobierz kolejne wyniki' })).not.toBeInTheDocument();

    rerender(
      <SearchResultsSection
        result={result}
        loading={false}
        loadingMore
        selectedIds={[]}
        onSelectionChange={() => undefined}
        onLoadMore={onLoadMore}
      />,
    );
    expect(screen.getByRole('button', { name: 'Pobieranie…' })).toBeDisabled();
  });

  it('keeps existing records visible when loading the next page fails', () => {
    render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        paginationError="Nie udało się pobrać kolejnych wyników."
        onLoadMore={() => undefined}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać kolejnych wyników');
    expect(screen.getByText('Lean energy result')).toBeInTheDocument();
  });

  it('selects one record and toggles all visible records', () => {
    render(<SelectableResults />);
    const first = screen.getByLabelText('Wybierz rekord Lean energy result');
    const second = screen.getByLabelText('Wybierz rekord Result without DOI');
    const all = screen.getByLabelText('Zaznacz wszystkie widoczne rekordy');
    fireEvent.click(first);
    expect(first).toBeChecked();
    expect(second).not.toBeChecked();
    fireEvent.click(all);
    expect(first).toBeChecked();
    expect(second).toBeChecked();
    fireEvent.click(all);
    expect(first).not.toBeChecked();
    expect(second).not.toBeChecked();
  });

  it('renders a partial provider warning', () => {
    render(
      <SearchResultsSection
        result={{
          ...result,
          provider_errors: [{ provider: 'crossref', message: 'Timeout' }],
        }}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
      />
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Część providerów nie odpowiedziała: crossref'
    );
  });

  it('imports selected records and disables import without a selection', () => {
    const onImport = vi.fn();
    const { rerender } = render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        onImport={onImport}
      />
    );
    expect(screen.getByRole('button', { name: 'Importuj zaznaczone' })).toBeDisabled();
    rerender(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={['one']}
        onSelectionChange={() => undefined}
        onImport={onImport}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Importuj zaznaczone' }));
    expect(onImport).toHaveBeenCalledOnce();
  });

  it('shows imported, skipped and Working Collection counts for a mixed import', () => {
    render(
      <SearchResultsSection
        result={result}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
        onImport={() => undefined}
        importResult={{
          project_id: 'lean_energy',
          imported_count: 2,
          skipped_count: 1,
          total_requested: 3,
          working_collection_count: 8,
        }}
      />
    );

    expect(screen.getByRole('status')).toHaveTextContent(
      'Zaimportowano: 2. Pominięto istniejące: 1. Working Collection: 8.'
    );
    expect(screen.getByText('Lean energy result')).toBeInTheDocument();
  });

  it('supports local page navigation over fetched results and preserves selection state across local page switches', () => {
    const manyResults = Array.from({ length: 25 }, (_, i) => ({
      id: `rec-${i + 1}`,
      title: `Publication ${i + 1}`,
      authors: [`Author ${i + 1}`],
      year: 2024,
      provider: 'openalex' as const,
      source_id: `W${i + 1}`,
      doi: null,
    }));

    const paginatedResult: SearchExecutionResult = {
      ...result,
      total_count: 50,
      returned_count: 25,
      results: manyResults,
    };

    const Harness = () => {
      const [selectedIds, setSelectedIds] = useState<string[]>([]);
      return (
        <SearchResultsSection
          result={paginatedResult}
          loading={false}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
        />
      );
    };

    render(<Harness />);

    // Page 1 should show 20 records (Publication 1 to Publication 20)
    expect(screen.getByText('Strona 1 z 2 (rekordy 1–20 z 25)')).toBeInTheDocument();
    expect(screen.getByText('Publication 1')).toBeInTheDocument();
    expect(screen.queryByText('Publication 21')).not.toBeInTheDocument();

    // Select Publication 1 on page 1
    const cb1 = screen.getByLabelText('Wybierz rekord Publication 1');
    fireEvent.click(cb1);
    expect(cb1).toBeChecked();

    // Navigate to page 2
    const nextBtn = screen.getByRole('button', { name: 'Następna strona' });
    fireEvent.click(nextBtn);

    // Page 2 should show 5 records (Publication 21 to Publication 25)
    expect(screen.getByText('Strona 2 z 2 (rekordy 21–25 z 25)')).toBeInTheDocument();
    expect(screen.getByText('Publication 21')).toBeInTheDocument();
    expect(screen.queryByText('Publication 1')).not.toBeInTheDocument();

    // Select Publication 21 on page 2
    const cb21 = screen.getByLabelText('Wybierz rekord Publication 21');
    fireEvent.click(cb21);
    expect(cb21).toBeChecked();

    // Stats strip must show 2 selected records in total
    expect(within(screen.getByTestId('result-stats')).getByText('2')).toBeInTheDocument();

    // Navigate back to page 1
    const prevBtn = screen.getByRole('button', { name: 'Poprzednia strona' });
    fireEvent.click(prevBtn);

    // Page 1 should show Publication 1 still checked!
    expect(screen.getByText('Strona 1 z 2 (rekordy 1–20 z 25)')).toBeInTheDocument();
    expect(screen.getByLabelText('Wybierz rekord Publication 1')).toBeChecked();
  });
});
