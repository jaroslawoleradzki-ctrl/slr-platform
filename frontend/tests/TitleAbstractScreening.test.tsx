import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { ScreeningSectionLayout } from '../src/components/screening/ScreeningSectionLayout';
import { TitleAbstractScreeningPage } from '../src/pages/TitleAbstractScreeningPage';
import { screeningApi, TitleAbstractOverview, TitleAbstractRecord } from '../src/services/api/screeningApi';

const criterion = {
  criterion_id: 'criterion-required', project_id: 'project-a', name: 'Relevant topic', description: 'Matches the review question.',
  criterion_type: 'inclusion' as const, screening_stage: 'title_abstract' as const, display_order: 1, is_active: true, is_required: true,
};
const optionalCriterion = { ...criterion, criterion_id: 'criterion-optional', name: 'Peer reviewed', screening_stage: 'both' as const, is_required: false };
const overview = (overrides: Partial<TitleAbstractOverview> = {}): TitleAbstractOverview => ({
  project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, readiness_status: 'ready', working_collection_count: 3,
  canonical_records_count: 3, unresolved_duplicate_groups: 0, criteria: [criterion, optionalCriterion],
  progress: { total: 3, unscreened: 3, included: 0, excluded: 0, uncertain: 0, completed: 0 }, ...overrides,
});
const record = (id: string, title = `Title ${id}`): TitleAbstractRecord => ({
  publication_id: id, title, abstract: `Abstract ${id}`, authors: ['Ada Lovelace'], publication_year: 2025, publication_date: null,
  identifiers: [{ type: 'doi', value: `10.1/${id}`, source: 'openalex' }], doi: `10.1/${id}`,
  venue: { name: 'Journal of Tests', type: 'journal', publisher: 'Test Press' }, publisher: 'Test Press', document_type: 'article',
  language: 'en', keywords: ['screening'], urls: ['https://example.test/article'], open_access: true, status: 'unscreened', latest_decision: null,
});
const decision = (outcome: 'include' | 'exclude' | 'uncertain' = 'include') => ({
  decision_id: 'decision-1', project_id: 'project-a', publication_id: 'A', stage: 'title_abstract' as const, outcome,
  reviewer_id: 'reviewer-a', rationale: 'Relevant', decided_at: '2026-08-10T10:00:00Z',
  criterion_assessments: [{ criterion_id: criterion.criterion_id, criterion_name: criterion.name, criterion_type: 'inclusion' as const, criterion_stage: 'title_abstract' as const, criterion_is_required: true, assessment_value: 'met' as const, notes: 'Fits' }],
});

