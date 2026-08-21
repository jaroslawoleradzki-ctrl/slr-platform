import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { ExportsPage } from '../src/pages/ExportsPage';
import { projectApiService } from '../src/services/api/projectApi';
import { screeningApi } from '../src/services/api/screeningApi';
import { extractionApi, ExtractionApiError } from '../src/api/extractionApi';
import { SLRProject, PrismaMetricsResponse } from '../src/types';

const PRISMA_METRICS: PrismaMetricsResponse = {
  project_id: 'proj_test',
  records_identified_providers: 12,
  records_identified_imports: 3,
  total_identified: 15,
  records_after_normalization: 15,
  records_before_dedup: 15,
  records_after_technical_merger: 14,
  duplicate_groups_pending_review: 2,
  records_screened_title_abstract: 10,
  records_screened_full_text: 5,
  studies_included_synthesis: 4,
  manual_source_breakdown: {},
};

const PROJECT: SLRProject = {
  id: 'proj_test',
  title: 'Test Project',
  description: 'Test project description',
  protocolVersion: '0.6',
  status: 'active',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-02T00:00:00Z',
  nextAction: { title: 'Next Action', description: 'Desc', targetStageId: 'search', actionLabel: 'Label', severity: 'normal' },
  conceptGroups: [],
  searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
  providers: [],
  imports: [],
  normalization: [],
  deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
  duplicateGroups: [],
  screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
  qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
  prismaMetrics: {
    recordsIdentifiedProviders: 12,
    recordsIdentifiedImports: 3,
    totalIdentified: 15,
    recordsAfterNormalization: 15,
    recordsBeforeDedup: 15,
    recordsAfterTechnicalMerger: 14,
    duplicateGroupsPendingReview: 2,
    recordsScreenedTitleAbstract: 10,
    recordsScreenedFullText: 5,
    studiesIncludedSynthesis: 4,
    manualSourceBreakdown: {},
  },
};

const renderExports = (path = '/projects/proj_test/exports') =>
  render(
    <ProjectProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/projects/:projectId/exports" element={<ExportsPage />} />
        </Routes>
      </MemoryRouter>
    </ProjectProvider>
  );

describe('ExportsPage — exports & PRISMA', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([PROJECT]);
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockResolvedValue(PRISMA_METRICS);
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue({
      project_id: 'proj_test',
      reviewer_id: 'default_reviewer',
      ready: true,
      readiness_status: 'ready',
      working_collection_count: 0,
      canonical_records_count: 0,
      unresolved_duplicate_groups: 0,
      criteria: [],
      progress: { total: 0, unscreened: 0, included: 0, excluded: 0, uncertain: 0, completed: 0 },
    });
    Object.assign(URL, {
      createObjectURL: vi.fn().mockReturnValue('blob:test'),
      revokeObjectURL: vi.fn(),
    });
  });

  it('renders page heading and Live PRISMA diagram with project metrics', async () => {
    renderExports();
    expect(
      await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)')
    ).toBeInTheDocument();
    expect(screen.getByText('Dynamic PRISMA 2020 Flow Diagram')).toBeInTheDocument();
    expect(screen.getByText('12 rekordów')).toBeInTheDocument();
    expect(screen.getByText('3 rekordów')).toBeInTheDocument();
    expect(screen.getByText('14 unikalnych rekordów')).toBeInTheDocument();
    expect(screen.getByText('2 grup')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('CSV and JSON buttons trigger exportDataset with publications dataset and download the blob', async () => {
    const exportDataset = vi
      .spyOn(extractionApi, 'exportDataset')
      .mockResolvedValue(new Blob(['data']));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const downloadButtons = screen.getAllByRole('button', { name: /Pobierz/i });
    fireEvent.click(downloadButtons[0]);
    await waitFor(() => expect(exportDataset).toHaveBeenCalledWith('proj_test', 'csv', 'publications'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test'));
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Zestawienie Rekordów CSV/);

    fireEvent.click(downloadButtons[1]);
    await waitFor(() => expect(exportDataset).toHaveBeenCalledWith('proj_test', 'json', 'publications'));
  });

  it('BibTeX, RIS and Excel formats are disabled and marked "Not yet available"', async () => {
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const unavailable = screen.getAllByRole('button', { name: /Not yet available/i });
    expect(unavailable.length).toBeGreaterThanOrEqual(3);
    unavailable.forEach((btn) => expect(btn).toBeDisabled());
    expect(screen.getByRole('button', { name: /Eksportuj PRISMA Flow/i })).toBeDisabled();
  });

  it('shows an error alert when export fails', async () => {
    vi.spyOn(extractionApi, 'exportDataset').mockRejectedValue(new Error('export unavailable'));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    fireEvent.click(screen.getAllByRole('button', { name: /Pobierz/i })[0]);
    expect(await screen.findByRole('alert')).toHaveTextContent(/Nie udało się pobrać eksportu/i);
  });

  it('shows the backend/API error message when export fails with an ExtractionApiError', async () => {
    vi.spyOn(extractionApi, 'exportDataset').mockRejectedValue(
      new ExtractionApiError(422, 'Query parameter format must be json or csv.')
    );
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    fireEvent.click(screen.getAllByRole('button', { name: /Pobierz/i })[0]);
    expect(await screen.findByRole('alert')).toHaveTextContent(/Query parameter format must be json or csv/i);
  });

  it('fetches PRISMA metrics from the backend for the active project', async () => {
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');
    await waitFor(() =>
      expect(projectApiService.getPrismaMetrics).toHaveBeenCalledWith('proj_test', 'default_reviewer')
    );
  });

  it('shows a loader while PRISMA metrics are being fetched', async () => {
    let resolveMetrics: (value: PrismaMetricsResponse) => void = () => {};
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockReturnValue(
      new Promise((resolve) => {
        resolveMetrics = resolve;
      })
    );
    renderExports();
    expect(
      await screen.findByText(/Ładowanie żywych metryk PRISMA z backendu/)
    ).toBeInTheDocument();
    resolveMetrics(PRISMA_METRICS);
    expect(
      await screen.findByText('Dynamic PRISMA 2020 Flow Diagram')
    ).toBeInTheDocument();
  });

  it('shows an error alert and no diagram when PRISMA metrics cannot be fetched', async () => {
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockRejectedValue(new Error('backend offline'));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');
    expect(await screen.findByRole('alert')).toHaveTextContent(/backend offline/i);
    expect(screen.queryByText('Dynamic PRISMA 2020 Flow Diagram')).not.toBeInTheDocument();
    expect(screen.getByText(/Diagram PRISMA jest niedostępny/)).toBeInTheDocument();
  });
});

