import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider } from '../src/context/ProjectContext';
import { SourcesIngestionPage } from '../src/pages/SourcesIngestionPage';
import { projectApiService } from '../src/services/api/projectApi';
import {
  ImportReviewDecisionResponse,
  ImportReviewDetail,
  SLRProject,
  SourcesSummaryResponse,
} from '../src/types';

const project: SLRProject = {
  id: 'lean_energy',
  title: 'Lean Energy Project',
  description: '',
  protocolVersion: '1.0',
  status: 'active',
  createdAt: '',
  updatedAt: '',
  nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
  conceptGroups: [],
  searchFilters: {
    publicationYearFrom: null,
    publicationYearTo: null,
    languages: [],
    publicationTypes: [],
    fullTextOnly: false,
  },
  providers: [
    {
      id: 'openalex',
      name: 'OpenAlex Works API',
      type: 'live_api',
      connected: true,
      status: 'idle',
      resultsCount: 0,
      lastRunTimestamp: null,
    },
  ],
  imports: [],
  normalization: [],
  deduplication: {
    recordsBeforeDedup: 0,
    identifierLinkedGroupsCount: 0,
    recordsAfterResultMerger: 0,
    candidateGroupsPendingUserReview: 0,
    status: 'pending',
  },
  duplicateGroups: [],
  screening: {
    titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 },
    fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 },
    status: 'pending',
  },
  qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
  prismaMetrics: {
    recordsIdentifiedProviders: 0,
    recordsIdentifiedImports: 0,
    totalIdentified: 0,
    recordsAfterNormalization: 0,
    recordsBeforeDedup: 0,
    recordsAfterTechnicalMerger: 0,
    duplicateGroupsPendingReview: 0,
    recordsScreenedTitleAbstract: 0,
    recordsScreenedFullText: 0,
    studiesIncludedSynthesis: 0,
    manualSourceBreakdown: {},
  },
};

const summary = (accepted: boolean): SourcesSummaryResponse => ({
  project_id: 'lean_energy',
  working_collection: { total_records: 446 },
  source_summaries: [{
    source: 'ris',
    source_kind: 'file',
    successful_imports_count: accepted ? 1 : 0,
    warning_imports_count: accepted ? 0 : 1,
    failed_imports_count: 0,
    records_added_count: 378,
    last_import_at: '2026-10-26T17:39:34Z',
    last_import_status: accepted ? 'success' : 'warning',
  }],
  import_history: [{
    import_id: 'import-gs01',
    source_type: 'file',
    filename: 'GS01.ris',
    format: 'RIS',
    provider: null,
    query: null,
    records_count: 378,
    status: 'warning',
    warnings: ['Skipped 2 exact DOI duplicate record(s) already in the project.'],
    created_at: '2026-10-26T17:39:34Z',
    effective_status: accepted ? 'success' : 'warning',
    review_status: accepted ? 'accepted' : 'pending',
    can_accept: !accepted,
    can_reject: false,
  }],
});

const reviewDetail: ImportReviewDetail = {
  project_id: 'lean_energy',
  import_id: 'import-gs01',
  source_type: 'file',
  filename: 'GS01.ris',
  format: 'RIS',
  provider: null,
  query: null,
  records_count: 378,
  status: 'warning',
  effective_status: 'warning',
  review_status: 'pending',
  warnings: ['Skipped 2 exact DOI duplicate record(s) already in the project.'],
  created_at: '2026-10-26T17:39:34Z',
  source_record_count: 380,
  canonical_publication_count: 378,
  exact_doi_match_count: 2,
  repeated_source_count: 3,
  title_candidate_count: 4,
  similar_title_candidate_count: 1,
  skipped_canonical_count: 5,
  invalid_doi_count: 2,
  validation_error_count: 0,
  audit_available: true,
  can_accept: true,
  can_reject: false,
  warning_categories: [{ code: 'exact_doi', label: 'Dokładne duplikaty DOI', count: 2 }],
  blockers: [],
  decision: null,
};

