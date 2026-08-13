import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { Sidebar } from '../src/components/layout/Sidebar';
import { WorkflowStepper } from '../src/components/workflow/WorkflowStepper';
import { projectApiService } from '../src/services/api/projectApi';
import {
  ApiDuplicateGroupListResponse,
  BibliographicImportHistoryRecord,
  NormalizationResponse,
  SearchStrategy,
} from '../src/types';

import { screeningApi } from '../src/services/api/screeningApi';

describe('v0.2.2 — WorkflowNavigationStatus Unit & Integration Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      {
        id: 'lean_energy',
        title: 'Lean Management Project',
        description: 'Test project description',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '2026-08-01T00:00:00Z',
        updatedAt: '2026-08-01T00:00:00Z',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
        conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
      {
        id: 'ai_architecture',
        title: 'AI Architecture Project',
        description: 'Test project description',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '2026-08-01T00:00:00Z',
        updatedAt: '2026-08-01T00:00:00Z',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
        conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
    ]);
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue({
      project_id: 'lean_energy',
      reviewer_id: 'default_reviewer',
      ready: true,
      readiness_status: 'ready',
      working_collection_count: 0,
      canonical_records_count: 0,
      unresolved_duplicate_groups: 0,
      criteria: [],
      progress: { total: 0, unscreened: 0, included: 0, excluded: 0, uncertain: 0, completed: 0 },
    });
  });

  const renderNav = (path = '/projects/lean_energy/dedup') =>
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={[path]}>
          <WorkflowStepper />
          <Sidebar />
        </MemoryRouter>
      </ProjectProvider>
    );

  it('A. Deduplication: returns 35 groups with 34 APPROVE, 1 REJECT, 0 PENDING -> shows Oceniono & completed step', async () => {
    const mockGroups: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 35,
      groups: [
        ...Array.from({ length: 34 }, (_, i) => ({
          group_id: `g-${i}`,
          reason: 'DOI match',
          records_count: 2,
          status: 'APPROVE' as const,
          shared_identifiers: [],
          records: [],
        })),
        {
          group_id: 'g-34',
          reason: 'DOI match',
          records_count: 2,
          status: 'REJECT' as const,
          shared_identifiers: [],
          records: [],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockGroups);

    renderNav();

    await waitFor(() => expect(screen.getByText('Oceniono')).toBeInTheDocument());
    expect(screen.queryByText(/45 do oceny/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/35 do oceny/i)).not.toBeInTheDocument();
  });

  it('B. Pending: returns 35 groups with 7 PENDING -> Sidebar shows "7 do oceny", Stepper shows alertCount 7', async () => {
    const mockGroups: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 35,
      groups: [
        ...Array.from({ length: 28 }, (_, i) => ({
          group_id: `g-${i}`,
          reason: 'DOI match',
          records_count: 2,
          status: 'APPROVE' as const,
          shared_identifiers: [],
          records: [],
        })),
        ...Array.from({ length: 7 }, (_, i) => ({
          group_id: `g-p-${i}`,
          reason: 'DOI match',
          records_count: 2,
          status: 'PENDING' as const,
          shared_identifiers: [],
          records: [],
        })),
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockGroups);

    renderNav();

    await waitFor(() => expect(screen.getByText('7 do oceny')).toBeInTheDocument());
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('C. Decision update: changing last PENDING group to APPROVE transitions Sidebar & Stepper to completed', async () => {
    const mockGroups: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'g-last',
          reason: 'DOI match',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [],
          records: [],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockGroups);

    const DecisionTrigger = () => {
      const { updateGroupDecision } = useProject();
      return (
        <button
          type="button"
          onClick={() => updateGroupDecision('g-last', 'APPROVE', 'Auto test approval')}
        >
          Approve Group
        </button>
      );
    };

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <WorkflowStepper />
          <Sidebar />
          <DecisionTrigger />
        </MemoryRouter>
      </ProjectProvider>
    );

    await waitFor(() => expect(screen.getByText('1 do oceny')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Approve Group' }));

    await waitFor(() => expect(screen.getByText('Oceniono')).toBeInTheDocument());
    expect(screen.queryByText('1 do oceny')).not.toBeInTheDocument();
  });

  it('D. Normalization: verifies status badges for not_started, OK, warning, and error', async () => {
    // 1. Not run
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    const { unmount } = renderNav('/projects/lean_energy/normalize');
    await waitFor(() => expect(screen.getByText('Pending')).toBeInTheDocument());
    unmount();

    // 2. OK
    const okNorm: NormalizationResponse = {
      run_id: 'r1',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 100,
      clean_records: 100,
      warnings_count: 0,
      errors_count: 0,
      rules_applied: [],
      audit_trail: [],
      started_at: '',
      completed_at: '',
      executed_at: '',
    };
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(okNorm);
    const { unmount: unmount2 } = renderNav('/projects/lean_energy/normalize');
    await waitFor(() => expect(screen.getByText('OK')).toBeInTheDocument());
    unmount2();

    // 3. Warning
    const warnNorm: NormalizationResponse = {
      ...okNorm,
      status: 'warning',
      warnings_count: 5,
    };
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(warnNorm);
    const { unmount: unmount3 } = renderNav('/projects/lean_energy/normalize');
    await waitFor(() => expect(screen.getByText('5 ostrzeżeń')).toBeInTheDocument());
    unmount3();

    // 4. Error
    const errNorm: NormalizationResponse = {
      ...okNorm,
      status: 'error',
      errors_count: 2,
    };
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(errNorm);
    renderNav('/projects/lean_energy/normalize');
    await waitFor(() => expect(screen.getByText('2 błędów')).toBeInTheDocument());
  });

  it('E. Sources: verifies badges for empty imports, valid imports, and warning imports', async () => {
    // 1. Empty imports
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    const { unmount } = renderNav('/projects/lean_energy/sources');
    await waitFor(() => expect(screen.getByText('Brak danych')).toBeInTheDocument());
    unmount();

    // 2. Completed imports
    const validImports: BibliographicImportHistoryRecord[] = [
      {
        import_id: 'i1',
        project_id: 'lean_energy',
        source_type: 'file',
        filename: 'data.bib',
        format: 'BibTeX',
        provider: null,
        query: null,
        records_count: 50,
        total_available: null,
        status: 'success',
        created_at: '',
        warnings: [],
      },
    ];
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(validImports);
    const { unmount: unmount2 } = renderNav('/projects/lean_energy/sources');
    await waitFor(() => expect(screen.getByText('1 importów')).toBeInTheDocument());
    unmount2();

    // 3. Warning imports
    const warnImports: BibliographicImportHistoryRecord[] = [
      {
        ...validImports[0],
        status: 'warning',
        warnings: ['Missing fields'],
      },
    ];
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(warnImports);
    renderNav('/projects/lean_energy/sources');
    await waitFor(() => expect(screen.getByText('1 importów')).toBeInTheDocument());
  });

  it('F. Mock leakage: 45 do oceny and 425 pending values from MOCK_PROJECTS do not leak into navigation', async () => {
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({
      project_id: 'lean_energy',
      total_groups_count: 0,
      groups: [],
    });

    renderNav();

    await waitFor(() => expect(screen.getByText('Oceniono')).toBeInTheDocument());
    expect(screen.queryByText(/45/)).not.toBeInTheDocument();
    expect(screen.queryByText(/425/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Faza 7/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Faza 8/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Flow/)).not.toBeInTheDocument();
  });

  it('G. Project switching: late response for Project A does not overwrite status for Project B', async () => {
    let resolveProjectA: (val: ApiDuplicateGroupListResponse) => void = () => {};

    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockImplementation(async (projectId) => {
      if (projectId === 'lean_energy') {
        return new Promise((resolve) => {
          resolveProjectA = resolve;
        });
      }
      return {
        project_id: 'ai_architecture',
        total_groups_count: 5,
        groups: Array.from({ length: 5 }, (_, i) => ({
          group_id: `g-b-${i}`,
          reason: 'DOI match',
          records_count: 2,
          status: 'PENDING' as const,
          shared_identifiers: [],
          records: [],
        })),
      };
    });

    const ProjectSwitcher = () => {
      const { setActiveProjectId } = useProject();
      const navigate = useNavigate();
      return (
        <button
          type="button"
          onClick={() => {
            setActiveProjectId('ai_architecture');
            navigate('/projects/ai_architecture/dedup');
          }}
        >
          Switch to B
        </button>
      );
    };

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <Routes>
            <Route
              path="/projects/:projectId/*"
              element={
                <>
                  <WorkflowStepper />
                  <Sidebar />
                  <ProjectSwitcher />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

    // Switch quickly to project B before A completes
    fireEvent.click(screen.getByRole('button', { name: 'Switch to B' }));

    await waitFor(() => expect(screen.getByText('5 do oceny')).toBeInTheDocument(), { timeout: 3000 });

    // Resolve late response for A
    resolveProjectA({
      project_id: 'lean_energy',
      total_groups_count: 99,
      groups: Array.from({ length: 99 }, (_, i) => ({
        group_id: `g-a-${i}`,
        reason: 'DOI match',
        records_count: 2,
        status: 'PENDING' as const,
        shared_identifiers: [],
        records: [],
      })),
    });

    // Project B status remains unchanged and is not overwritten by 99 from A
    expect(screen.getByText('5 do oceny')).toBeInTheDocument();
    expect(screen.queryByText('99 do oceny')).not.toBeInTheDocument();
  });

  it('H. Failure isolation: when duplicate-groups endpoint fails, search, sources & normalization continue working', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue({
      strategy_id: 'st-1',
      project_id: 'lean_energy',
      name: 'Strategy 1',
      description: null,
      research_questions: [],
      concept_groups: [
        { group_id: 'cg1', name: 'Domain', terms: ['term'], operator: 'or' },
        { group_id: 'cg2', name: 'Topic', terms: ['term2'], operator: 'or' },
      ],
      group_operator: 'and',
      constraints: {
        publication_year_from: null,
        publication_year_to: null,
        languages: [],
        publication_types: [],
        additional_limits: {},
      },
      providers: [],
      queries: [],
      version: 1,
      created_at: '',
      updated_at: '',
    } as SearchStrategy);

    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      {
        import_id: 'i1',
        project_id: 'lean_energy',
        source_type: 'file',
        filename: 'file.bib',
        format: 'BibTeX',
        provider: null,
        query: null,
        records_count: 10,
        total_available: null,
        status: 'success',
        created_at: '',
        warnings: [],
      },
    ]);

    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue({
      run_id: 'r1',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 10,
      clean_records: 10,
      warnings_count: 0,
      errors_count: 0,
      rules_applied: [],
      audit_trail: [],
      started_at: '',
      completed_at: '',
      executed_at: '',
    });

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockRejectedValue(
      new Error('500 Internal Server Error'),
    );

    renderNav();

    // Deduplication shows Błąd
    await waitFor(() => expect(screen.getByText('Błąd')).toBeInTheDocument());

    // Search strategy, sources, and normalization still display clean completed badges
    expect(screen.getByText('2 grup')).toBeInTheDocument();
    expect(screen.getByText('1 importów')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
  });
});
