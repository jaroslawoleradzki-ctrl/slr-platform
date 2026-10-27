import { describe, expect, it } from 'vitest';
import { computeWorkflowStatus } from '../src/context/ProjectContext';
import {
  ApiDuplicateGroupListResponse,
  BibliographicImportHistoryRecord,
  DuplicateReadiness,
  SearchStrategy,
} from '../src/types';

const strategy: SearchStrategy = {
  strategy_id: 'strategy-1',
  project_id: 'project-a',
  name: 'Strategy',
  description: null,
  research_questions: [],
  concept_groups: [{ group_id: 'cg1', name: 'Group', terms: ['term'], operator: 'or' as const }],
  group_operator: 'and' as const,
  constraints: {
    publication_year_from: null,
    publication_year_to: null,
    languages: [],
    publication_types: [],
    additional_limits: {},
  },
  providers: ['openalex'],
  queries: [],
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const readiness = (overrides: Partial<DuplicateReadiness> = {}): DuplicateReadiness => ({
  status: 'ready',
  screening_ready: true,
  total_groups: 0,
  pending_review_groups: 0,
  approved_unmerged_groups: 0,
  merged_groups: 0,
  rejected_groups: 0,
  stale_decisions: 0,
  blocking_groups: 0,
  blocking_group_ids: [],
  reason: 'No duplicate groups block screening.',
  ...overrides,
});

const duplicateResponse = (value: DuplicateReadiness): ApiDuplicateGroupListResponse => ({
  project_id: 'project-a',
  total_groups_count: value.total_groups,
  groups: [],
  readiness: value,
});

const acceptedWarningImport: BibliographicImportHistoryRecord = {
  import_id: 'import-1',
  project_id: 'project-a',
  source_type: 'file',
  filename: 'review.ris',
  format: 'RIS',
  provider: null,
  query: null,
  records_count: 2,
  total_available: null,
  status: 'warning',
  created_at: '2026-10-27T10:00:00Z',
  warnings: ['Skipped 1 duplicate.'],
  review_status: 'accepted',
  effective_status: 'success',
};

describe('deduplication and screening workflow consistency', () => {
  it('marks pending review consistently in deduplication and screening stage feedback', () => {
    const status = computeWorkflowStatus(
      strategy,
      [acceptedWarningImport],
      null,
      duplicateResponse(readiness({
        status: 'pending_review',
        screening_ready: false,
        total_groups: 1,
        pending_review_groups: 1,
        blocking_groups: 1,
        blocking_group_ids: ['group-1'],
      })),
      { project_id: 'project-a', reviewer_id: 'reviewer-a', ready: false, readiness_status: 'unresolved_duplicates', working_collection_count: 2, canonical_records_count: 0, unresolved_duplicate_groups: 1, criteria: [], progress: null },
      null,
      null,
      null,
    );

    expect(status.deduplication.state).toBe('pending_action');
    expect(status.deduplication.pendingGroups).toBe(1);
    expect(status.deduplication.readinessStatus).toBe('pending_review');
    expect(status.screening.state).not.toBe('completed');
    expect(status.sources.state).toBe('completed');
  });

  it('shows approved-unmerged groups as merge-required instead of completed', () => {
    const status = computeWorkflowStatus(
      strategy,
      [acceptedWarningImport],
      null,
      duplicateResponse(readiness({
        status: 'approved_unmerged',
        screening_ready: false,
        total_groups: 1,
        approved_unmerged_groups: 1,
        blocking_groups: 1,
        blocking_group_ids: ['group-1'],
      })),
      { project_id: 'project-a', reviewer_id: 'reviewer-a', ready: false, readiness_status: 'unmerged_duplicates', working_collection_count: 2, canonical_records_count: 0, unresolved_duplicate_groups: 1, criteria: [], progress: null },
      null,
      null,
      null,
    );

    expect(status.deduplication.state).toBe('pending_action');
    expect(status.deduplication.approvedUnmergedGroups).toBe(1);
    expect(status.deduplication.label).toContain('do scalenia');
    expect(status.deduplication.label).not.toContain('Oceniono');
  });

  it('marks deduplication completed only when the backend says no duplicate work blocks screening', () => {
    const status = computeWorkflowStatus(
      strategy,
      [acceptedWarningImport],
      null,
      duplicateResponse(readiness({
        status: 'ready',
        total_groups: 1,
        merged_groups: 1,
      })),
      { project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, readiness_status: 'ready', working_collection_count: 2, canonical_records_count: 1, unresolved_duplicate_groups: 0, criteria: [], progress: { total: 1, unscreened: 1, included: 0, excluded: 0, uncertain: 0, completed: 0 } },
      null,
      null,
      null,
    );

    expect(status.deduplication.state).toBe('completed');
    expect(status.deduplication.readinessStatus).toBe('ready');
  });
});
