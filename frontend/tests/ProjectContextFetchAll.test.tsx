import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { projectApiService } from '../src/services/api/projectApi';
import {
  EditableSearchStrategy,
  FetchAllStatusResult,
  SearchExecutionResult,
} from '../src/types';

const strategy: EditableSearchStrategy = {
  filters: {
    publicationYearFrom: 2020,
    publicationYearTo: 2026,
    languages: [],
    publicationTypes: [],
    fullTextOnly: false,
  },
  providers: ['openalex'],
  conceptGroups: [{ id: 'g1', name: 'Lean', terms: ['lean manufacturing'] }],
};

const page = (
  results: SearchExecutionResult['results'],
  next_cursor: string | null,
  has_more: boolean
): SearchExecutionResult => ({
  project_id: 'lean_energy',
  status: 'validated',
  rendered_query: '"lean manufacturing"',
  providers: ['openalex'],
  publication_year_from: 2020,
  publication_year_to: 2026,
  executed_at: '2026-08-25T10:00:00Z',
  total_count: 5,
  returned_count: results.length,
  next_cursor,
  has_more,
  results,
});

const record = (id: string, sourceId: string, provider = 'openalex'): SearchExecutionResult['results'][number] => ({
  id,
  title: `Record ${id}`,
  authors: [],
  year: 2024,
  provider: provider as SearchExecutionResult['results'][number]['provider'],
  source_id: sourceId,
  doi: null,
});

let jobState: { running: boolean; result: SearchExecutionResult | null };

const runningStatus = (): FetchAllStatusResult => ({
  job_id: 'job-1',
  project_id: 'lean_energy',
  status: 'running',
  started_at: '2026-08-25T10:00:00Z',
  finished_at: null,
  providers: [
    {
      provider: 'openalex',
      status: 'running',
      fetched_count: 1,
      kept_count: 1,
      pages_fetched: 1,
      total_reported: 3,
      limit_reached: false,
      message: null,
    },
  ],
  fetched_total: 1,
  kept_total: 1,
  message: null,
  result: null,
});

const completedStatus = (): FetchAllStatusResult => ({
  job_id: 'job-1',
  project_id: 'lean_energy',
  status: 'completed',
  started_at: '2026-08-25T10:00:00Z',
  finished_at: '2026-08-25T10:05:00Z',
  providers: [
    {
      provider: 'openalex',
      status: 'complete',
      fetched_count: 3,
      kept_count: 3,
      pages_fetched: 2,
      total_reported: 3,
      limit_reached: false,
      message: null,
    },
  ],
  fetched_total: 3,
  kept_total: 3,
  message: null,
  result: page(
    [record('r1', 'W1'), record('r2', 'W2'), record('r3', 'W3')],
    null,
    false
  ),
});

const Harness = () => {
  const project = useProject();
  return (
    <>
      <div data-testid="active-proj">{project.activeProject?.id || ''}</div>
      <button type="button" onClick={() => void project.executeSearchStrategy(strategy)}>
        search
      </button>
      <button type="button" onClick={() => void project.startFetchAllResults()}>
        fetch-all
      </button>
      <button type="button" onClick={() => void project.cancelFetchAllResults()}>
        cancel-fetch-all
      </button>
      <div data-testid="records">
        {project.searchExecutionResult?.results.map((r) => r.source_id).join(',') || ''}
      </div>
      <div data-testid="returned">{project.searchExecutionResult?.returned_count ?? 0}</div>
      <div data-testid="fetch-all-status">{project.fetchAllJob?.status || 'none'}</div>
      <div data-testid="starting">{project.fetchAllStarting ? 'yes' : 'no'}</div>
      {project.fetchAllError && <div role="alert">{project.fetchAllError}</div>}
    </>
  );
};

