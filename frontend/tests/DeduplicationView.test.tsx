import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { DeduplicationPage } from '../src/pages/DeduplicationPage';
import { DuplicateGroupCardPreview } from '../src/components/deduplication/DuplicateGroupCardPreview';
import { projectApiService } from '../src/services/api/projectApi';
import { ApiDuplicateGroupListResponse } from '../src/types';

describe('DeduplicationPage Phase 6.5 — Duplicate Comparison & Review UI', () => {
  beforeEach(() => {
    localStorage.clear();
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
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
      },
    ]);
  });

  it('renders loading state while fetching candidate duplicate groups from API', async () => {
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockReturnValue(new Promise(() => {}));

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Pobieranie grup kandydatów z API backendu/i)).toBeInTheDocument();
  });

  it('renders duplicate candidate groups, side-by-side comparison, field states, and provenance', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-test-101',
          reason: 'Zgodność identyfikatorów (DOI: 10.1016/j.jclepro.2021.102834)',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1016/j.jclepro.2021.102834' }],
          records: [
            {
              id: 'rec-001',
              title: 'Lean Energy Management in Auto Production',
              authors: 'Smith, J., Kowalski, P.',
              year: 2021,
              source: 'OpenAlex',
              venue: 'Journal of Cleaner Production',
              doi: '10.1016/j.jclepro.2021.102834',
              provenance: [
                { source: 'OpenAlex', source_record_id: 'W3128349201', retrieved_at: '2026-07-01T10:00:00Z' },
              ],
            },
            {
              id: 'rec-002',
              title: 'Lean Energy Management in Auto Production',
              authors: 'Smith, John, Kowalski, Piotr',
              year: 2021,
              source: 'Crossref',
              venue: 'Journal of Cleaner Production',
              doi: '10.1016/j.jclepro.2021.102834',
              provenance: [
                { source: 'Crossref', source_record_id: '10.1016/j.jclepro.2021.102834', retrieved_at: '2026-07-01T10:00:00Z' },
              ],
            },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-test-101',
      decision: 'PENDING',
      rationale: null,
    });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/grp-test-101/i)).toBeInTheDocument();
    expect(screen.getByText(/Porównanie Publikacji Obok Siebie/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Zgodne \(Identical\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Różne \(Different\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/OpenAlex/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Crossref/i).length).toBeGreaterThan(0);
  });

  it('renders empty state when backend API returns 0 candidate duplicate groups', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'ai_architecture',
      total_groups_count: 0,
      groups: [],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Brak grup kandydatów na duplikaty/i)).toBeInTheDocument();
  });

  it('reruns duplicate detection with the existing GET endpoint and reports the result', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      {
        import_id: 'history-535',
        project_id: 'lean_energy',
        source_type: 'provider',
        filename: null,
        format: null,
        provider: 'openalex',
        query: 'accumulated imports',
        total_available: null,
        records_count: 535,
        status: 'success',
        created_at: '2026-08-04T08:00:00Z',
        warnings: [],
      },
    ]);
    const initialResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 0,
      groups: [],
    };
    const rerunResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [{
        group_id: 'grp-rerun-1',
        reason: 'Zgodność DOI',
        records_count: 2,
        status: 'APPROVED',
        rationale: 'Existing decision',
        shared_identifiers: [{ identifier_type: 'doi', value: '10.1000/rerun' }],
        records: [
          { id: 'r1', title: 'Rerun A', authors: 'A', year: 2024, source: 'OpenAlex' },
          { id: 'r2', title: 'Rerun B', authors: 'B', year: 2024, source: 'OpenAlex' },
        ],
      }],
    };
    const getGroupsSpy = vi.spyOn(projectApiService, 'getDuplicateGroups')
      .mockResolvedValueOnce(initialResponse)
      .mockResolvedValueOnce(rerunResponse);

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Brak grup kandydatów na duplikaty/i)).toBeInTheDocument();
    expect(screen.getByText(/Nigdy nie uruchamiano deduplikacji/i)).toBeInTheDocument();
    expect(screen.getByText(/Uruchom deduplikację, aby wyszukać grupy kandydatów/i)).toBeInTheDocument();
    expect(screen.queryByText(/Oceniono wszystkie grupy/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Uruchom deduplikację/i }));

    expect(await screen.findByText(/Deduplikacja zakończona pomyślnie/i)).toBeInTheDocument();
    expect(screen.getByText(/Zakończono pomyślnie/i)).toBeInTheDocument();
    expect(screen.getByText(/535 publikacji/i)).toBeInTheDocument();
    expect(screen.getByText(/Znaleziono grup/i).parentElement).toHaveTextContent('1');
    expect(screen.getByText(/Czas wykonania/i).parentElement).toHaveTextContent(/s/);
    expect(screen.getByText(/Oceniono wszystkie grupy/i)).toBeInTheDocument();
    expect(await screen.findByText(/Existing decision/i)).toBeInTheDocument();
    expect(getGroupsSpy).toHaveBeenCalledTimes(2);
  });

  it('shows analyzed record count, loading state, and successful zero-group result', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      {
        import_id: 'history-535-empty',
        project_id: 'lean_energy',
        source_type: 'provider',
        filename: null,
        format: null,
        provider: 'openalex',
        query: 'accumulated imports',
        total_available: null,
        records_count: 535,
        status: 'success',
        created_at: '2026-08-04T08:00:00Z',
        warnings: [],
      },
    ]);
    const emptyResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 0,
      groups: [],
    };
    let finishRerun!: (response: ApiDuplicateGroupListResponse) => void;
    vi.spyOn(projectApiService, 'getDuplicateGroups')
      .mockResolvedValueOnce(emptyResponse)
      .mockReturnValueOnce(new Promise((resolve) => { finishRerun = resolve; }));

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Wejściowa kolekcja: 535/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Uruchom deduplikację/i }));

    expect(screen.getByText(/Analizowanie 535 rekordów/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Uruchamianie deduplikacji/i })).toBeDisabled();

    await act(async () => finishRerun(emptyResponse));

    expect(await screen.findByText(/Deduplikacja zakończona pomyślnie/i)).toBeInTheDocument();
    expect(screen.queryByText(/Przeanalizowano 535 rekordów. Nie znaleziono grup kandydatów/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Nie znaleziono grup wymagających oceny/i)).toBeInTheDocument();
    expect(screen.getByText(/Wykryte grupy kandydatów/i)).toBeInTheDocument();
    expect(screen.getByText(/Decyzje APPROVE i REJECT są trwale zapisywane w bazie SQLite/i)).toBeInTheDocument();
    expect(screen.queryByText(/Trwała rejestracja decyzji w SQLite \(v0\.2\.2\)/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Oceniono wszystkie grupy/i)).not.toBeInTheDocument();
  });

  it('supports toggling comparison view with aria-expanded accessibility attribute', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-test-202',
          reason: 'Zgodność PMID',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'pmid', value: '12345' }],
          records: [
            { id: 'r1', title: 'Paper Alpha', authors: 'Author A', year: 2022, source: 'PubMed' },
            { id: 'r2', title: 'Paper Alpha', authors: 'Author A', year: 2022, source: 'S2' },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-test-202',
      decision: 'PENDING',
      rationale: null,
    });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    const toggleBtn = await screen.findByRole('button', { name: /Zwiń/i });
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText(/Porównanie Publikacji Obok Siebie/i)).not.toBeInTheDocument();
  });

  it('handles approve decision recording with rationale input', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-test-303',
          reason: 'Zgodność identyfikatorów',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1000/test' }],
          records: [
            { id: 'r1', title: 'Test Paper A', authors: 'A', year: 2020, source: 'Crossref' },
            { id: 'r2', title: 'Test Paper B', authors: 'B', year: 2020, source: 'OpenAlex' },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-test-303',
      decision: 'PENDING',
      rationale: null,
    });
    const postSpy = vi.spyOn(projectApiService, 'postDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-test-303',
      decision: 'APPROVE',
      rationale: 'Zweryfikowano zgodność po analizie abstraktów',
    });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Test Paper A/i)).toBeInTheDocument();

    const rationaleInput = screen.getByPlaceholderText(/Wprowadź opcjonalne uzasadnienie decyzji/i);
    fireEvent.change(rationaleInput, { target: { value: 'Zweryfikowano zgodność po analizie abstraktów' } });

    const approveBtn = screen.getByRole('button', { name: /Zatwierdź/i });
    fireEvent.click(approveBtn);

    expect(postSpy).toHaveBeenCalledWith(
      'lean_energy',
      'grp-test-303',
      'APPROVE',
      'Zweryfikowano zgodność po analizie abstraktów'
    );
    expect(await screen.findByText(/Decyzja Zapisana!/i)).toBeInTheDocument();
    expect(await screen.findByText(/Approved/i)).toBeInTheDocument();
  });

  it('handles reject click, error state, and retry action with rationale', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-test-404',
          reason: 'Zgodność PMID',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'pmid', value: '12345' }],
          records: [
            { id: 'r1', title: 'Reject Test Paper A', authors: 'A', year: 2021, source: 'PubMed' },
            { id: 'r2', title: 'Reject Test Paper B', authors: 'B', year: 2021, source: 'S2' },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-test-404',
      decision: 'PENDING',
      rationale: null,
    });
    const postSpy = vi
      .spyOn(projectApiService, 'postDuplicateGroupDecision')
      .mockRejectedValueOnce(new Error('Błąd połączenia z serwerem'))
      .mockResolvedValueOnce({
        project_id: 'lean_energy',
        group_id: 'grp-test-404',
        decision: 'REJECT',
        rationale: 'Odrzucono po weryfikacji roku wydania',
      });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Reject Test Paper A/i)).toBeInTheDocument();

    const rationaleInput = screen.getByPlaceholderText(/Wprowadź opcjonalne uzasadnienie decyzji/i);
    fireEvent.change(rationaleInput, { target: { value: 'Odrzucono po weryfikacji roku wydania' } });

    const rejectBtn = screen.getByRole('button', { name: /Odrzuć/i });
    fireEvent.click(rejectBtn);

    expect(await screen.findByText(/Błąd zapisu: Błąd połączenia z serwerem/i)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Ponów/i });
    fireEvent.click(retryBtn);

    expect(await screen.findByText(/Rejected/i)).toBeInTheDocument();
    expect(postSpy).toHaveBeenCalledTimes(2);
  });
});

