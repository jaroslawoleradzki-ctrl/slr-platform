import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SearchResultsSection } from '../src/components/search/SearchResultsSection';
import { SearchExecutionResult } from '../src/types';

const result: SearchExecutionResult = {
  project_id: 'lean_energy',
  status: 'validated',
  rendered_query: '("Lean")',
  providers: ['openalex', 'crossref'],
  publication_year_from: 2020,
  publication_year_to: 2026,
  executed_at: '2026-07-29T12:00:00Z',
  result_count: 2,
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
        result={{ ...result, result_count: 0, results: [] }}
        loading={false}
        selectedIds={[]}
        onSelectionChange={() => undefined}
      />
    );
    expect(screen.getByText('Nie znaleziono rekordów dla tej strategii.')).toBeInTheDocument();
  });

  it('renders record fields and omits an empty DOI', () => {
    render(<SelectableResults />);
    expect(screen.getByText('Znaleziono 2 rekordów. Wybrano 0.')).toBeInTheDocument();
    expect(screen.getByText('Lean energy result')).toBeInTheDocument();
    expect(screen.getByText(/Anna Kowalska, Michael Smith · 2021 · Provider: openalex/)).toBeInTheDocument();
    expect(screen.getByText('DOI: 10.1000/lean')).toBeInTheDocument();
    expect(screen.getByText('Result without DOI')).toBeInTheDocument();
    expect(screen.queryByText('DOI:', { exact: true })).not.toBeInTheDocument();
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
});