describe('ProjectContext fetch-all results', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.useFakeTimers();
    jobState = { running: false, result: null };
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
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
      },
    ]);
  });

  it('polls the job, merges deduplicated records and updates the counts', async () => {
    const startSpy = vi
      .spyOn(projectApiService, 'startFetchAllSearch')
      .mockResolvedValue({ job_id: 'job-1', project_id: 'lean_energy', status: 'running' });
    vi.spyOn(projectApiService, 'getFetchAllSearchStatus')
      .mockResolvedValueOnce(runningStatus())
      .mockResolvedValueOnce(completedStatus());
    vi.spyOn(projectApiService, 'executeSearchStrategy').mockResolvedValue(
      page([record('old-1', 'W1')], 'cursor-2', true)
    );

    render(<ProjectProvider><Harness /></ProjectProvider>);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(screen.getByTestId('active-proj')).toHaveTextContent('lean_energy');

    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(screen.getByTestId('records')).toHaveTextContent('W1');

    fireEvent.click(screen.getByRole('button', { name: 'fetch-all' }));
    expect(startSpy).toHaveBeenCalledWith('lean_energy', strategy);

    // First poll (after 500 ms): still running.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(screen.getByTestId('fetch-all-status')).toHaveTextContent('running');
    expect(screen.getByTestId('records')).toHaveTextContent('W1');

    // Second poll (after another 1500 ms): finished; W1 stays a single entry.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(screen.getByTestId('fetch-all-status')).toHaveTextContent('completed');
    expect(screen.getByTestId('records')).toHaveTextContent('W1,W2,W3');
    expect(screen.getByTestId('returned')).toHaveTextContent('3');
  });

  it('does not start a second fetch-all while one is already active', async () => {
    const startSpy = vi
      .spyOn(projectApiService, 'startFetchAllSearch')
      .mockResolvedValue({ job_id: 'job-1', project_id: 'lean_energy', status: 'running' });
    vi.spyOn(projectApiService, 'getFetchAllSearchStatus').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolve(jobState.running ? runningStatus() : completedStatus());
        })
    );
    vi.spyOn(projectApiService, 'executeSearchStrategy').mockResolvedValue(
      page([record('old-1', 'W1')], null, false)
    );

    render(<ProjectProvider><Harness /></ProjectProvider>);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    jobState.running = true;
    fireEvent.click(screen.getByRole('button', { name: 'fetch-all' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(screen.getByTestId('fetch-all-status')).toHaveTextContent('running');

    fireEvent.click(screen.getByRole('button', { name: 'fetch-all' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(startSpy).toHaveBeenCalledOnce();

    jobState.running = false;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(screen.getByTestId('fetch-all-status')).toHaveTextContent('completed');
  });

  it('requests cancellation of the active fetch-all job', async () => {
    vi.spyOn(projectApiService, 'startFetchAllSearch').mockResolvedValue({
      job_id: 'job-1',
      project_id: 'lean_energy',
      status: 'running',
    });
    vi.spyOn(projectApiService, 'getFetchAllSearchStatus').mockResolvedValue(runningStatus());
    const cancelSpy = vi
      .spyOn(projectApiService, 'cancelFetchAllSearch')
      .mockResolvedValue(runningStatus());
    vi.spyOn(projectApiService, 'executeSearchStrategy').mockResolvedValue(
      page([record('old-1', 'W1')], null, false)
    );

    render(<ProjectProvider><Harness /></ProjectProvider>);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    fireEvent.click(screen.getByRole('button', { name: 'search' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    fireEvent.click(screen.getByRole('button', { name: 'fetch-all' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(screen.getByTestId('fetch-all-status')).toHaveTextContent('running');

    fireEvent.click(screen.getByRole('button', { name: 'cancel-fetch-all' }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(cancelSpy).toHaveBeenCalledWith('lean_energy', 'job-1');
  });

  it('restores resumable job status from API discovery and executes resume with specific job_id', async () => {
    vi.spyOn(projectApiService, 'getResumableFetchAllSearches').mockResolvedValue([
      {
        job_id: 'job-resumable-429',
        project_id: 'lean_energy',
        provider: 'openalex',
        status: 'partial',
        fetched_count: 2400,
        canonical_accepted_count: 404,
        canonical_rejected_count: 1996,
        canonical_indeterminate_count: 0,
        pages_fetched: 24,
        created_at: '2026-08-25T10:00:00Z',
        updated_at: '2026-08-25T10:05:00Z',
        resumable: true,
        message: 'HTTP 429 Too Many Requests',
      },
    ]);

    const resumeSpy = vi
      .spyOn(projectApiService, 'resumeFetchAllSearch')
      .mockResolvedValue({ job_id: 'job-resumed-new', project_id: 'lean_energy', status: 'running' });

    vi.spyOn(projectApiService, 'getFetchAllSearchStatus')
      .mockResolvedValueOnce({
        job_id: 'job-resumed-new',
        project_id: 'lean_energy',
        status: 'running',
        started_at: '2026-08-25T10:00:00Z',
        finished_at: null,
        providers: [
          {
            provider: 'openalex',
            status: 'running',
            fetched_count: 2401,
            kept_count: 405,
            pages_fetched: 25,
            total_reported: 27021,
            limit_reached: false,
            message: null,
          },
        ],
        fetched_total: 2401,
        kept_total: 405,
        message: null,
        result: null,
      })
      .mockResolvedValueOnce({
        job_id: 'job-resumed-new',
        project_id: 'lean_energy',
        status: 'completed',
        started_at: '2026-08-25T10:00:00Z',
        finished_at: '2026-08-25T10:10:00Z',
        providers: [
          {
            provider: 'openalex',
            status: 'complete',
            fetched_count: 2500,
            kept_count: 500,
            pages_fetched: 26,
            total_reported: 27021,
            limit_reached: false,
            message: null,
          },
        ],
        fetched_total: 2500,
        kept_total: 500,
        message: null,
        result: page([record('r-new', 'W-new')], null, false),
      });

    const ResumeHarness = () => {
      const project = useProject();
      return (
        <>
          <div data-testid="resumable-job-id">{project.fetchAllJob?.job_id || ''}</div>
          <div data-testid="resumable-job-status">{project.fetchAllJob?.status || ''}</div>
          <button type="button" onClick={() => void project.resumeFetchAllResults('job-resumable-429')}>
            resume-button
          </button>
          <div data-testid="final-status">{project.fetchAllJob?.status || ''}</div>
        </>
      );
    };

    render(<ProjectProvider><ResumeHarness /></ProjectProvider>);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    // Verification: discovery restored the resumable job
    expect(screen.getByTestId('resumable-job-id')).toHaveTextContent('job-resumable-429');

    // Click resume
    fireEvent.click(screen.getByRole('button', { name: 'resume-button' }));
    expect(resumeSpy).toHaveBeenCalledWith('lean_energy', 'job-resumable-429');

    // Advance to running poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(screen.getByTestId('final-status')).toHaveTextContent('running');

    // Advance to completed poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(screen.getByTestId('final-status')).toHaveTextContent('completed');
  });

  it('preserves multiple historical resumable jobs and allows selecting and resuming older job A instead of only latest B', async () => {
    const jobA = {
      job_id: 'job-A-openalex',
      project_id: 'lean_energy',
      provider: 'openalex',
      providers: ['openalex'],
      status: 'partial' as const,
      fetched_count: 2400,
      canonical_accepted_count: 404,
      canonical_rejected_count: 1996,
      canonical_indeterminate_count: 0,
      pages_fetched: 24,
      created_at: '2026-08-25T10:00:00Z',
      updated_at: '2026-08-25T10:05:00Z',
      resumable: true,
      message: 'HTTP 429 Too Many Requests',
    };

    const jobB = {
      job_id: 'job-B-crossref',
      project_id: 'lean_energy',
      provider: 'crossref',
      providers: ['crossref'],
      status: 'partial' as const,
      fetched_count: 500,
      canonical_accepted_count: 120,
      canonical_rejected_count: 380,
      canonical_indeterminate_count: 0,
      pages_fetched: 10,
      created_at: '2026-08-25T11:00:00Z',
      updated_at: '2026-08-25T11:10:00Z',
      resumable: true,
      message: 'Connection timeout',
    };

    vi.spyOn(projectApiService, 'getResumableFetchAllSearches').mockResolvedValue([jobB, jobA]);

    const resumeSpy = vi
      .spyOn(projectApiService, 'resumeFetchAllSearch')
      .mockResolvedValue({ job_id: 'job-resumed-A', project_id: 'lean_energy', status: 'running' });

    vi.spyOn(projectApiService, 'getFetchAllSearchStatus').mockResolvedValue({
      job_id: 'job-resumed-A',
      project_id: 'lean_energy',
      status: 'completed',
      started_at: '2026-08-25T10:00:00Z',
      finished_at: '2026-08-25T10:15:00Z',
      providers: [
        {
          provider: 'openalex',
          status: 'complete',
          fetched_count: 2500,
          kept_count: 500,
          pages_fetched: 26,
          total_reported: 27021,
          limit_reached: false,
          message: null,
        },
      ],
      fetched_total: 2500,
      kept_total: 500,
      message: null,
      result: page([record('r-A', 'W-A')], null, false),
    });

    const MultiJobHarness = () => {
      const project = useProject();
      return (
        <>
          <div data-testid="resumable-jobs-count">{project.resumableJobs.length}</div>
          <div data-testid="active-job-id">{project.fetchAllJob?.job_id || ''}</div>
          <button
            type="button"
            data-testid="select-job-A-btn"
            onClick={() => project.selectResumableJob('job-A-openalex')}
          >
            select-A
          </button>
          <button
            type="button"
            data-testid="resume-job-A-btn"
            onClick={() => void project.resumeFetchAllResults('job-A-openalex')}
          >
            resume-A
          </button>
          <button
            type="button"
            data-testid="resume-job-B-btn"
            onClick={() => void project.resumeFetchAllResults('job-B-crossref')}
          >
            resume-B
          </button>
        </>
      );
    };

    render(<ProjectProvider><MultiJobHarness /></ProjectProvider>);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    // Both jobs exist in state
    expect(screen.getByTestId('resumable-jobs-count')).toHaveTextContent('2');

    // Initial default active job is latest (B)
    expect(screen.getByTestId('active-job-id')).toHaveTextContent('job-B-crossref');

    // Select job A
    fireEvent.click(screen.getByTestId('select-job-A-btn'));
    expect(screen.getByTestId('active-job-id')).toHaveTextContent('job-A-openalex');

    // Resume job A specifically
    fireEvent.click(screen.getByTestId('resume-job-A-btn'));
    expect(resumeSpy).toHaveBeenCalledWith('lean_energy', 'job-A-openalex');

    // Advance poll timer to complete job A
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    // Resume job B specifically
    fireEvent.click(screen.getByTestId('resume-job-B-btn'));
    expect(resumeSpy).toHaveBeenCalledWith('lean_energy', 'job-B-crossref');
  });
});
