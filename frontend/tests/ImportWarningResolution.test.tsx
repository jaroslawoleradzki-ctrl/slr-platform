import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ImportReviewModal } from '../src/components/imports/ImportReviewModal';
import { ImportFileRecord, ImportReviewDetail } from '../src/types';
import { projectApiService } from '../src/services/api/projectApi';

const importRecord: ImportFileRecord = {
  id: 'import-1',
  sourceType: 'file',
  filename: 'review.ris',
  format: 'RIS',
  recordsCount: 2,
  importedAt: '2026-10-27T10:00:00Z',
  status: 'warning',
  warnings: ['Skipped 1 duplicate.', 'Title-only candidate requires review.'],
  sourceRecordCount: 3,
  canonicalPublicationCount: 2,
  exactDoiMatchCount: 1,
  titleCandidateCount: 1,
  auditAvailable: true,
};

const detail = (overrides: Partial<ImportReviewDetail> = {}): ImportReviewDetail => ({
  project_id: 'project-a',
  import_id: 'import-1',
  source_type: 'file',
  filename: 'review.ris',
  format: 'RIS',
  provider: null,
  query: null,
  records_count: 2,
  status: 'warning',
  effective_status: 'warning',
  review_status: 'pending',
  warnings: ['Skipped 1 duplicate.', 'Title-only candidate requires review.'],
  created_at: '2026-10-27T10:00:00Z',
  source_record_count: 3,
  canonical_publication_count: 2,
  exact_doi_match_count: 1,
  repeated_source_count: 0,
  title_candidate_count: 1,
  similar_title_candidate_count: 0,
  skipped_canonical_count: 1,
  invalid_doi_count: 0,
  validation_error_count: 0,
  audit_available: true,
  can_accept: true,
  can_reject: true,
  warning_categories: [
    { code: 'exact_doi', label: 'Dokładne duplikaty DOI', count: 1 },
  ],
  blockers: [],
  decision: null,
  ...overrides,
});

describe('Import warning resolution UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem('slr_screening_reviewer_id', 'reviewer-a');
  });

  it('shows warning detail and accepts through the server-confirmed path', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const post = vi.spyOn(projectApiService, 'postImportReview').mockResolvedValue({
      project_id: 'project-a',
      import_id: 'import-1',
      decision: {
        decision_id: 'decision-1',
        decision: 'accepted',
        reviewer_id: 'reviewer-a',
        rationale: null,
        decided_at: '2026-10-27T11:00:00Z',
        deleted_publication_count: 0,
        retained_source_record_count: 3,
        prisma_treatment: 'not_applicable',
      },
      effective_status: 'success',
      review_status: 'accepted',
    });
    const onChanged = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(<ImportReviewModal importRecord={importRecord} projectId="project-a" onChanged={onChanged} onClose={onClose} />);

    expect(await screen.findByText('Kategorie ostrzeżeń')).toBeInTheDocument();
    expect(screen.getAllByText(/Dokładne duplikaty DOI/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Akceptuję' }));

    await waitFor(() => expect(post).toHaveBeenCalledWith('project-a', 'import-1', {
      decision: 'accept',
      reviewer_id: 'reviewer-a',
    }));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('cancels rejection without issuing a request and confirms only after the dialog', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const post = vi.spyOn(projectApiService, 'postImportReview').mockResolvedValue({
      project_id: 'project-a',
      import_id: 'import-1',
      decision: {
        decision_id: 'decision-2',
        decision: 'rejected',
        reviewer_id: 'reviewer-a',
        rationale: null,
        decided_at: '2026-10-27T11:00:00Z',
        deleted_publication_count: 2,
        retained_source_record_count: 3,
        prisma_treatment: 'removed_before_screening_rejected_import',
      },
      effective_status: 'rejected',
      review_status: 'rejected',
    });
    const onChanged = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(<ImportReviewModal importRecord={importRecord} projectId="project-a" onChanged={onChanged} onClose={onClose} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Odrzucam' }));
    expect(screen.getByText(/Czy na pewno chcesz odrzucić ten import/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }));
    expect(post).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Odrzucam' }));
    fireEvent.click(screen.getByRole('button', { name: 'Potwierdź odrzucenie' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('project-a', 'import-1', {
      decision: 'reject',
      reviewer_id: 'reviewer-a',
      confirm_rejection: true,
    }));
  });

  it('shows blockers and disables the destructive action', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail({
      can_reject: false,
      blockers: [{
        code: 'screening_decision',
        message: 'Publication(s) have a screening decision.',
        count: 1,
        publication_ids: ['pub-1'],
      }],
    }));

    render(<ImportReviewModal importRecord={importRecord} projectId="project-a" onChanged={vi.fn()} onClose={vi.fn()} />);

    expect(await screen.findByText('Odrzucenie jest zablokowane')).toBeInTheDocument();
    expect(screen.getByText(/Publication\(s\) have a screening decision/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Odrzucam' })).toBeDisabled();
  });
});