describe('canonical duplicate merge action', () => {
  const approvedGroup: ApiDuplicateGroupListResponse['groups'][number] = {
    group_id: 'merge-group', reason: 'DOI', records_count: 2, status: 'APPROVED', rationale: 'same study',
    shared_identifiers: [], records: [
      { id: 'a', title: 'A', authors: 'A', year: 2024, source: 'one' },
      { id: 'b', title: 'B', authors: 'B', year: 2024, source: 'two' },
    ],
  };

  it('keeps approval separate and explicitly posts a bodyless merge request', async () => {
    const merge = vi.spyOn(projectApiService, 'mergeDuplicateGroup').mockResolvedValue({
      project_id: 'lean_energy', group_id: 'merge-group', status: 'MERGED', canonical_record_id: 'a',
      merged_publication_ids: ['a', 'b'], merged_at: '2026-08-21T10:00:00Z',
    });
    render(<DuplicateGroupCardPreview group={approvedGroup} index={0} projectId="lean_energy" />);
    expect(screen.getByText('Approved')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Merge duplicates' }));
    expect(await screen.findByText('Merged')).toBeInTheDocument();
    expect(merge).toHaveBeenCalledWith('lean_energy', 'merge-group');
    expect(screen.getByText(/Canonical publication: a/i)).toBeInTheDocument();
  });
});
