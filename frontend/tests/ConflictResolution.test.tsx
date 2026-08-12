import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { ConflictResolutionPage } from '../src/pages/ConflictResolutionPage';
import {
  ApiError,
  ConflictResolution,
  ScreeningConflict,
  screeningApi,
} from '../src/services/api/screeningApi';

const decision = (reviewer: string, outcome: 'include' | 'exclude') => ({
  reviewer_id: reviewer,
  outcome,
  decision_id: `decision-${reviewer}`,
  decided_at: '2026-08-11T10:00:00Z',
  decision: {
    decision_id: `decision-${reviewer}`,
    project_id: 'project-a',
    publication_id: 'paper-a',
    stage: 'full_text' as const,
    outcome,
    reviewer_id: reviewer,
    rationale: `${reviewer} detailed rationale`,
    criterion_snapshot_schema_version: 2,
    criterion_assessments: [{
      criterion_id: reviewer === 'bob' ? 'criterion-exclusion' : 'criterion-inclusion',
      criterion_name: reviewer === 'bob' ? 'Wrong population' : 'Relevant design',
      criterion_type: reviewer === 'bob' ? 'exclusion' as const : 'inclusion' as const,
      criterion_stage: 'full_text' as const,
      criterion_is_required: true,
      assessment_value: reviewer === 'bob' ? 'met' as const : 'met' as const,
      notes: `${reviewer} criterion notes`,
    }],
    exclusion_reason_criterion_ids: reviewer === 'bob' ? ['criterion-exclusion'] : [],
    decided_at: '2026-08-11T10:00:00Z',
  },
});

const conflict: ScreeningConflict = {
  publication_id: 'paper-a',
  publication_title: 'Conflicted publication',
  stage: 'full_text',
  status: 'conflict',
  expected_reviewers: ['alice', 'bob'],
  pending_reviewers: [],
  latest_decisions: [decision('alice', 'include'), decision('bob', 'exclude')],
  current_decision_set_key: 'decision-set-key',
  resolution: null,
};

const historical: ConflictResolution = {
  resolution_id: 'resolution-old', project_id: 'project-a', publication_id: 'paper-a',
  stage: 'full_text', decision_set_key: 'old-key', resolved_outcome: 'exclude',
  resolver_id: 'previous-resolver', rationale: 'Previous rationale',
  resolved_at: '2026-08-10T10:00:00Z', decision_ids: ['decision-alice', 'decision-bob'],
  is_current: false,
};

const renderPage = (projectId = 'project-a') => render(
  <MemoryRouter initialEntries={[`/projects/${projectId}/screen/conflict-resolution`]}>
    <Routes>
      <Route path="/projects/:projectId/screen/conflict-resolution" element={<ConflictResolutionPage />} />
    </Routes>
  </MemoryRouter>,
);