describe('Title & Abstract Screening GUI (Phase 7.5C)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue(overview());
    vi.spyOn(screeningApi, 'listRecords').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 1, offset: 0, limit: 50, items: [record('A')] });
    vi.spyOn(screeningApi, 'getRecord').mockResolvedValue(record('A'));
    vi.spyOn(screeningApi, 'saveDecision').mockResolvedValue(decision());
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  const renderPage = (route = '/projects/project-a/screen/title-abstract') => render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/projects/:projectId/screen" element={<ScreeningSectionLayout />}>
          <Route path="title-abstract" element={<TitleAbstractScreeningPage />} />
          <Route path="title-abstract/:publicationId" element={<TitleAbstractScreeningPage />} />
          <Route path="criteria" element={<div>Criteria configuration route</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  const enterReviewer = async (value = ' reviewer-a ') => {
    fireEvent.change(screen.getByLabelText('Reviewer identifier'), { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: 'Rozpocznij screening' }));
    await screen.findByText('Title A');
  };
  const renderReady = async () => { localStorage.setItem('slr_screening_reviewer_id', 'reviewer-a'); renderPage(); await screen.findByText('Title A'); };
  const assessRequired = () => fireEvent.click(within(screen.getByRole('group', { name: 'Relevant topic' })).getByRole('button', { name: 'Spełnione' }));
  const chooseOutcome = (label: string) => fireEvent.click(within(screen.getByRole('group', { name: 'Decyzja końcowa' })).getByRole('button', { name: label }));

  it('requires, trims, persists, and visibly allows changing local reviewer identity', async () => {
    renderPage();
    expect(screen.getByText('Podaj lokalny identyfikator reviewera. Nie jest to konto ani login.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Rozpocznij screening' }));
    expect(screen.getByText('Identyfikator reviewera nie może być pusty.')).toBeInTheDocument();
    await enterReviewer();
    expect(localStorage.getItem('slr_screening_reviewer_id')).toBe('reviewer-a');
    expect(screen.getByText('Reviewer:')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Zmień' }));
    expect(screen.getByText('Zmień reviewera')).toBeInTheDocument();
  });

  it('renders canonical publication metadata, TITLE_ABSTRACT/BOTH criteria, progress and latest decision', async () => {
    const withLatest = { ...record('A'), latest_decision: decision() };
    vi.spyOn(screeningApi, 'listRecords').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 1, offset: 0, limit: 50, items: [withLatest] });
    await renderReady();
    expect(screen.getByText('Abstract A')).toBeInTheDocument();
    expect(screen.getByText(/Journal of Tests/)).toBeInTheDocument();
    expect(screen.getByText(/Włączone: 0/)).toBeInTheDocument();
    expect(screen.getByText('Relevant topic')).toBeInTheDocument();
    expect(screen.getByText('Peer reviewed')).toBeInTheDocument();
    expect(screen.getByText('Najnowsza decyzja:', { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/Relevant topic: met/)).toBeInTheDocument();
  });

  it('renders an automatic criterion as read-only and excludes it from the client decision payload', async () => {
    const automatic = {
      ...criterion,
      criterion_id: 'criterion-year',
      name: 'Prace po 2021',
      evaluation_mode: 'metadata_rule' as const,
      metadata_rule: { field: 'publication_year' as const, operator: 'greater_than' as const, value: 2021 },
    };
    const automaticRecord = {
      ...record('A'),
      automatic_assessments: [{ criterion_id: automatic.criterion_id, assessment_value: 'met' as const, evaluated_metadata_value: 2025 }],
    };
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue(overview({ criteria: [criterion, automatic] }));
    vi.spyOn(screeningApi, 'listRecords').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 1, offset: 0, limit: 50, items: [automaticRecord] });
    await renderReady();
    const automaticPanel = screen.getByTestId('automatic-assessment-criterion-year');
    expect(automaticPanel).toHaveTextContent('Automatyczne');
    expect(automaticPanel).toHaveTextContent('Rok publikacji');
    expect(automaticPanel).toHaveTextContent('Wartość publikacji: 2025');
    expect(automaticPanel).toHaveTextContent('Wynik: Spełnione');
    expect(within(automaticPanel).queryByRole('button')).not.toBeInTheDocument();
    assessRequired(); chooseOutcome('Włącz'); fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    await waitFor(() => expect(screeningApi.saveDecision).toHaveBeenCalledWith('project-a', expect.objectContaining({ criterion_assessments: [expect.objectContaining({ criterion_id: 'criterion-required' })] })));
    expect(vi.mocked(screeningApi.saveDecision).mock.calls.at(-1)?.[1].criterion_assessments).not.toContainEqual(expect.objectContaining({ criterion_id: 'criterion-year' }));
  });

  it.each([
    ['unresolved_duplicates', 'Pozostały nierozstrzygnięte duplikaty.'],
    ['merge_conflict', 'Wystąpił konflikt metadanych podczas tworzenia canonical screening input set.'],
  ] as const)('blocks executable workflow for %s readiness', async (readiness_status, message) => {
    localStorage.setItem('slr_screening_reviewer_id', 'reviewer-a');
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue(overview({ ready: false, readiness_status, unresolved_duplicate_groups: readiness_status === 'unresolved_duplicates' ? 2 : 0 }));
    renderPage();
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText('Decyzja końcowa')).not.toBeInTheDocument();
  });

  it('renders empty and missing-abstract states', async () => {
    localStorage.setItem('slr_screening_reviewer_id', 'reviewer-a');
    vi.spyOn(screeningApi, 'listRecords').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 0, offset: 0, limit: 50, items: [] });
    renderPage();
    expect(await screen.findByText('Brak publikacji do screeningu')).toBeInTheDocument();
  });

  it('renders an explicit missing-abstract state without losing the publication metadata', async () => {
    vi.spyOn(screeningApi, 'listRecords').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 1, offset: 0, limit: 50, items: [{ ...record('A'), abstract: null }] });
    await renderReady();
    expect(screen.getByText('Brak abstraktu w zapisanych metadanych publikacji.')).toBeInTheDocument();
    expect(screen.getByText(/10.1\/A/)).toBeInTheDocument();
  });

  it('requires required assessment and sends rationale and criterion notes', async () => {
    await renderReady();
    expect(screen.getByRole('button', { name: 'Zapisz' })).toBeDisabled();
    expect(screen.getByLabelText('Decision rationale')).toHaveStyle('background-color: var(--bg-primary)');
    assessRequired();
    expect(within(screen.getByRole('group', { name: 'Relevant topic' })).getByRole('button', { name: 'Spełnione' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.change(screen.getByLabelText('Notes for Relevant topic'), { target: { value: 'criterion note' } });
    fireEvent.change(screen.getByLabelText('Decision rationale'), { target: { value: 'reason' } });
    chooseOutcome('Włącz');
    expect(within(screen.getByRole('group', { name: 'Decyzja końcowa' })).getByRole('button', { name: 'Włącz' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    await waitFor(() => expect(screeningApi.saveDecision).toHaveBeenLastCalledWith('project-a', expect.objectContaining({ outcome: 'include', rationale: 'reason', criterion_assessments: [expect.objectContaining({ criterion_id: 'criterion-required', assessment_value: 'met', notes: 'criterion note' })] })));
  });

  it.each([['Wyklucz', 'exclude'], ['Niepewne', 'uncertain']] as const)('saves a %s decision', async (button, outcome) => {
    await renderReady(); assessRequired(); chooseOutcome(button); fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    await waitFor(() => expect(screeningApi.saveDecision).toHaveBeenCalledWith('project-a', expect.objectContaining({ outcome })));
  });

  it('Save & Next keeps UNSCREENED offset at zero and does not skip B after A is removed', async () => {
    const a = record('A'); const b = record('B'); const c = record('C');
    vi.spyOn(screeningApi, 'listRecords')
      .mockResolvedValueOnce({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 3, offset: 0, limit: 50, items: [a, b, c] })
      .mockResolvedValueOnce({ project_id: 'project-a', reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 2, offset: 0, limit: 50, items: [b, c] });
    await renderReady(); assessRequired(); chooseOutcome('Włącz');
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz i następny' }));
    expect(await screen.findByText('Title B')).toBeInTheDocument();
    expect(screeningApi.listRecords).toHaveBeenLastCalledWith('project-a', 'reviewer-a', 'unscreened', 0, 50);
  });

  it('does not navigate after failed save, refreshes filters at offset zero, and supports retryable API errors', async () => {
    await renderReady(); assessRequired(); chooseOutcome('Wyklucz');
    vi.spyOn(screeningApi, 'saveDecision').mockRejectedValueOnce(new Error('Backend unavailable'));
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz i następny' }));
    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument();
    expect(screen.getByText('Title A')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Włączone' }));
    await waitFor(() => expect(screeningApi.listRecords).toHaveBeenLastCalledWith('project-a', 'reviewer-a', 'included', 0, 50));
  });

  it('reloads the workflow for an explicitly changed reviewer and retains reviewer-specific resume state', async () => {
    await renderReady();
    fireEvent.click(screen.getByRole('button', { name: 'Zmień' }));
    fireEvent.change(screen.getByLabelText('Reviewer identifier'), { target: { value: 'reviewer-b' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz identyfikator' }));
    await waitFor(() => expect(screeningApi.getOverview).toHaveBeenLastCalledWith('project-a', 'reviewer-b'));
    expect(localStorage.getItem('slr_screening_reviewer_id')).toBe('reviewer-b');
  });

  it('shows an eligible-record 404 and refreshes a readiness change after a 409', async () => {
    await renderReady(); assessRequired(); chooseOutcome('Włącz');
    vi.spyOn(screeningApi, 'saveDecision').mockRejectedValueOnce({ message: 'missing', status: 404 });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    expect(await screen.findByText('Ta publikacja nie należy już do aktualnego Screening Input Set.')).toBeInTheDocument();

    vi.spyOn(screeningApi, 'saveDecision').mockRejectedValueOnce({ message: 'not ready', status: 409 });
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue(overview({ ready: false, readiness_status: 'merge_conflict' }));
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    expect(await screen.findByText('Screening nie może się rozpocząć')).toBeInTheDocument();
  });

  it('ignores a late response from the previous project after a project switch', async () => {
    localStorage.setItem('slr_screening_reviewer_id', 'reviewer-a');
    let resolveProjectA: ((value: TitleAbstractOverview) => void) | undefined;
    vi.spyOn(screeningApi, 'getOverview').mockImplementation((projectId) => projectId === 'project-a'
      ? new Promise((resolve) => { resolveProjectA = resolve; })
      : Promise.resolve(overview({ project_id: 'project-b' })));
    vi.spyOn(screeningApi, 'listRecords').mockImplementation((projectId) => Promise.resolve({
      project_id: projectId, reviewer_id: 'reviewer-a', ready: true, status_filter: 'unscreened', total: 1, offset: 0, limit: 50,
      items: [record(projectId === 'project-b' ? 'B' : 'A')],
    }));
    const ProjectSwitcher = () => { const navigate = useNavigate(); return <button onClick={() => navigate('/projects/project-b/screen/title-abstract')}>Switch project</button>; };
    render(<MemoryRouter initialEntries={['/projects/project-a/screen/title-abstract']}><ProjectSwitcher /><Routes><Route path="/projects/:projectId/screen/title-abstract/:publicationId?" element={<TitleAbstractScreeningPage />} /></Routes></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Switch project' }));
    expect(await screen.findByText('Title B')).toBeInTheDocument();
    resolveProjectA?.(overview());
    await waitFor(() => expect(screen.queryByText('Title A')).not.toBeInTheDocument());
  });

  it('keeps Previous/Next at page boundaries and exposes section navigation to criteria', async () => {
    await renderReady();
    expect(screen.getByRole('button', { name: 'Poprzedni' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Następny' })).toBeDisabled();
    fireEvent.click(screen.getByRole('link', { name: 'Criteria Configuration' }));
    expect(await screen.findByText('Criteria configuration route')).toBeInTheDocument();
  });
});
