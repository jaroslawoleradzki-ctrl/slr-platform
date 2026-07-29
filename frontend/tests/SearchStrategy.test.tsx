import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { SearchStrategyPage } from '../src/pages/SearchStrategyPage';
import { EditableSearchStrategy, SearchExecutionResult } from '../src/types';

const initialStrategy: EditableSearchStrategy = {
  filters: {
    publicationYearFrom: 2018,
    publicationYearTo: 2026,
    languages: ['en'],
    publicationTypes: ['article'],
    fullTextOnly: false,
  },
  providers: ['openalex', 'crossref'],
  conceptGroups: [{ id: 'g1', name: 'Lean', terms: ['Kaizen'] }],
};

let currentStrategy: EditableSearchStrategy | null;
let lastStrategy: EditableSearchStrategy | null;
let result: SearchExecutionResult | null;
let selectedIds: string[];
const execute = vi.fn();

vi.mock('../src/context/ProjectContext', () => ({
  useProject: () => ({
    activeProject: {
      id: 'lean_energy',
      searchFilters: initialStrategy.filters,
      conceptGroups: initialStrategy.conceptGroups,
      providers: [
        { id: 'openalex', name: 'OpenAlex', type: 'live_api', connected: true },
        { id: 'crossref', name: 'Crossref', type: 'live_api', connected: true },
        { id: 'unsupported', name: 'Unsupported', type: 'live_api', connected: false },
      ],
    },
    currentSearchStrategy: currentStrategy,
    lastExecutedSearchStrategy: lastStrategy,
    searchExecutionResult: result,
    selectedSearchResultIds: selectedIds,
    setCurrentSearchStrategy: (strategy: EditableSearchStrategy) => { currentStrategy = strategy; },
    setSelectedSearchResultIds: (ids: string[]) => { selectedIds = ids; },
    executeSearchStrategy: execute,
  }),
}));