describe('Conflict Resolution workspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('slr_screening_reviewer_id', 'current-reviewer');
    vi.spyOn(screeningApi, 'getConflicts').mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [conflict] });
    vi.spyOn(screeningApi, 'getConflictMetrics').mockResolvedValue({ incomplete: 0, agreement: 0, conflict: 1, agreement_rate: null });
    vi.spyOn(screeningApi, 'getReviewerRoster').mockResolvedValue([
      { project_id: 'project-a', stage: 'full_text', reviewer_id: 'alice', is_active: true },
      { project_id: 'project-a', stage: 'full_text', reviewer_id: 'bob', is_active: true },
    ]);
    vi.spyOn(screeningApi, 'getConflictResolutionHistory').mockResolvedValue({
      publication_id: 'paper-a', stage: 'full_text', current_decision_set_key: 'decision-set-key',
      total: 1, offset: 0, limit: 100,
      resolutions: [historical],
    });
    vi.spyOn(screeningApi, 'saveConflictResolution').mockResolvedValue({
      ...historical, resolution_id: 'resolution-new', decision_set_key: 'decision-set-key',
      resolved_outcome: 'include', resolver_id: 'edited-resolver', rationale: 'Resolution rationale',
      is_current: true,
    });
  });

  it('renders conflict detail, reviewer context, editable prefill, history, and saves', async () => {
    renderPage();
    expect(await screen.findAllByText('Conflicted publication')).toHaveLength(2);
    expect(screen.getByLabelText('Etap')).toHaveStyle({ backgroundColor: 'var(--bg-primary)' });
    expect(screen.getByLabelText('Filtr statusu')).toHaveStyle({ backgroundColor: 'var(--bg-primary)' });
    expect(screen.getByText('alice: include')).toBeInTheDocument();
    expect(screen.getByText('Uzasadnienie: alice detailed rationale')).toBeInTheDocument();
    expect(screen.getByText('Kryteria: Relevant design: met')).toBeInTheDocument();
    expect(screen.getByText('Powody wykluczenia: Wrong population')).toBeInTheDocument();
    expect(screen.getByText(/exclude · previous-resolver — nieaktualne/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Etap'), { target: { value: 'full_text' } });
    await waitFor(() => expect(screeningApi.getConflicts).toHaveBeenLastCalledWith(
      'project-a', 'full_text', null, 0, 100, 'current-reviewer', true,
    ));
    const resolver = screen.getByLabelText('Osoba rozstrzygająca');
    expect(resolver).toHaveValue('current-reviewer');
    fireEvent.change(resolver, { target: { value: 'edited-resolver' } });
    fireEvent.change(screen.getByLabelText('Uzasadnienie rozstrzygnięcia'), { target: { value: 'Resolution rationale' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz rozstrzygnięcie' }));
    await waitFor(() => expect(screeningApi.saveConflictResolution).toHaveBeenCalledWith('project-a', {
      publication_id: 'paper-a', stage: 'full_text', resolved_outcome: 'include',
      resolver_id: 'edited-resolver', rationale: 'Resolution rationale',
      expected_decision_set_key: 'decision-set-key',
    }));
    expect(await screen.findByRole('status')).toHaveTextContent('Rozstrzygnięcie zapisane.');
  });

  it('renders conflict, resolved, and stale entries in the queue', async () => {
    vi.mocked(screeningApi.getConflicts).mockResolvedValue({
      total: 3, offset: 0, limit: 100,
      items: [
        conflict,
        { ...conflict, publication_id: 'paper-resolved', publication_title: 'Resolved paper', status: 'resolved' },
        { ...conflict, publication_id: 'paper-stale', publication_title: 'Stale paper', status: 'stale_resolution' },
      ],
    });
    renderPage();
    expect(await screen.findByText('Resolved paper')).toBeInTheDocument();
    expect(screen.getAllByText('Konflikt')).not.toHaveLength(0);
    expect(screen.getAllByText('Rozstrzygnięte')).not.toHaveLength(0);
    expect(screen.getAllByText('Nieaktualne rozstrzygnięcie')).not.toHaveLength(0);
  });

  it('shows stale state and preserves the draft on 409 until explicit reload', async () => {
    vi.mocked(screeningApi.getConflicts).mockResolvedValue({
      total: 1, offset: 0, limit: 100, items: [{ ...conflict, status: 'stale_resolution' }],
    });
    vi.mocked(screeningApi.saveConflictResolution).mockRejectedValue(
      new ApiError('Reviewer decisions changed', 409, 'decision_set_changed'),
    );
    renderPage();
    expect(await screen.findAllByText('Nieaktualne rozstrzygnięcie')).not.toHaveLength(0);
    const rationale = screen.getByLabelText('Uzasadnienie rozstrzygnięcia');
    fireEvent.change(rationale, { target: { value: 'Keep this draft' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz rozstrzygnięcie' }));
    expect(await screen.findByText(/Wczytaj konflikt ponownie przed zapisem/)).toBeInTheDocument();
    expect(rationale).toHaveValue('Keep this draft');
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }));
    await waitFor(() => expect(screeningApi.getConflicts).toHaveBeenCalledTimes(2));
  });

  it('renders loading, empty, and error states', async () => {
    let release: ((value: { total: number; offset: number; limit: number; items: ScreeningConflict[] }) => void) | undefined;
    vi.mocked(screeningApi.getConflicts).mockReturnValueOnce(new Promise((resolve) => { release = resolve; }));
    const view = renderPage();
    expect(screen.getByText('Ładowanie konfliktów i rozstrzygnięć...')).toBeInTheDocument();
    release?.({ total: 0, offset: 0, limit: 100, items: [] });
    expect(await screen.findByText('Brak konfliktów wymagających rozstrzygnięcia')).toBeInTheDocument();
    view.unmount();

    vi.mocked(screeningApi.getConflicts).mockRejectedValueOnce(new Error('Workspace unavailable'));
    renderPage();
    expect(await screen.findByText('Workspace unavailable')).toBeInTheDocument();
  });

  it('does not let a late response from the previous project overwrite the new project', async () => {
    let releaseA: ((value: { total: number; offset: number; limit: number; items: ScreeningConflict[] }) => void) | undefined;
    vi.mocked(screeningApi.getConflicts).mockImplementation((projectId) => {
      if (projectId === 'project-a') return new Promise((resolve) => { releaseA = resolve; });
      return Promise.resolve({ total: 1, offset: 0, limit: 100, items: [{
        ...conflict, publication_id: 'paper-b', publication_title: 'Project B publication',
      }] });
    });
    vi.mocked(screeningApi.getConflictResolutionHistory).mockResolvedValue({
      publication_id: 'paper-b', stage: 'title_abstract', current_decision_set_key: 'b-key',
      total: 0, offset: 0, limit: 100, resolutions: [],
    });
    const Switcher = () => {
      const navigate = useNavigate();
      return <><button onClick={() => navigate('/projects/project-b/screen/conflict-resolution')}>Switch project</button><ConflictResolutionPage /></>;
    };
    render(<MemoryRouter initialEntries={['/projects/project-a/screen/conflict-resolution']}><Routes>
      <Route path="/projects/:projectId/screen/conflict-resolution" element={<Switcher />} />
    </Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Switch project' }));
    expect(await screen.findAllByText('Project B publication')).toHaveLength(2);
    releaseA?.({ total: 1, offset: 0, limit: 100, items: [conflict] });
    await waitFor(() => expect(screen.queryByText('Conflicted publication')).not.toBeInTheDocument());
  });
});
