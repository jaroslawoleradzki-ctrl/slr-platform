import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { SourcesIngestionPage, applyImportDecisionToSummary } from '../src/pages/SourcesIngestionPage';
import { projectApiService } from '../src/services/api/projectApi';
import { SourcesSummaryResponse } from '../src/types';

const project: any = {
  id: 'lean_energy',
  title: 'Lean Energy Project',
  description: '',
  protocolVersion: '1.0',
  status: 'active',
  createdAt: '',
  updatedAt: '',
  nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
  conceptGroups: [],
  searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
  providers: [],
  imports: [{
    id: 'import-gs01',
    sourceType: 'file',
    filename: 'GS01.ris',
    format: 'RIS',
    provider: null,
    query: null,
    totalAvailable: null,
    recordsCount: 378,
    importedAt: '2026-10-26T17:39:34Z',
    status: 'warning',
    warnings: [],
    sourceDatabase: null,
    sourceLabel: null,
    reviewStatus: 'pending',
    effectiveStatus: 'warning',
    reviewerId: null,
    reviewedAt: null,
    canAccept: true,
    canReject: false,
  }],
  normalization: [],
  deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
  duplicateGroups: [],
  screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
  qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
  prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
};

const Probe = () => {
  const { workflowStatus } = useProject();
  return <div data-testid="probe">{workflowStatus?.sources.state}:{workflowStatus?.sources.count}</div>;
};

const summary = (accepted: boolean): SourcesSummaryResponse => ({
  project_id: 'lean_energy',
  working_collection: { total_records: 446 },
  source_summaries: [{
    source: 'ris',
    source_kind: 'file' as const,
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
    warnings: [],
    created_at: '2026-10-26T17:39:34Z',
    effective_status: accepted ? 'success' : 'warning',
    review_status: accepted ? 'accepted' : 'pending',
    can_accept: !accepted,
    can_reject: false,
  }],
});

const reviewDetail: any = {
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
  warnings: [],
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
  warning_categories: [],
  blockers: [],
  decision: null,
};

const acceptedDecision: any = {
  project_id: 'lean_energy',
  import_id: 'import-gs01',
  decision: { decision_id: 'd1', decision: 'accepted', reviewer_id: 'r', rationale: null, decided_at: '2026-10-27T11:00:00Z', deleted_publication_count: 0, retained_source_record_count: 380, prisma_treatment: 'not_applicable' },
  effective_status: 'success',
  review_status: 'accepted',
};

const rejectedDecision: any = {
  project_id: 'lean_energy',
  import_id: 'import-gs01',
  decision: { decision_id: 'd2', decision: 'rejected', reviewer_id: 'r', rationale: 'not relevant', decided_at: '2026-10-27T11:00:00Z', deleted_publication_count: 0, retained_source_record_count: 380, prisma_treatment: 'not_applicable' },
  effective_status: 'rejected',
  review_status: 'rejected',
};

describe('Workflow status refresh after import decision', () => {
  let decisionApplied = false;
  beforeEach(() => {
    decisionApplied = false;
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([project]);
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockImplementation(async () => project.imports.map((i: any) => ({ ...i, effective_status: decisionApplied ? 'success' : i.effectiveStatus, review_status: decisionApplied ? 'accepted' : i.reviewStatus, can_accept: !decisionApplied, can_reject: false, records_count: i.recordsCount, created_at: i.importedAt, source_type: i.sourceType, source_database: i.sourceDatabase, source_label: i.sourceLabel })));
    vi.spyOn(projectApiService, 'postImportReview').mockImplementation(async () => { decisionApplied = true; return acceptedDecision; });
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({ project_id: 'lean_energy', total_groups_count: 0, groups: [] } as any);
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockResolvedValue({ project_id: 'lean_energy', records_identified_providers: 0, records_identified_imports: 0, total_identified: 0, records_after_normalization: 0, records_before_dedup: 0, records_after_technical_merger: 0, duplicate_groups_pending_review: 0, records_screened_title_abstract: 0, records_screened_full_text: 0, studies_included_synthesis: 0, manual_source_breakdown: {} } as any);
    vi.spyOn(projectApiService, 'getResumableFetchAllSearches').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getSourcesSummary').mockResolvedValue(summary(false));
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(reviewDetail);
  });

  it('updates shared workflow status on accept', async () => {
    vi.spyOn(projectApiService, 'getSourcesSummary').mockImplementation(async () => summary(decisionApplied));

    render(
      <ProjectProvider>
        <Probe />
        <SourcesIngestionPage />
      </ProjectProvider>
    );

    await waitFor(() => expect(screen.getByTestId('probe')).toHaveTextContent(/warning:1/));
    fireEvent.click(await screen.findByText('Ostrzeżenie'));
    fireEvent.click(await screen.findByRole('button', { name: 'Akceptuję' }));

    await waitFor(() => expect(screen.getByTestId('probe')).toHaveTextContent(/completed:1/));
  });

  it('updates source-summary counters on accept', () => {
    const before = summary(false);
    const after = applyImportDecisionToSummary(before, acceptedDecision);
    expect(after.source_summaries[0].successful_imports_count).toBe(1);
    expect(after.source_summaries[0].warning_imports_count).toBe(0);
    expect(after.source_summaries[0].records_added_count).toBe(378);
    expect(after.working_collection.total_records).toBe(446);
  });

  it('updates source-summary counters and workflow status on reject', async () => {
    vi.spyOn(projectApiService, 'postImportReview').mockImplementation(async () => { decisionApplied = true; return rejectedDecision as any; });
    vi.spyOn(projectApiService, 'getSourcesSummary').mockImplementation(async () => summary(false));

    render(
      <ProjectProvider>
        <Probe />
        <SourcesIngestionPage />
      </ProjectProvider>
    );

    await waitFor(() => expect(screen.getByTestId('probe')).toHaveTextContent(/warning:1/));
    fireEvent.click(await screen.findByText('Ostrzeżenie'));
    fireEvent.click(await screen.findByRole('button', { name: 'Akceptuję' }));

    await waitFor(() => expect(screen.getByTestId('probe')).toHaveTextContent(/completed:1/));
    const after = applyImportDecisionToSummary(summary(false), rejectedDecision);
    expect(after.source_summaries[0].warning_imports_count).toBe(0);
  });
});