describe('functional Search Strategy', () => {
  beforeEach(() => {
    currentStrategy = structuredClone(initialStrategy);
    lastStrategy = null;
    result = null;
    selectedIds = [];
    execute.mockReset();
    execute.mockResolvedValue({});
  });

  it('edits years, providers, groups and terms without resetting other fields', () => {
    const { rerender } = render(<SearchStrategyPage />);
    expect(screen.getByTestId('search-strategy-action-bar')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Wykonaj' })).toHaveAttribute('data-variant', 'primary');
    expect(screen.getByRole('button', { name: 'Powtórz' })).toHaveAttribute('data-variant', 'secondary');
    expect(screen.getAllByTestId('concept-term-tag')).toHaveLength(1);
    expect(screen.getByTestId('boolean-query-preview')).toHaveTextContent('"Kaizen"');

    fireEvent.change(screen.getByLabelText('Rok początkowy'), { target: { value: '2020' } });
    rerender(<SearchStrategyPage />);
    fireEvent.click(screen.getByLabelText('Crossref'));
    rerender(<SearchStrategyPage />);
    fireEvent.change(screen.getByLabelText('Nazwa grupy 1'), { target: { value: 'Updated group' } });
    rerender(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Edytuj termin 1 grupy 1' }));
    fireEvent.change(screen.getByLabelText('Edytuj termin 1 grupy 1'), { target: { value: 'updated term' } });
    fireEvent.keyDown(screen.getByLabelText('Edytuj termin 1 grupy 1'), { key: 'Enter' });
    rerender(<SearchStrategyPage />);

    expect(screen.getByLabelText('Rok początkowy')).toHaveValue(2020);
    expect(screen.getByLabelText('Crossref')).not.toBeChecked();
    expect(screen.getByLabelText('Nazwa grupy 1')).toHaveValue('Updated group');
    expect(screen.getByText('"updated term"')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Unsupported (niedostępny)' })).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Nazwa nowej grupy'), { target: { value: 'Added group' } });
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj Grupę' }));
    rerender(<SearchStrategyPage />);
    expect(screen.getByLabelText('Nazwa grupy 2')).toHaveValue('Added group');
    expect(screen.getByTestId('group-operator-separator')).toHaveTextContent('AND');
    fireEvent.change(screen.getByLabelText('Nowy termin grupy 2'), { target: { value: 'new term' } });
    fireEvent.keyDown(screen.getByLabelText('Nowy termin grupy 2'), { key: 'Enter' });
    rerender(<SearchStrategyPage />);
    expect(screen.getByText('"new term"')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Usuń termin 1 grupy 2' }));
    rerender(<SearchStrategyPage />);
    expect(screen.queryByText('"new term"')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Usuń grupę 2' }));
    rerender(<SearchStrategyPage />);
    expect(screen.queryByLabelText('Nazwa grupy 2')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Rok początkowy')).toHaveValue(2020);
    expect(screen.getByLabelText('Crossref')).not.toBeChecked();
  });

  it('cancels term editing with Escape and adds a term with the button', () => {
    const { rerender } = render(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Edytuj termin 1 grupy 1' }));
    const editInput = screen.getByLabelText('Edytuj termin 1 grupy 1');
    fireEvent.change(editInput, { target: { value: 'discarded value' } });
    fireEvent.keyDown(editInput, { key: 'Escape' });
    expect(screen.getByText('"Kaizen"')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Nowy termin grupy 1'), { target: { value: 'button term' } });
    fireEvent.click(screen.getByRole('button', { name: '+ Dodaj Termin' }));
    rerender(<SearchStrategyPage />);
    expect(screen.getByText('"button term"')).toBeInTheDocument();
  });

  it('validates input and blocks Execute', () => {
    currentStrategy = {
      ...structuredClone(initialStrategy),
      providers: [],
      filters: { ...initialStrategy.filters, publicationYearFrom: 2030, publicationYearTo: 2020 },
      conceptGroups: [{ id: 'g1', name: '', terms: [''] }],
    };
    render(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Zakres lat musi zawierać pełne lata');
    expect(screen.getByRole('alert')).toHaveTextContent('Wybierz co najmniej jednego providera');
    expect(screen.getByRole('alert')).toHaveTextContent('Nazwa grupy nie może być pusta');
    expect(execute).not.toHaveBeenCalled();
  });

  it.each([
    ['rok 999', 999, 2024],
    ['rok 10000', 2020, 10000],
    ['częściowy rok', 202, 2024],
  ])('blocks Execute for %s', (_caseName, from, to) => {
    currentStrategy = {
      ...structuredClone(initialStrategy),
      filters: {
        ...initialStrategy.filters,
        publicationYearFrom: from,
        publicationYearTo: to,
      },
    };
    render(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    expect(screen.getByRole('alert')).toHaveTextContent('od 1000 do 9999');
    expect(execute).not.toHaveBeenCalled();
  });

  it('accepts boundary years 1000 and 9999', async () => {
    currentStrategy = {
      ...structuredClone(initialStrategy),
      filters: {
        ...initialStrategy.filters,
        publicationYearFrom: 1000,
        publicationYearTo: 9999,
      },
    };
    render(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    await waitFor(() => expect(execute).toHaveBeenCalledWith(currentStrategy));
  });

  it('executes the current strategy and shows loading', async () => {
    let resolveExecution: () => void = () => undefined;
    execute.mockReturnValue(new Promise<void>((resolve) => { resolveExecution = resolve; }));
    render(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    expect(screen.getByRole('button', { name: 'Wykonywanie…' })).toBeDisabled();
    expect(execute).toHaveBeenCalledWith(initialStrategy);
    resolveExecution();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Wykonaj' })).toBeEnabled());
  });

  it('repeats the last successful strategy rather than current edits', async () => {
    lastStrategy = structuredClone(initialStrategy);
    currentStrategy = { ...structuredClone(initialStrategy), providers: ['crossref'] };
    render(<SearchStrategyPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Powtórz' }));
    await waitFor(() => expect(execute).toHaveBeenCalledWith(lastStrategy));
  });

  it('disables Repeat before success and displays API errors', async () => {
    execute.mockRejectedValue(new Error('API unavailable'));
    render(<SearchStrategyPage />);
    expect(screen.getByRole('button', { name: 'Powtórz' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable');
  });
});
