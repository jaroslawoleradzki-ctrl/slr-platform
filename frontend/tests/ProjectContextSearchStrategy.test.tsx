import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { SearchStrategyPage } from '../src/pages/SearchStrategyPage';
import { projectApiService } from '../src/services/api/projectApi';
import { EditableSearchStrategy } from '../src/types';

const Probe: React.FC = () => {
  const context = useProject();
  const initializeAndExecute = async () => {
    if (!context.activeProject) return;
    const strategy: EditableSearchStrategy = {
      filters: structuredClone(context.activeProject.searchFilters),
      providers: ['openalex'],
      conceptGroups: structuredClone(context.activeProject.conceptGroups),
    };
    context.setCurrentSearchStrategy(strategy);
    await context.executeSearchStrategy(strategy);
  };
  return (
    <>
      <output data-testid="active-project">{context.activeProject?.id}</output>
      <output data-testid="current-strategy">{context.currentSearchStrategy ? 'set' : 'null'}</output>
      <output data-testid="last-strategy">{context.lastExecutedSearchStrategy ? 'set' : 'null'}</output>
      <output data-testid="execution-result">{context.searchExecutionResult ? 'set' : 'null'}</output>
      <output data-testid="selected-results">{context.selectedSearchResultIds.join(',') || 'none'}</output>
      <button onClick={initializeAndExecute}>Execute A</button>
      <button onClick={() => context.setActiveProjectId('ai_architecture')}>Switch to B</button>
      <button onClick={() => context.setActiveProjectId('lean_energy')}>Set same project</button>
    </>
  );
};

