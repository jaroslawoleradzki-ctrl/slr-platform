import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { AppShell } from '../src/components/layout/AppShell';
import { ScreeningPage } from '../src/pages/ScreeningPage';
import { projectApiService } from '../src/services/api/projectApi';
import { ScreeningCriterionResponse } from '../src/types';

describe('Screening Criteria Configuration GUI (Phase 7.3)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
      {
        id: 'ai_architecture',
        title: 'AI Architecture Project',
        description: '',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '', updatedAt: '',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
        conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
    ]);
  });

  const mockCriterionActive: ScreeningCriterionResponse = {
    criterion_id: 'crit-uuid-001',
    project_id: 'lean_energy',
    name: 'Peer-reviewed Journal Articles',
    description: 'Must be published in a peer-reviewed scientific journal.',
    criterion_type: 'inclusion',
    screening_stage: 'title_abstract',
    display_order: 1,
    is_active: true,
    is_required: true,
  };

  const mockCriterionExclusion: ScreeningCriterionResponse = {
    criterion_id: 'crit-uuid-002',
    project_id: 'lean_energy',
    name: 'Non-English Publications',
    description: 'Exclude articles not available in English language.',
    criterion_type: 'exclusion',
    screening_stage: 'both',
    display_order: 2,
    is_active: true,
    is_required: false,
  };

  const mockCriterionInactive: ScreeningCriterionResponse = {
    criterion_id: 'crit-uuid-003',
    project_id: 'lean_energy',
    name: 'Conference Abstracts Only',
    description: 'Short conference abstracts without full paper.',
    criterion_type: 'exclusion',
    screening_stage: 'full_text',
    display_order: 3,
    is_active: false,
    is_required: true,
  };

  const renderComponent = (initialRoute = '/projects/lean_energy/screen') => {
    return render(
      <ProjectProvider>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route path="/projects/:projectId/screen" element={<ScreeningPage />} />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );
  };

  const renderComponentWithAppShell = (initialRoute = '/projects/proj_alpha/screen') => {
    return render(
      <ProjectProvider>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route path="/projects/:projectId" element={<AppShell />}>
              <Route path="screen" element={<ScreeningPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );
  };

  // Test 1: Loading state
  it('1. renders loading state during GET request', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockReturnValue(new Promise(() => {}));
    renderComponent();
    expect(await screen.findByText(/Ładowanie kryteriów screeningu z backendu/i)).toBeInTheDocument();
  });

  // Test 2: Empty state
  it('2. renders empty state when backend returns 0 criteria', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [],
      total: 0,
    });
    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów screeningu/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Dodaj pierwsze kryterium/i })).toBeInTheDocument();
  });

  // Test 3: Criteria loaded from backend
  it('3. renders criteria list loaded from backend', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive, mockCriterionExclusion],
      total: 2,
    });
    renderComponent();
    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();
    expect(screen.getByText('Non-English Publications')).toBeInTheDocument();
  });

  // Test 4: Inclusion / Exclusion rendering
  it('4. correctly renders Inclusion and Exclusion badges', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive, mockCriterionExclusion],
      total: 2,
    });
    renderComponent();
    expect(await screen.findByText('Inclusion')).toBeInTheDocument();
    expect(screen.getByText('Exclusion')).toBeInTheDocument();
  });

  // Test 5: Correct stage rendering
  it('5. correctly renders stage badges (Title & Abstract, Both, Full Text)', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive, mockCriterionExclusion, mockCriterionInactive],
      total: 3,
    });
    renderComponent();
    expect(await screen.findByText('Etap: Title & Abstract')).toBeInTheDocument();
    expect(screen.getByText('Etap: Both')).toBeInTheDocument();
    expect(screen.getByText('Etap: Full Text')).toBeInTheDocument();
  });

  // Test 6: Required / Optional rendering
  it('6. correctly renders required and optional badges', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive, mockCriterionExclusion],
      total: 2,
    });
    renderComponent();
    expect(await screen.findByText('Required (Wymagane)')).toBeInTheDocument();
    expect(screen.getByText('Optional (Opcjonalne)')).toBeInTheDocument();
  });

  // Test 7: Active / Inactive rendering
  it('7. correctly renders active and inactive indicators', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive, mockCriterionInactive],
      total: 2,
    });
    renderComponent();
    expect(await screen.findByText('Aktywne')).toBeInTheDocument();
    expect(screen.getByText('Dezaktywowane')).toBeInTheDocument();
  });

  // Test 8: Create criterion
  it('8. opens create modal, submits form, and calls createScreeningCriterion API', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria')
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce({ items: [{ ...mockCriterionActive, name: 'New Custom Inclusion Rule' }], total: 1 });

    const createSpy = vi.spyOn(projectApiService, 'createScreeningCriterion').mockResolvedValue({
      ...mockCriterionActive,
      criterion_id: 'new-uuid-004',
      name: 'New Custom Inclusion Rule',
    });

    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów/i)).toBeInTheDocument();

    const addBtn = screen.getAllByRole('button', { name: /Dodaj/i })[0];
    fireEvent.click(addBtn);

    expect(screen.getByText('Dodaj nowe kryterium screeningu')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Kryterium aktywne/i)).not.toBeInTheDocument(); // Requirement 2: No active/inactive toggle on create

    const nameInput = screen.getByLabelText(/Nazwa kryterium/i);
    fireEvent.change(nameInput, { target: { value: 'New Custom Inclusion Rule' } });

    const submitBtn = screen.getByRole('button', { name: /Utwórz kryterium/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('lean_energy', {
        name: 'New Custom Inclusion Rule',
        description: null,
        criterion_type: 'inclusion',
        screening_stage: 'title_abstract',
        display_order: 0,
        is_active: true,
        is_required: true,
      });
    });
  });

  it('configures an automatic metadata rule and hides its value for EXISTS', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({ items: [], total: 0 });
    const createSpy = vi.spyOn(projectApiService, 'createScreeningCriterion').mockResolvedValue(mockCriterionActive);
    renderComponent();
    await screen.findByText(/Nie zdefiniowano jeszcze kryteriów/i);
    fireEvent.click(screen.getAllByRole('button', { name: /Dodaj/i })[0]);
    fireEvent.change(screen.getByLabelText(/Nazwa kryterium/i), { target: { value: 'Prace po 2021' } });
    fireEvent.click(within(screen.getByRole('group', { name: 'Sposób oceny' })).getByRole('button', { name: 'Automatyczna na podstawie metadanych' }));
    fireEvent.change(screen.getByLabelText('Pole reguły'), { target: { value: 'abstract' } });
    expect(screen.queryByLabelText('Wartość reguły')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Pole reguły'), { target: { value: 'publication_year' } });
    fireEvent.change(screen.getByLabelText('Operator reguły'), { target: { value: 'greater_than' } });
    fireEvent.change(screen.getByLabelText('Wartość reguły'), { target: { value: '2021' } });
    fireEvent.click(screen.getByRole('button', { name: /Utwórz kryterium/i }));
    await waitFor(() => expect(createSpy).toHaveBeenCalledWith('lean_energy', expect.objectContaining({ evaluation_mode: 'metadata_rule', metadata_rule: { field: 'publication_year', operator: 'greater_than', value: 2021 } })));
  });

  // Test 9: Edit criterion
  it('9. opens edit modal prefilled with target criterion data and calls updateScreeningCriterion API', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria')
      .mockResolvedValueOnce({ items: [mockCriterionActive], total: 1 })
      .mockResolvedValueOnce({ items: [{ ...mockCriterionActive, name: 'Updated Article Rule' }], total: 1 });

    const updateSpy = vi.spyOn(projectApiService, 'updateScreeningCriterion').mockResolvedValue({
      ...mockCriterionActive,
      name: 'Updated Article Rule',
    });

    renderComponent();
    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();

    const editBtn = screen.getByRole('button', { name: /Edytuj/i });
    fireEvent.click(editBtn);

    expect(screen.getByText('Edytuj kryterium screeningu')).toBeInTheDocument();
    expect(screen.getByLabelText(/Kryterium aktywne/i)).toBeInTheDocument(); // Allowed in edit mode

    const nameInput = screen.getByLabelText(/Nazwa kryterium/i);
    fireEvent.change(nameInput, { target: { value: 'Updated Article Rule' } });

    const saveBtn = screen.getByRole('button', { name: /Zapisz zmiany/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith('lean_energy', 'crit-uuid-001', {
        name: 'Updated Article Rule',
        description: 'Must be published in a peer-reviewed scientific journal.',
        criterion_type: 'inclusion',
        screening_stage: 'title_abstract',
        display_order: 1,
        is_active: true,
        is_required: true,
      });
    });
  });

  // Test 10: Deactivate criterion
  it('10. calls deactivateScreeningCriterion API on deactivate action', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive],
      total: 1,
    });
    const deactivateSpy = vi.spyOn(projectApiService, 'deactivateScreeningCriterion').mockResolvedValue({
      ...mockCriterionActive,
      is_active: false,
    });

    renderComponent();
    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();

    const deactivateBtn = screen.getByRole('button', { name: /Dezaktywuj/i });
    fireEvent.click(deactivateBtn);

    await waitFor(() => {
      expect(deactivateSpy).toHaveBeenCalledWith('lean_energy', 'crit-uuid-001');
    });
  });

  // Test 11: Reactivate criterion via PUT API call
  it('11. calls updateScreeningCriterion API with is_active=true on reactivate action', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionInactive],
      total: 1,
    });
    const updateSpy = vi.spyOn(projectApiService, 'updateScreeningCriterion').mockResolvedValue({
      ...mockCriterionInactive,
      is_active: true,
    });

    renderComponent();
    expect(await screen.findByText('Conference Abstracts Only')).toBeInTheDocument();

    const reactivateBtn = screen.getByRole('button', { name: /Aktywuj/i });
    fireEvent.click(reactivateBtn);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith('lean_energy', 'crit-uuid-003', {
        name: 'Conference Abstracts Only',
        description: 'Short conference abstracts without full paper.',
        criterion_type: 'exclusion',
        screening_stage: 'full_text',
        display_order: 3,
        is_active: true,
        is_required: true,
      });
    });
  });

  // Test 12: Validation: empty name
  it('12. shows validation error when submitting empty name in modal', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [],
      total: 0,
    });

    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów/i)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Dodaj/i })[0]);

    const submitBtn = screen.getByRole('button', { name: /Utwórz kryterium/i });
    fireEvent.submit(submitBtn.closest('form')!);

    expect(await screen.findByText('Nazwa kryterium nie może być pusta.')).toBeInTheDocument();
  });

  // Test 13: Validation: negative display_order
  it('13. shows validation error when submitting negative display order', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [],
      total: 0,
    });

    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów/i)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Dodaj/i })[0]);

    const nameInput = screen.getByLabelText(/Nazwa kryterium/i);
    fireEvent.change(nameInput, { target: { value: 'Valid Name' } });

    const orderInput = screen.getByLabelText(/Kolejność wyświetlania/i);
    fireEvent.change(orderInput, { target: { value: '-5' } });

    const submitBtn = screen.getByRole('button', { name: /Utwórz kryterium/i });
    fireEvent.submit(submitBtn.closest('form')!);

    expect(await screen.findByText('Kolejność wyświetlania nie może być ujemna.')).toBeInTheDocument();
  });

  // Test 14: API create error
  it('14. displays API error when createScreeningCriterion fails', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.spyOn(projectApiService, 'createScreeningCriterion').mockRejectedValue(
      new Error('Błąd serwera przy tworzeniu kryterium.')
    );

    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów/i)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Dodaj/i })[0]);

    const nameInput = screen.getByLabelText(/Nazwa kryterium/i);
    fireEvent.change(nameInput, { target: { value: 'Fail Name' } });

    const submitBtn = screen.getByRole('button', { name: /Utwórz kryterium/i });
    fireEvent.submit(submitBtn.closest('form')!);

    expect(await screen.findByText(/Błąd serwera przy tworzeniu kryterium/i)).toBeInTheDocument();
  });

  // Test 15: API update error
  it('15. displays API error when updateScreeningCriterion fails', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive],
      total: 1,
    });
    vi.spyOn(projectApiService, 'updateScreeningCriterion').mockRejectedValue(
      new Error('Błąd aktualizacji w bazie.')
    );

    renderComponent();
    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Edytuj/i }));

    const submitBtn = screen.getByRole('button', { name: /Zapisz zmiany/i });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/Błąd aktualizacji w bazie/i)).toBeInTheDocument();
  });

  // Test 16: API deactivate error
  it('16. displays error alert when deactivateScreeningCriterion fails', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive],
      total: 1,
    });
    vi.spyOn(projectApiService, 'deactivateScreeningCriterion').mockRejectedValue(
      new Error('Błąd połączenia podczas dezaktywacji.')
    );

    renderComponent();
    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Dezaktywuj/i }));

    expect(await screen.findByText(/Błąd połączenia podczas dezaktywacji/i)).toBeInTheDocument();
  });

  // Test 17: GET error
  it('17. displays error alert when listScreeningCriteria fails on page load', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockRejectedValue(
      new Error('Błąd połączenia z bazą SQLite.')
    );

    renderComponent();

    expect(await screen.findByText(/Nie udało się pobrać kryteriów screeningu: Błąd połączenia z bazą SQLite/i)).toBeInTheDocument();
  });

  // Test 18: Retry after GET error
  it('18. retries fetching criteria when clicking Retry button after GET error', async () => {
    const listSpy = vi.spyOn(projectApiService, 'listScreeningCriteria')
      .mockRejectedValueOnce(new Error('Chwilowy błąd SIECI'))
      .mockResolvedValueOnce({
        items: [mockCriterionActive],
        total: 1,
      });

    renderComponent();

    expect(await screen.findByText(/Chwilowy błąd SIECI/i)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Spróbuj ponownie/i });
    fireEvent.click(retryBtn);

    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();
    expect(listSpy).toHaveBeenCalledTimes(2);
  });

  // Test 19: Project change reloads criteria
  it('19. reloads criteria when route project ID changes', async () => {
    const listSpy = vi.spyOn(projectApiService, 'listScreeningCriteria').mockImplementation(async (projId) => {
      if (projId === 'ai_architecture') {
        return { items: [mockCriterionActive], total: 1 };
      }
      return { items: [mockCriterionExclusion], total: 1 };
    });

    renderComponentWithAppShell('/projects/ai_architecture/screen');
    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();

    expect(listSpy).toHaveBeenCalledWith('ai_architecture');
  });

  // Test 20: No hardcoded criteria
  it('20. verifies zero hardcoded criteria exist on empty backend response', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [],
      total: 0,
    });

    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów screeningu/i)).toBeInTheDocument();

    expect(screen.queryByText(/K1/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Lean Management/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Energy Efficiency/i)).not.toBeInTheDocument();
  });

  // Test 21: Deterministic list order preserved
  it('21. preserves display order of criteria as returned by backend', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [mockCriterionActive, mockCriterionExclusion, mockCriterionInactive],
      total: 3,
    });

    renderComponent();

    expect(await screen.findByText('Peer-reviewed Journal Articles')).toBeInTheDocument();

    const headings = screen.getAllByRole('heading', { level: 3 });
    expect(headings[0]).toHaveTextContent('Peer-reviewed Journal Articles');
    expect(headings[1]).toHaveTextContent('Non-English Publications');
    expect(headings[2]).toHaveTextContent('Conference Abstracts Only');
  });

  // Test 22: Create/update buttons disabled while saving
  it('22. disables submit button while API call is in progress', async () => {
    vi.spyOn(projectApiService, 'listScreeningCriteria').mockResolvedValue({
      items: [],
      total: 0,
    });
    let resolveCreate!: (val: ScreeningCriterionResponse) => void;
    vi.spyOn(projectApiService, 'createScreeningCriterion').mockReturnValue(
      new Promise((res) => { resolveCreate = res; })
    );

    renderComponent();
    expect(await screen.findByText(/Nie zdefiniowano jeszcze kryteriów/i)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Dodaj/i })[0]);

    const nameInput = screen.getByLabelText(/Nazwa kryterium/i);
    fireEvent.change(nameInput, { target: { value: 'Async Rule' } });

    const submitBtn = screen.getByRole('button', { name: /Utwórz kryterium/i });
    fireEvent.click(submitBtn);

    expect(screen.getByRole('button', { name: /Zapisywanie/i })).toBeDisabled();

    await act(async () => {
      resolveCreate({
        ...mockCriterionActive,
        criterion_id: 'async-001',
        name: 'Async Rule',
      });
    });
  });
});
