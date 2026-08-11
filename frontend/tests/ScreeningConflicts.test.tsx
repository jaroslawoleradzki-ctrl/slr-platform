import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ScreeningConflictsPage } from '../src/pages/ScreeningConflictsPage';
import { screeningApi } from '../src/services/api/screeningApi';

describe('Screening conflicts page', () => {
  beforeEach(() => {
    localStorage.setItem('slr_screening_reviewer_id', 'alice');
    vi.restoreAllMocks();
    vi.spyOn(screeningApi, 'getReviewerRoster').mockResolvedValue([
      { project_id: 'project-a', stage: 'title_abstract', reviewer_id: 'alice', is_active: true },
      { project_id: 'project-a', stage: 'title_abstract', reviewer_id: 'bob', is_active: true },
    ]);
    vi.spyOn(screeningApi, 'getConflicts').mockResolvedValue({
      total: 1, offset: 0, limit: 25,
      items: [{ publication_id: 'paper-a', publication_title: 'Paper A', stage: 'title_abstract', status: 'conflict', expected_reviewers: ['alice', 'bob'], pending_reviewers: [], latest_decisions: [{ reviewer_id: 'alice', outcome: 'include', decision_id: 'a', decided_at: '2026-08-11T00:00:00Z' }, { reviewer_id: 'bob', outcome: 'exclude', decision_id: 'b', decided_at: '2026-08-11T00:00:01Z' }] }],
    });
    vi.spyOn(screeningApi, 'getConflictMetrics').mockResolvedValue({ incomplete: 0, agreement: 2, conflict: 1, agreement_rate: 2 / 3 });
  });

  it('renders derived conflict details and resets the list filter', async () => {
    render(<MemoryRouter initialEntries={['/projects/project-a/screen/conflicts']}><Routes><Route path="/projects/:projectId/screen/conflicts" element={<ScreeningConflictsPage />} /></Routes></MemoryRouter>);
    expect(await screen.findByText('Paper A')).toBeInTheDocument();
    expect(screen.getByText('alice: include · bob: exclude')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Filtr'), { target: { value: 'conflict' } });
    expect(await screen.findByText('Paper A')).toBeInTheDocument();
    expect(screeningApi.getConflicts).toHaveBeenLastCalledWith('project-a', 'title_abstract', 'conflict', 0, 25, 'alice');
  });
});
