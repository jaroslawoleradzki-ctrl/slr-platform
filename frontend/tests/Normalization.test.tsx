import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider } from '../src/context/ProjectContext';
import { NormalizationPage } from '../src/pages/NormalizationPage';
import { projectApiService } from '../src/services/api/projectApi';
import { NormalizationResponse } from '../src/types';

describe('Normalization page', () => {
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
        providers: [], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
    ]);
  });

  const renderPage = () => render(
    <ProjectProvider>
      <NormalizationPage />
    </ProjectProvider>,
  );

  it('does not show demo counts before normalization and loads real summary after run', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    let executed = false;
    const result: NormalizationResponse = {
      run_id: 'run-1',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 5,
      clean_records: 5,
      warnings_count: 0,
      errors_count: 0,
      rules_applied: ['DOI normalized'],
      audit_trail: ['DOI normalized: 2'],
      started_at: '2026-07-30T11:59:59Z',
      completed_at: '2026-07-30T12:00:00Z',
      executed_at: '2026-07-30T12:00:00Z',
    };
    vi.spyOn(projectApiService, 'getNormalization').mockImplementation(async () => executed ? result : null);
    const runSpy = vi.spyOn(projectApiService, 'runNormalization').mockImplementation(async () => {
      executed = true;
      return result;
    });
    renderPage();

    expect(screen.queryByText('2,105')).not.toBeInTheDocument();
    expect(await screen.findByText('Normalizacja nie została jeszcze uruchomiona dla tego projektu.')).toBeInTheDocument();
    expect(runSpy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Uruchom normalizację' }));
    await waitFor(() => expect(screen.getByText('DOI normalized: 2')).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText('5').length).toBeGreaterThan(0));
  });

  it('shows an empty neutral state when no execution exists', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    renderPage();
    await waitFor(() => expect(screen.getByText('Normalizacja nie została jeszcze uruchomiona dla tego projektu.')).toBeInTheDocument());
    expect(screen.queryByText('63')).not.toBeInTheDocument();
  });

  it('renders a persisted result returned by GET on entry', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue({
      run_id: 'persisted-run',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 7,
      clean_records: 6,
      warnings_count: 1,
      errors_count: 0,
      rules_applied: ['DOI normalized'],
      audit_trail: ['DOI normalized: 1'],
      started_at: '2026-07-30T11:59:59Z',
      completed_at: '2026-07-30T12:00:00Z',
      executed_at: '2026-07-30T12:00:00Z',
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('DOI normalized: 1')).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText('7').length).toBeGreaterThan(0));
  });

  it('renders re-run button, handles click, calls runNormalization(), sets disabled while running, and shows toast on success', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    const initialResult: NormalizationResponse = {
      run_id: 'persisted-run',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 7,
      clean_records: 6,
      warnings_count: 1,
      errors_count: 0,
      rules_applied: ['DOI normalized'],
      audit_trail: ['DOI normalized: 1'],
      started_at: '2026-07-30T11:59:59Z',
      completed_at: '2026-07-30T12:00:00Z',
      executed_at: '2026-07-30T12:00:00Z',
    };
    const updatedResult: NormalizationResponse = {
      ...initialResult,
      run_id: 're-run-2',
      processed_records: 10,
      clean_records: 10,
    };

    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(initialResult);

    let resolveRunPromise: (val: NormalizationResponse) => void = () => {};
    const runSpy = vi.spyOn(projectApiService, 'runNormalization').mockImplementation(
      () => new Promise((resolve) => {
        resolveRunPromise = resolve;
      }),
    );

    renderPage();

    const reRunButton = await screen.findByRole('button', { name: /Uruchom.*normalizację/i });
    expect(reRunButton).toBeInTheDocument();
    expect(reRunButton).not.toBeDisabled();

    fireEvent.click(reRunButton);

    expect(runSpy).toHaveBeenCalledTimes(1);
    expect(reRunButton).toBeDisabled();
    expect(reRunButton).toHaveTextContent('Normalizowanie...');

    resolveRunPromise(updatedResult);

    await waitFor(() => {
      expect(screen.getByText('Normalizacja została wykonana ponownie.')).toBeInTheDocument();
    });
  });
});
