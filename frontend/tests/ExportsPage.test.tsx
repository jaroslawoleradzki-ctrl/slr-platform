import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { ExportsPage } from '../src/pages/ExportsPage';
import { projectApiService } from '../src/services/api/projectApi';
import { screeningApi } from '../src/services/api/screeningApi';
import { extractionApi } from '../src/services/api/extractionApi';
import { exportApi, ExportApiError } from '../src/services/api/exportApi';
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

describe('ExportsPage — Stage 9 exports & PRISMA completion', () => {
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
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });

  it('renders page heading, Live PRISMA diagram, and exactly zero locked buttons', async () => {
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

    // Verify 0 locked/disabled 'Not yet available' buttons exist in Stage 9
    const lockedButtons = screen.queryAllByText(/Not yet available/i);
    expect(lockedButtons.length).toBe(0);

    // Verify all 5 dataset cards have active download buttons + 2 PRISMA buttons (7 total download buttons)
    const downloadButtons = screen.getAllByRole('button', { name: /Pobierz/i });
    expect(downloadButtons.length).toBe(7);
  });

  it('triggers CSV and JSON downloads via extractionApi', async () => {
    const exportDataset = vi
      .spyOn(extractionApi, 'exportDataset')
      .mockResolvedValue(new Blob(['data']));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const downloadButtons = screen.getAllByRole('button', { name: /^Pobierz$/i });

    // CSV
    fireEvent.click(downloadButtons[0]);
    await waitFor(() => expect(exportDataset).toHaveBeenCalledWith('proj_test', 'csv', 'publications'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Zestawienie Rekordów CSV/);

    // JSON
    fireEvent.click(downloadButtons[1]);
    await waitFor(() => expect(exportDataset).toHaveBeenCalledWith('proj_test', 'json', 'publications'));
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Zestawienie rekordów JSON/);
  });

  it('triggers BibTeX download via exportApi with correct filename', async () => {
    const bibtexSpy = vi
      .spyOn(exportApi, 'exportBibtex')
      .mockResolvedValue(new Blob(['@article{...}'], { type: 'application/x-bibtex' }));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const downloadButtons = screen.getAllByRole('button', { name: /^Pobierz$/i });
    // BibTeX is 3rd card (index 2)
    fireEvent.click(downloadButtons[2]);
    await waitFor(() => expect(bibtexSpy).toHaveBeenCalledWith('proj_test'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Eksport Bazy BibTeX \(\.bib\)/);
  });

  it('triggers RIS download via exportApi with correct filename', async () => {
    const risSpy = vi
      .spyOn(exportApi, 'exportRis')
      .mockResolvedValue(new Blob(['TY  - JOUR...'], { type: 'application/x-research-info-systems' }));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const downloadButtons = screen.getAllByRole('button', { name: /^Pobierz$/i });
    // RIS is 4th card (index 3)
    fireEvent.click(downloadButtons[3]);
    await waitFor(() => expect(risSpy).toHaveBeenCalledWith('proj_test'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Eksport Bazy RIS \(\.ris\)/);
  });

  it('triggers XLSX download via exportApi with binary blob', async () => {
    const xlsxSpy = vi
      .spyOn(exportApi, 'exportXlsx')
      .mockResolvedValue(new Blob(['PK...'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const downloadButtons = screen.getAllByRole('button', { name: /^Pobierz$/i });
    // Excel is 5th card (index 4)
    fireEvent.click(downloadButtons[4]);
    await waitFor(() => expect(xlsxSpy).toHaveBeenCalledWith('proj_test'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Arkusz Excel Matrix \(\.xlsx\)/);
  });

  it('triggers PRISMA SVG download via exportApi', async () => {
    const svgSpy = vi
      .spyOn(exportApi, 'exportPrismaSvg')
      .mockResolvedValue(new Blob(['<svg></svg>'], { type: 'image/svg+xml' }));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const svgButton = screen.getByRole('button', { name: /Pobierz SVG/i });
    fireEvent.click(svgButton);
    await waitFor(() => expect(svgSpy).toHaveBeenCalledWith('proj_test'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik PRISMA Flow \(SVG\)/);
  });

  it('triggers PRISMA PDF download via exportApi with binary blob', async () => {
    const pdfSpy = vi
      .spyOn(exportApi, 'exportPrismaPdf')
      .mockResolvedValue(new Blob(['%PDF-1.4...'], { type: 'application/pdf' }));
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const pdfButton = screen.getByRole('button', { name: /Pobierz PDF/i });
    fireEvent.click(pdfButton);
    await waitFor(() => expect(pdfSpy).toHaveBeenCalledWith('proj_test'));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik PRISMA Flow \(PDF\)/);
  });

  it('shows error alert and allows retry when export fails', async () => {
    vi.spyOn(exportApi, 'exportBibtex').mockRejectedValue(
      new ExportApiError(500, 'Database query failed')
    );
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const downloadButtons = screen.getAllByRole('button', { name: /^Pobierz$/i });
    fireEvent.click(downloadButtons[2]);

    expect(await screen.findByRole('alert')).toHaveTextContent(/Database query failed/i);

    // Verify retry works after failure reset
    vi.spyOn(exportApi, 'exportBibtex').mockResolvedValue(new Blob(['@article{...}']));
    fireEvent.click(downloadButtons[2]);
    expect(await screen.findByRole('status')).toHaveTextContent(/Pobrano plik Eksport Bazy BibTeX/);
  });

  it('shows error alert when PRISMA export fails', async () => {
    vi.spyOn(exportApi, 'exportPrismaPdf').mockRejectedValue(
      new ExportApiError(404, 'Project not found')
    );
    renderExports();
    await screen.findByText('8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)');

    const pdfButton = screen.getByRole('button', { name: /Pobierz PDF/i });
    fireEvent.click(pdfButton);

    expect(await screen.findByRole('alert')).toHaveTextContent(/Project not found/i);
  });
});
