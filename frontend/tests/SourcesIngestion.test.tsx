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

  it('shows the accumulated provider record count and reflects neutral vs success status accurately', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      {
        import_id: 'i-100',
        project_id: 'lean_energy',
        source_type: 'provider',
        filename: null,
        format: 'BibTeX',
        provider: 'openalex',
        query: 'test query',
        records_count: 100,
        total_available: 100,
        status: 'success',
        created_at: '2026-07-30T12:00:00Z',
        warnings: [],
      },
      {
        import_id: 'i-previous-100',
        project_id: 'lean_energy',
        source_type: 'provider',
        filename: null,
        format: 'BibTeX',
        provider: 'openalex',
        query: 'previous query',
        records_count: 100,
        total_available: 100,
        status: 'success',
        created_at: '2026-07-29T12:00:00Z',
        warnings: [],
      },
    ]);

    renderPage();

    await waitFor(() => expect(screen.getByText('200')).toBeInTheDocument());
    // Tylko OpenAlex jest połączony z udanym importem
    expect(screen.getAllByText('● Połączenie OK').length).toBe(1);
    // Pozostali dostawcy bez historii są w stanie neutralnym "○ Brak danych"
    expect(screen.getAllByText('○ Brak danych').length).toBe(2);
  });

  it('reflects failed latest import without masking it with previous connected state', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      {
        import_id: 'i-old',
        project_id: 'lean_energy',
        source_type: 'provider',
        filename: null,
        format: 'BibTeX',
        provider: 'openalex',
        query: 'old query',
        records_count: 100,
        total_available: 100,
        status: 'success',
        created_at: '2026-07-20T12:00:00Z',
        warnings: [],
      },
      {
        import_id: 'i-new-failed',
        project_id: 'lean_energy',
        source_type: 'provider',
        filename: null,
        format: 'BibTeX',
        provider: 'openalex',
        query: 'failed query',
        records_count: 0,
        total_available: 0,
        status: 'failed',
        created_at: '2026-07-30T12:00:00Z',
        warnings: ['Provider API Timeout'],
      },
    ]);

    renderPage();

    await waitFor(() => expect(screen.getByText('Błąd Providera')).toBeInTheDocument());
    expect(screen.getByText('Provider API Timeout')).toBeInTheDocument();
  });

  it('ignores file imports for provider card record counts', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      {
        import_id: 'i-file-1',
        project_id: 'lean_energy',
        source_type: 'file',
        filename: 'data.ris',
        format: 'RIS',
        provider: 'openalex', // powiązanic file-based
        query: null,
        records_count: 500,
        total_available: null,
        status: 'success',
        created_at: '2026-07-30T12:00:00Z',
        warnings: [],
      },
    ]);

    renderPage();

    await waitFor(() => expect(screen.getByText('data.ris')).toBeInTheDocument());
    // Karta OpenAlex nie powinna przejąć licznika 500 z pliku
    expect(screen.queryByText('500')).not.toBeInTheDocument();
  });
});
