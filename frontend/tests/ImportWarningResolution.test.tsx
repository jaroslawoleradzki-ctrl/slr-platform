import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ImportReviewModal } from '../src/components/imports/ImportReviewModal';
import { ImportFileRecord, ImportReviewDecisionResponse, ImportReviewDetail } from '../src/types';
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

const decisionResponse = (
  decision: 'accepted' | 'rejected',
): ImportReviewDecisionResponse => ({
  project_id: 'project-a',
  import_id: 'import-1',
  decision: {
    decision_id: `decision-${decision}`,
    decision,
    reviewer_id: 'reviewer-a',
    rationale: null,
    decided_at: '2026-10-27T11:00:00Z',
    deleted_publication_count: decision === 'rejected' ? 2 : 0,
    retained_source_record_count: 3,
    prisma_treatment: decision === 'rejected'
      ? 'removed_before_screening_rejected_import'
      : 'not_applicable',
  },
  effective_status: decision === 'accepted' ? 'success' : 'rejected',
  review_status: decision,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const spinner = (button: HTMLElement) => button.querySelector('.lucide-loader-circle');

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

  it('closes a successful accept without waiting for a slow refresh', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const post = vi.spyOn(projectApiService, 'postImportReview').mockResolvedValue(decisionResponse('accepted'));
    const onChanged = vi.fn(() => new Promise<void>(() => {}));
    const onDecisionApplied = vi.fn();
    const onClose = vi.fn();

    render(
      <ImportReviewModal
        importRecord={importRecord}
        projectId="project-a"
        onChanged={onChanged}
        onDecisionApplied={onDecisionApplied}
        onClose={onClose}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Akceptuję' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onDecisionApplied).toHaveBeenCalledWith(decisionResponse('accepted'));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('closes a successful rejection without waiting for a slow refresh', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const post = vi.spyOn(projectApiService, 'postImportReview').mockResolvedValue(decisionResponse('rejected'));
    const onChanged = vi.fn(() => new Promise<void>(() => {}));
    const onDecisionApplied = vi.fn();
    const onClose = vi.fn();

    render(
      <ImportReviewModal
        importRecord={importRecord}
        projectId="project-a"
        onChanged={onChanged}
        onDecisionApplied={onDecisionApplied}
        onClose={onClose}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Odrzucam' }));
    fireEvent.click(screen.getByRole('button', { name: 'Potwierdź odrzucenie' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onDecisionApplied).toHaveBeenCalledWith(decisionResponse('rejected'));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('shows a pending indicator only on the accept action', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const request = deferred<ImportReviewDecisionResponse>();
    vi.spyOn(projectApiService, 'postImportReview').mockReturnValue(request.promise);
    const onClose = vi.fn();

    render(<ImportReviewModal importRecord={importRecord} projectId="project-a" onChanged={vi.fn()} onClose={onClose} />);

    const acceptButton = await screen.findByRole('button', { name: 'Akceptuję' });
    fireEvent.click(acceptButton);

    await waitFor(() => expect(spinner(acceptButton)).not.toBeNull());
    const rejectButton = screen.getByRole('button', { name: 'Odrzucam' });
    expect(spinner(rejectButton)).toBeNull();
    expect(rejectButton).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Zamknij' })).toBeDisabled();

    await act(async () => {
      request.reject(new Error('Decyzja odrzucona przez serwer'));
      await Promise.resolve();
    });

    await waitFor(() => expect(screen.getByRole('button', { name: 'Zamknij' })).not.toBeDisabled());
    expect(screen.getByRole('alert')).toHaveTextContent('Decyzja odrzucona przez serwer');
    expect(onClose).not.toHaveBeenCalled();
  });

  it('shows a pending indicator only on the rejection confirmation', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const request = deferred<ImportReviewDecisionResponse>();
    vi.spyOn(projectApiService, 'postImportReview').mockReturnValue(request.promise);
    const onClose = vi.fn();

    render(<ImportReviewModal importRecord={importRecord} projectId="project-a" onChanged={vi.fn()} onClose={onClose} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Odrzucam' }));
    fireEvent.click(screen.getByRole('button', { name: 'Potwierdź odrzucenie' }));

    const confirmButton = screen.getByRole('button', { name: 'Potwierdź odrzucenie' });
    await waitFor(() => expect(spinner(confirmButton)).not.toBeNull());
    expect(spinner(screen.getByRole('button', { name: 'Akceptuję' }))).toBeNull();
    expect(screen.getByRole('button', { name: 'Akceptuję' })).toBeDisabled();

    await act(async () => {
      request.resolve(decisionResponse('rejected'));
      await Promise.resolve();
    });

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('keeps the dialog open with blockers when the decision request fails', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const blocker = {
      code: 'screening_decision',
      message: 'Publication(s) have a screening decision.',
      count: 1,
      publication_ids: ['pub-1'],
    };
    vi.spyOn(projectApiService, 'postImportReview').mockRejectedValue(
      Object.assign(new Error('Import rejection is blocked.'), { blockers: [blocker] }),
    );
    const onDecisionApplied = vi.fn();
    const onClose = vi.fn();

    render(
      <ImportReviewModal
        importRecord={importRecord}
        projectId="project-a"
        onChanged={vi.fn()}
        onDecisionApplied={onDecisionApplied}
        onClose={onClose}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Odrzucam' }));
    fireEvent.click(screen.getByRole('button', { name: 'Potwierdź odrzucenie' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Import rejection is blocked.'));
    expect(screen.getByText(/Publication\(s\) have a screening decision/)).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(onDecisionApplied).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Zamknij' })).not.toBeDisabled();
  });

  it('does not report a failed post-decision refresh as a failed decision', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    vi.spyOn(projectApiService, 'postImportReview').mockResolvedValue(decisionResponse('accepted'));
    const onChanged = vi.fn().mockRejectedValue(new Error('Nie udało się odświeżyć podsumowania źródeł'));
    const onDecisionApplied = vi.fn();
    const onClose = vi.fn();

    render(
      <ImportReviewModal
        importRecord={importRecord}
        projectId="project-a"
        onChanged={onChanged}
        onDecisionApplied={onDecisionApplied}
        onClose={onClose}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Akceptuję' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onDecisionApplied).toHaveBeenCalledWith(decisionResponse('accepted'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('submits only one decision request for repeated activation', async () => {
    vi.spyOn(projectApiService, 'getImportReview').mockResolvedValue(detail());
    const request = deferred<ImportReviewDecisionResponse>();
    const post = vi.spyOn(projectApiService, 'postImportReview').mockReturnValue(request.promise);

    render(<ImportReviewModal importRecord={importRecord} projectId="project-a" onChanged={vi.fn()} onClose={vi.fn()} />);

    const acceptButton = await screen.findByRole('button', { name: 'Akceptuję' });
    fireEvent.click(acceptButton);
    fireEvent.click(acceptButton);

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));

    await act(async () => {
      request.resolve(decisionResponse('accepted'));
      await Promise.resolve();
    });

    expect(post).toHaveBeenCalledTimes(1);
  });
});
