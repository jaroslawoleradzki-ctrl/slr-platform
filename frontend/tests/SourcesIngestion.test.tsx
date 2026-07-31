import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { SourcesIngestionPage } from '../src/pages/SourcesIngestionPage';
import { projectApiService } from '../src/services/api/projectApi';

describe('Sources ingestion upload', () => {
  afterEach(() => vi.restoreAllMocks());

  const renderPage = () => render(
    <ProjectProvider>
      <SourcesIngestionPage />
    </ProjectProvider>,
  );

  it('uploads a file, shows success and refreshes the project import history', async () => {
    vi.spyOn(projectApiService, 'importBibliographicFile').mockResolvedValue({
      import_id: 'import-new',
      records_count: 2,
      warnings: [],
      status: 'success',
    });
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([{
      import_id: 'import-new',
      project_id: 'lean_energy',
      source_type: 'file',
      filename: 'new.bib',
      format: 'BibTeX',
      provider: null,
      query: null,
      records_count: 2,
      total_available: null,
      status: 'success',
      created_at: '2026-07-30T12:00:00Z',
      warnings: [],
    }]);
    renderPage();

    const input = screen.getByLabelText('Wybierz plik RIS lub BibTeX');
    const file = new File(['@article{one, title={One}}'], 'new.bib', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Zaimportowano 2 rekordów.'));
    await waitFor(() => expect(screen.getByText('new.bib')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('2 rekordów')).toBeInTheDocument());
  });

  it('preserves existing history and shows the backend error on upload failure', async () => {
    vi.spyOn(projectApiService, 'importBibliographicFile').mockRejectedValue(
      new Error('Niepoprawny RIS (HTTP 422).'),
    );
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    renderPage();

    const input = screen.getByLabelText('Wybierz plik RIS lub BibTeX');
    const file = new File(['broken'], 'broken.ris', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Niepoprawny RIS'));
    expect(screen.queryByText('google_scholar_export_2026.ris')).not.toBeInTheDocument();
    expect(screen.queryByText('broken.ris')).not.toBeInTheDocument();
  });

  it('reloads the history for the newly selected project', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockImplementation(async (projectId) => [
      {
        import_id: projectId,
        project_id: projectId,
        source_type: 'file',
        filename: `${projectId}.ris`,
        format: 'RIS',
        provider: null,
        query: null,
        records_count: 1,
        total_available: null,
        status: 'success',
        created_at: '2026-07-30T12:00:00Z',
        warnings: [],
      },
    ]);
    const Switcher = () => {
      const { setActiveProjectId } = useProject();
      return <button type="button" onClick={() => setActiveProjectId('ai_architecture')}>switch</button>;
    };
    render(
      <ProjectProvider>
        <Switcher />
        <SourcesIngestionPage />
      </ProjectProvider>,
    );

    await waitFor(() => expect(screen.getByText('lean_energy.ris')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'switch' }));
    await waitFor(() => expect(screen.getByText('ai_architecture.ris')).toBeInTheDocument());
    expect(screen.queryByText('lean_energy.ris')).not.toBeInTheDocument();
  });
});