describe('ProjectContext search strategy isolation', () => {
  beforeEach(() => {
    vi.spyOn(projectApiService, 'importSearchResults').mockResolvedValue({
      project_id: 'lean_energy',
      imported_count: 1,
      skipped_count: 0,
      total_requested: 1,
      working_collection_count: 6,
    });
    vi.spyOn(projectApiService, 'executeSearchStrategy').mockResolvedValue({
      project_id: 'lean_energy',
      status: 'validated',
      rendered_query: '("Kaizen")',
      providers: ['openalex'],
      publication_year_from: 2015,
      publication_year_to: 2026,
      executed_at: '2026-07-29T15:00:00Z',
      result_count: 1,
      results: [{
        id: 'result-1',
        title: 'Controlled result',
        authors: ['Author One'],
        year: 2021,
        provider: 'openalex',
        source_id: 'W1',
        doi: null,
      }],
    });
  });

  it('clears all search execution state only when the active project changes', async () => {
    render(<ProjectProvider><Probe /></ProjectProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Execute A' }));
    await waitFor(() => expect(screen.getByTestId('last-strategy')).toHaveTextContent('set'));
    expect(screen.getByTestId('execution-result')).toHaveTextContent('set');

    fireEvent.click(screen.getByRole('button', { name: 'Set same project' }));
    expect(screen.getByTestId('last-strategy')).toHaveTextContent('set');

    fireEvent.click(screen.getByRole('button', { name: 'Switch to B' }));
    await waitFor(() => expect(screen.getByTestId('active-project')).toHaveTextContent('ai_architecture'));
    expect(screen.getByTestId('current-strategy')).toHaveTextContent('null');
    expect(screen.getByTestId('last-strategy')).toHaveTextContent('null');
    expect(screen.getByTestId('execution-result')).toHaveTextContent('null');
    expect(screen.getByTestId('selected-results')).toHaveTextContent('none');
  });

  it('initializes project B without exposing or repeating project A state', async () => {
    render(
      <ProjectProvider>
        <Probe />
        <SearchStrategyPage />
      </ProjectProvider>
    );
    await screen.findByRole('button', { name: 'Wykonaj' });
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Powtórz' })).toBeEnabled());
    expect(screen.getByText(/Strategia została poprawnie zweryfikowana/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Wybierz rekord Controlled result'));
    expect(screen.getByTestId('selected-results')).toHaveTextContent('result-1');
    fireEvent.click(screen.getByRole('button', { name: 'Wykonaj' }));
    await waitFor(() => expect(screen.getByLabelText('Wybierz rekord Controlled result')).not.toBeChecked());

    fireEvent.click(screen.getByRole('button', { name: 'Switch to B' }));
    await waitFor(() => expect(screen.getByTestId('active-project')).toHaveTextContent('ai_architecture'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Powtórz' })).toBeDisabled());
    expect(screen.queryByText(/Strategia została poprawnie zweryfikowana/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Nazwa grupy 1')).toHaveValue('LLM & Generative AI');

    fireEvent.click(screen.getByRole('button', { name: 'Powtórz' }));
    expect(projectApiService.executeSearchStrategy).toHaveBeenCalledTimes(2);
    expect(projectApiService.executeSearchStrategy).not.toHaveBeenCalledWith(
      'ai_architecture',
      expect.objectContaining({ conceptGroups: expect.arrayContaining([
        expect.objectContaining({ name: 'Lean Management Terms' }),
      ]) })
    );
  });

  it('ignores a late project A response after switching to project B', async () => {
    let resolveRequest: ((value: Awaited<ReturnType<typeof projectApiService.executeSearchStrategy>>) => void) | undefined;
    vi.mocked(projectApiService.executeSearchStrategy).mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      })
    );
    render(
      <ProjectProvider>
        <Probe />
        <SearchStrategyPage />
      </ProjectProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Execute A' }));
    await waitFor(() => expect(projectApiService.executeSearchStrategy).toHaveBeenCalledWith(
      'lean_energy',
      expect.any(Object)
    ));
    fireEvent.click(screen.getByRole('button', { name: 'Switch to B' }));
    await waitFor(() => expect(screen.getByTestId('active-project')).toHaveTextContent('ai_architecture'));

    await act(async () => {
      resolveRequest?.({
        project_id: 'lean_energy',
        status: 'validated',
        rendered_query: '("Late result")',
        providers: ['openalex'],
        publication_year_from: 2015,
        publication_year_to: 2026,
        executed_at: '2026-07-29T15:00:00Z',
        result_count: 1,
        results: [{
          id: 'late-a-result',
          title: 'Late project A result',
          authors: ['Author A'],
          year: 2021,
          provider: 'openalex',
          source_id: 'W-late',
          doi: null,
        }],
      });
    });

    expect(screen.getByTestId('execution-result')).toHaveTextContent('null');
    expect(screen.getByTestId('last-strategy')).toHaveTextContent('null');
    expect(screen.queryByText('Late project A result')).not.toBeInTheDocument();
    expect(screen.getByText('Brak wykonanych wyszukiwań.')).toBeInTheDocument();
  });

  it('imports the selected record, refreshes the collection and clears selection', async () => {
    const getProjects = vi.spyOn(projectApiService, 'getProjects');
    render(
      <ProjectProvider>
        <Probe />
        <SearchStrategyPage />
      </ProjectProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Execute A' }));
    await screen.findByLabelText('Wybierz rekord Controlled result');
    fireEvent.click(screen.getByLabelText('Wybierz rekord Controlled result'));

    fireEvent.click(screen.getByRole('button', { name: 'Importuj zaznaczone' }));

    await waitFor(() => expect(projectApiService.importSearchResults).toHaveBeenCalledWith(
      'lean_energy',
      [expect.objectContaining({ id: 'result-1', source_id: 'W1' })]
    ));
    await waitFor(() => expect(screen.getByTestId('selected-results')).toHaveTextContent('none'));
    expect(await screen.findByText(
      'Zaimportowano: 1. Pominięto istniejące: 0. Working Collection: 6.'
    )).toBeInTheDocument();
    expect(getProjects).toHaveBeenCalled();
    expect(screen.getByText('Controlled result')).toBeInTheDocument();
  });

  it('ignores a late import response after switching projects', async () => {
    let resolveImport:
      | ((value: Awaited<ReturnType<typeof projectApiService.importSearchResults>>) => void)
      | undefined;
    vi.mocked(projectApiService.importSearchResults).mockReturnValue(
      new Promise((resolve) => {
        resolveImport = resolve;
      })
    );
    render(
      <ProjectProvider>
        <Probe />
        <SearchStrategyPage />
      </ProjectProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Execute A' }));
    await screen.findByLabelText('Wybierz rekord Controlled result');
    fireEvent.click(screen.getByLabelText('Wybierz rekord Controlled result'));
    fireEvent.click(screen.getByRole('button', { name: 'Importuj zaznaczone' }));
    await waitFor(() => expect(projectApiService.importSearchResults).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Switch to B' }));

    await act(async () => {
      resolveImport?.({
        project_id: 'lean_energy',
        imported_count: 0,
        skipped_count: 1,
        total_requested: 1,
        working_collection_count: 6,
      });
    });

    expect(screen.getByTestId('active-project')).toHaveTextContent('ai_architecture');
    expect(screen.queryByText(/Zaimportowano:/)).not.toBeInTheDocument();
    expect(screen.getByText('Brak wykonanych wyszukiwań.')).toBeInTheDocument();
  });
});
