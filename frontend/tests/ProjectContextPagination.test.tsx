import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { projectApiService } from '../src/services/api/projectApi';
import { EditableSearchStrategy, SearchExecutionResult } from '../src/types';

const strategy: EditableSearchStrategy = {
  filters: {
    publicationYearFrom: 2020,
    publicationYearTo: 2026,
    languages: ['en', 'pl'],
    publicationTypes: ['article'],
    fullTextOnly: false,
  },
  providers: ['openalex'],
  conceptGroups: [{ id: 'g1', name: 'Lean', terms: ['lean manufacturing'] }],
};

const page = (results: SearchExecutionResult['results'], next_cursor: string | null, has_more: boolean): SearchExecutionResult => ({
  project_id: 'lean_energy',
  status: 'validated',
  rendered_query: '"lean manufacturing"',
  providers: ['openalex'],
  publication_year_from: 2020,
  publication_year_to: 2026,
  executed_at: '2026-07-30T10:00:00Z',
  total_count: 3,
  returned_count: results.length,
  next_cursor,
  has_more,
  results,
});

const Harness = () => {
  const project = useProject();
  return (
    <>
      <button type="button" onClick={() => void project.executeSearchStrategy(strategy)}>search</button>
      <button type="button" onClick={() => void project.loadMoreSearchResults()}>more</button>
      <div data-testid="loaded">{project.searchExecutionResult?.returned_count ?? 0}</div>
      <div data-testid="records">{project.searchExecutionResult?.results.map((record) => record.source_id).join(',')}</div>
      {project.searchPaginationError && <div role="alert">{project.searchPaginationError}</div>}
    </>
  );
};

describe('ProjectContext cursor pagination', () => {
  afterEach(() => vi.restoreAllMocks());

  it('forwards the cursor, appends pages, and removes duplicate source records', async () => {
    const execute = vi.spyOn(projectApiService, 'executeSearchStrategy')
      .mockResolvedValueOnce(page([
        { id: '1', title: 'One', authors: [], year: 2020, provider: 'openalex', source_id: 'W1', doi: null },
        { id: '2', title: 'Two', authors: [], year: 2021, provider: 'openalex', source_id: 'W2', doi: null },
      ], 'cursor-2', true))
      .mockResolvedValueOnce(page([
        { id: '2-new', title: 'Two duplicate', authors: [], year: 2021, provider: 'openalex', source_id: 'W2', doi: null },
        { id: '3', title: 'Three', authors: [], year: 2022, provider: 'openalex', source_id: 'W3', doi: null },
      ], null, false));
    render(<ProjectProvider><Harness /></ProjectProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await waitFor(() => expect(screen.getByTestId('records')).toHaveTextContent('W1,W2'));
    fireEvent.click(screen.getByRole('button', { name: 'more' }));
    await waitFor(() => expect(screen.getByTestId('records')).toHaveTextContent('W1,W2,W3'));

    expect(execute).toHaveBeenNthCalledWith(2, 'lean_energy', strategy, 'cursor-2');
    expect(screen.getByTestId('loaded')).toHaveTextContent('3');
  });

  it('keeps existing records and exposes an error when the next page fails', async () => {
    vi.spyOn(projectApiService, 'executeSearchStrategy')
      .mockResolvedValueOnce(page([
        { id: '1', title: 'One', authors: [], year: 2020, provider: 'openalex', source_id: 'W1', doi: null },
      ], 'cursor-2', true))
      .mockRejectedValueOnce(new Error('HTTP 503'));
    render(<ProjectProvider><Harness /></ProjectProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await waitFor(() => expect(screen.getByTestId('records')).toHaveTextContent('W1'));
    fireEvent.click(screen.getByRole('button', { name: 'more' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('HTTP 503'));
    expect(screen.getByTestId('records')).toHaveTextContent('W1');
  });

  it('resets the cursor and records when a new search starts', async () => {
    const execute = vi.spyOn(projectApiService, 'executeSearchStrategy')
      .mockResolvedValueOnce(page([
        { id: '1', title: 'One', authors: [], year: 2020, provider: 'openalex', source_id: 'W1', doi: null },
      ], 'cursor-2', true))
      .mockResolvedValueOnce(page([
        { id: '2', title: 'Two', authors: [], year: 2021, provider: 'openalex', source_id: 'W2', doi: null },
      ], null, false))
      .mockResolvedValueOnce(page([
        { id: '9', title: 'New', authors: [], year: 2022, provider: 'openalex', source_id: 'W9', doi: null },
      ], null, false));
    render(<ProjectProvider><Harness /></ProjectProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await waitFor(() => expect(screen.getByTestId('records')).toHaveTextContent('W1'));
    fireEvent.click(screen.getByRole('button', { name: 'more' }));
    await waitFor(() => expect(screen.getByTestId('records')).toHaveTextContent('W1,W2'));
    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await waitFor(() => expect(screen.getByTestId('records')).toHaveTextContent('W9'));

    expect(screen.getByTestId('records')).not.toHaveTextContent('W1');
    expect(execute).toHaveBeenNthCalledWith(3, 'lean_energy', strategy);
  });
});