const acceptedDecision: ImportReviewDecisionResponse = {
  project_id: 'lean_energy',
  import_id: 'import-gs01',
  decision: {
    decision_id: 'decision-1',
    decision: 'accepted',
    reviewer_id: 'reviewer-a',
    rationale: null,
    decided_at: '2026-10-27T11:00:00Z',
    deleted_publication_count: 0,
    retained_source_record_count: 380,
    prisma_treatment: 'not_applicable',
  },
  effective_status: 'success',
  review_status: 'accepted',
};

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const renderPage = () => render(
  <ProjectProvider>
    <SourcesIngestionPage />
  </ProjectProvider>,
);

const acceptWarningImport = async () => {
  fireEvent.click(await screen.findByText('Ostrzeżenie'));
  fireEvent.click(await screen.findByRole('button', { name: 'Akceptuję' }));
};

describe('Sources ingestion refresh after an import decision', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([project]);
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({
      project_id: 'lean_energy',
      total_groups_count: 0,
      groups: [],
    });
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockResolvedValue({
      project_id: 'lean_energy',
      records_identified_providers: 0,
      records_identified_imports: 0,
      total_identified: 0,
      records_after_normalization: 0,
      records_before_dedup: 0,
      records_after_technical_merger: 0,
      duplicate_groups_pending_review: 0,
      records_screened_title_abstract: 0,
      records_screened_full_text: 0,
      studies_included_synthesis: 0,
      manual_source_breakdown: {},
    } as never);
    vi.spyOn(projectApiService, 'getResumableFetchAllSearches').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(reviewDetail);
  });

  it('shows a refresh error and retry action even when an older summary exists', async () => {
    let decisionApplied = false;
    let refreshFailures = 1;
    vi.spyOn(projectApiService, 'getSourcesSummary').mockImplementation(() => {
      if (decisionApplied && refreshFailures > 0) {
        refreshFailures -= 1;
        return Promise.reject(new Error('Nie udało się odświeżyć podsumowania źródeł'));
      }
      return Promise.resolve(summary(decisionApplied));
    });
    vi.spyOn(projectApiService, 'postImportReview').mockImplementation(async () => {
      decisionApplied = true;
      return acceptedDecision;
    });

    renderPage();
    await acceptWarningImport();

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(
      'Nie udało się odświeżyć podsumowania źródeł',
    ));
    expect(screen.getByText('GS01.ris')).toBeInTheDocument();
    expect(screen.getByText('Zaimportowano')).toBeInTheDocument();
    expect(screen.getByText(/Working Collection.*446/)).toBeInTheDocument();
    expect(screen.getByText('378 rekordów')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Ponów' }));

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(screen.getByText('Zaimportowano')).toBeInTheDocument();
    expect(screen.getByText(/Working Collection.*446/)).toBeInTheDocument();
    expect(screen.getByText('378 rekordów')).toBeInTheDocument();
  });

  it('updates the row immediately and keeps visible counts stable after a slow refresh', async () => {
    let decisionApplied = false;
    const refresh = deferred<SourcesSummaryResponse>();
    vi.spyOn(projectApiService, 'getSourcesSummary').mockImplementation(() => (
      decisionApplied ? refresh.promise : Promise.resolve(summary(false))
    ));
    vi.spyOn(projectApiService, 'postImportReview').mockImplementation(async () => {
      decisionApplied = true;
      return acceptedDecision;
    });

    renderPage();
    await acceptWarningImport();

    await waitFor(() => expect(screen.getByText('Zaimportowano')).toBeInTheDocument());
    expect(screen.getByText(/Working Collection.*446/)).toBeInTheDocument();
    expect(screen.getByText('378 rekordów')).toBeInTheDocument();

    await act(async () => {
      refresh.resolve(summary(true));
      await Promise.resolve();
    });

    await waitFor(() => expect(screen.queryByText('Ostrzeżenie')).not.toBeInTheDocument());
    expect(screen.getByText('Zaimportowano')).toBeInTheDocument();
    expect(screen.getByText(/Working Collection.*446/)).toBeInTheDocument();
    expect(screen.getByText('378 rekordów')).toBeInTheDocument();
  });
});
