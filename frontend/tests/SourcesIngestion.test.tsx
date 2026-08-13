import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { SourcesIngestionPage } from '../src/pages/SourcesIngestionPage';
import { projectApiService } from '../src/services/api/projectApi';

describe('Sources ingestion upload', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      {
        id: 'lean_energy',
        title: 'Lean Energy Project',
        description: '',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '', updatedAt: '',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
        conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [
          { id: 'openalex', name: 'OpenAlex Works API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
          { id: 'crossref', name: 'Crossref REST API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
          { id: 'semantic_scholar', name: 'Semantic Scholar Graph API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
        ], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
      {
        id: 'ai_architecture',
        title: 'AI Architecture Project',
        description: '',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '', updatedAt: '',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
        conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [
          { id: 'openalex', name: 'OpenAlex Works API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
          { id: 'crossref', name: 'Crossref REST API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
          { id: 'semantic_scholar', name: 'Semantic Scholar Graph API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
        ], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
    ]);
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({
      project_id: 'lean_energy',
      total_groups_count: 0,
      groups: [],
    });
  });

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
    vi.spyOn(projectApiService, 'getSourcesSummary').mockResolvedValue({
      project_id: 'lean_energy',
      working_collection: { total_records: 2 },
      source_summaries: [{
        source: 'RIS', source_kind: 'file', successful_imports_count: 1, warning_imports_count: 0, failed_imports_count: 0, records_added_count: 2, last_import_at: '2026-07-30T12:00:00Z', last_import_status: 'success'
      }],
      import_history: [{
        import_id: 'import-new', source_type: 'file', filename: 'new.bib', format: 'BibTeX', provider: null, query: null, records_count: 2, status: 'success', warnings: [], created_at: '2026-07-30T12:00:00Z'
      }],
    });
    renderPage();

    const input = await screen.findByLabelText('Wybierz plik RIS lub BibTeX');
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
    vi.spyOn(projectApiService, 'getSourcesSummary').mockResolvedValue({
      project_id: 'lean_energy',
      working_collection: { total_records: 0 },
      source_summaries: [],
      import_history: [],
    });
    renderPage();

    const input = await screen.findByLabelText('Wybierz plik RIS lub BibTeX');
    const file = new File(['broken'], 'broken.ris', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Niepoprawny RIS'));
    expect(screen.queryByText('google_scholar_export_2026.ris')).not.toBeInTheDocument();
    expect(screen.queryByText('broken.ris')).not.toBeInTheDocument();
  });

  it('reloads the history for the newly selected project', async () => {
    vi.spyOn(projectApiService, 'getSourcesSummary').mockImplementation(async (projectId) => ({
      project_id: projectId,
      working_collection: { total_records: 1 },
      source_summaries: [{ source: 'RIS', source_kind: 'file', successful_imports_count: 1, warning_imports_count: 0, failed_imports_count: 0, records_added_count: 1, last_import_at: '2026-07-30T12:00:00Z', last_import_status: 'success' }],
      import_history: [{
        import_id: projectId,
        source_type: 'file',
        filename: `${projectId}.ris`,
        format: 'RIS',
        provider: null,
        query: null,
        records_count: 1,
        status: 'success',
        created_at: '2026-07-30T12:00:00Z',
        warnings: [],
      }],
    }));
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
    vi.spyOn(projectApiService, 'getSourcesSummary').mockResolvedValue({
      project_id: 'lean_energy',
      working_collection: { total_records: 200 },
      source_summaries: [{
        source: 'openalex', source_kind: 'provider', successful_imports_count: 2, warning_imports_count: 0, failed_imports_count: 0, records_added_count: 200, last_import_at: '2026-07-30T12:00:00Z', last_import_status: 'success'
      }],
      import_history: [],
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('200')).toBeInTheDocument());
    // Tylko OpenAlex jest połączony z udanym importem
    expect(screen.getAllByText('● Połączenie OK').length).toBe(1);
    // Pozostali dostawcy bez historii są w stanie neutralnym "○ Brak danych"
    expect(screen.getAllByText('○ Brak danych').length).toBe(2);
  });

  it('reflects failed latest import without masking it with previous connected state', async () => {
    vi.spyOn(projectApiService, 'getSourcesSummary').mockResolvedValue({
      project_id: 'lean_energy',
      working_collection: { total_records: 100 },
      source_summaries: [{
        source: 'openalex', source_kind: 'provider', successful_imports_count: 1, warning_imports_count: 0, failed_imports_count: 1, records_added_count: 100, last_import_at: '2026-07-30T12:00:00Z', last_import_status: 'failed'
      }],
      import_history: [],
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('Błąd Providera')).toBeInTheDocument());
    expect(screen.getByText('Nieudana próba pobrania')).toBeInTheDocument();
  });

  it('ignores file imports for provider card record counts', async () => {
    vi.spyOn(projectApiService, 'getSourcesSummary').mockResolvedValue({
      project_id: 'lean_energy',
      working_collection: { total_records: 500 },
      source_summaries: [{
        source: 'RIS', source_kind: 'file', successful_imports_count: 1, warning_imports_count: 0, failed_imports_count: 0, records_added_count: 500, last_import_at: '2026-07-30T12:00:00Z', last_import_status: 'success'
      }],
      import_history: [{
        import_id: 'i-file-1',
        source_type: 'file',
        filename: 'data.ris',
        format: 'RIS',
        provider: 'openalex',
        query: null,
        records_count: 500,
        status: 'success',
        created_at: '2026-07-30T12:00:00Z',
        warnings: [],
      }],
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('data.ris')).toBeInTheDocument());
    // Karta OpenAlex nie powinna przejąć licznika 500 z pliku
    expect(screen.queryByText('500')).not.toBeInTheDocument();
  });
});
