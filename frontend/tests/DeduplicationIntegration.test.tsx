import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { DeduplicationPage } from '../src/pages/DeduplicationPage';
import { projectApiService } from '../src/services/api/projectApi';
import { ApiDuplicateGroupListResponse } from '../src/types';

describe('Deduplication Page Full Integration Workflow & Regression Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('executes full end-to-end reviewer workflow: load -> inspect -> approve with rationale -> update to reject -> verify persistence', async () => {
    const groupListResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-flow-999',
          reason: 'Zgodność identyfikatorów (DOI: 10.1016/j.energy.2025.1001)',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1016/j.energy.2025.1001' }],
          records: [
            {
              id: 'rec-a',
              title: 'Advanced SLR Workflow Architecture',
              authors: 'Kowalski, P., Smith, J.',
              year: 2025,
              source: 'OpenAlex',
              venue: 'IEEE Transactions on Software Engineering',
              doi: '10.1016/j.energy.2025.1001',
              provenance: [
                { source: 'OpenAlex', source_record_id: 'W999001', retrieved_at: '2026-07-01T12:00:00Z' },
              ],
            },
            {
              id: 'rec-b',
              title: 'Advanced SLR Workflow Architecture',
              authors: 'Kowalski, Piotr, Smith, John',
              year: 2025,
              source: 'Crossref',
              venue: 'IEEE Transactions on Software Engineering',
              doi: '10.1016/j.energy.2025.1001',
              provenance: [
                { source: 'Crossref', source_record_id: '10.1016/j.energy.2025.1001', retrieved_at: '2026-07-01T12:00:00Z' },
              ],
            },
          ],
        },
      ],
    };

    // 1. Mock API calls
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(groupListResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-flow-999',
      decision: 'PENDING',
      rationale: null,
    });

    const postDecisionSpy = vi
      .spyOn(projectApiService, 'postDuplicateGroupDecision')
      .mockResolvedValueOnce({
        project_id: 'lean_energy',
        group_id: 'grp-flow-999',
        decision: 'APPROVE',
        rationale: 'Zatwierdzono na podstawie zgodności abstraktów',
      })
      .mockResolvedValueOnce({
        project_id: 'lean_energy',
        group_id: 'grp-flow-999',
        decision: 'REJECT',
        rationale: 'Zmieniono decyzję po dodatkowej weryfikacji autorów',
      });

    // 2. Render Page
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    // 3. Verify loading state then initial group render
    expect(screen.getByText(/Pobieranie grup kandydatów z API backendu/i)).toBeInTheDocument();
    expect(await screen.findByText(/Pobrano 1 grup z API backendu/i)).toBeInTheDocument();
    expect(screen.getByText(/Porównanie Publikacji Obok Siebie/i)).toBeInTheDocument();

    // 4. Verify field comparison badges
    expect(screen.getAllByText(/Zgodne \(Identical\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Różne \(Different\)/i).length).toBeGreaterThan(0);

    // 5. Test toggle aria-expanded
    const toggleBtn = screen.getByRole('button', { name: /Zwiń/i });
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText(/Porównanie Publikacji Obok Siebie/i)).not.toBeInTheDocument();

    // Re-expand
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText(/Porównanie Publikacji Obok Siebie/i)).toBeInTheDocument();

    // 6. Enter rationale and approve
    const rationaleInput = screen.getByPlaceholderText(/Wprowadź opcjonalne uzasadnienie decyzji/i);
    fireEvent.change(rationaleInput, { target: { value: 'Zatwierdzono na podstawie zgodności abstraktów' } });

    const approveBtn = screen.getByRole('button', { name: /Zatwierdź/i });
    fireEvent.click(approveBtn);

    expect(postDecisionSpy).toHaveBeenNthCalledWith(
      1,
      'lean_energy',
      'grp-flow-999',
      'APPROVE',
      'Zatwierdzono na podstawie zgodności abstraktów'
    );
    expect(await screen.findByText(/Decyzja Zapisana!/i)).toBeInTheDocument();
    expect(screen.getByText(/Approved/i)).toBeInTheDocument();

    // 7. Change rationale and reject
    fireEvent.change(rationaleInput, { target: { value: 'Zmieniono decyzję po dodatkowej weryfikacji autorów' } });
    const rejectBtn = screen.getByRole('button', { name: /Odrzuć/i });
    fireEvent.click(rejectBtn);

    expect(postDecisionSpy).toHaveBeenNthCalledWith(
      2,
      'lean_energy',
      'grp-flow-999',
      'REJECT',
      'Zmieniono decyzję po dodatkowej weryfikacji autorów'
    );
    expect(await screen.findByText(/Rejected/i)).toBeInTheDocument();
  });

  it('handles network failure during initial fetch and successful recovery via retry button', async () => {
    const mockSuccessResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-retry-1',
          reason: 'Zgodność DOI',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1000/retry' }],
          records: [
            { id: 'r1', title: 'Retry Paper 1', authors: 'Author 1', year: 2024, source: 'OpenAlex' },
            { id: 'r2', title: 'Retry Paper 2', authors: 'Author 2', year: 2024, source: 'Crossref' },
          ],
        },
      ],
    };

    const getGroupsSpy = vi
      .spyOn(projectApiService, 'getDuplicateGroups')
      .mockRejectedValueOnce(new Error('Serwer niedostępny (500)'))
      .mockResolvedValueOnce(mockSuccessResponse);

    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-retry-1',
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

    expect(await screen.findByText(/Serwer niedostępny \(500\)/i)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Spróbuj ponownie/i });
    fireEvent.click(retryBtn);

    expect(await screen.findByText(/Pobrano 1 grup z API backendu/i)).toBeInTheDocument();
    expect(getGroupsSpy).toHaveBeenCalledTimes(2);
  });

  it('handles null venue, empty provenance, and missing optional identifiers cleanly', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-nulls-10',
          reason: 'Identical strong identifier match',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [],
          records: [
            {
              id: 'rec-null-1',
              title: 'Null Fields Publication A',
              authors: 'Smith, J.',
              year: null,
              source: 'Manual Import',
              venue: null,
              doi: null,
              pmid: null,
              openalex_id: null,
              provenance: [],
            },
            {
              id: 'rec-null-2',
              title: 'Null Fields Publication B',
              authors: 'Smith, J.',
              year: null,
              source: 'Manual Import',
              venue: null,
              doi: null,
              pmid: null,
              openalex_id: null,
              provenance: [],
            },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-nulls-10',
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

    expect(await screen.findByText(/Pobrano 1 grup z API backendu/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Brak danych \(Missing\)/i).length).toBeGreaterThan(0);
  });

  it('computes field states deterministically across repeated renders', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-det-555',
          reason: 'Identical strong identifier match',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1000/det' }],
          records: [
            { id: 'r1', title: 'Deterministic Title', authors: 'Author X', year: 2023, source: 'PubMed', doi: '10.1000/det' },
            { id: 'r2', title: 'Deterministic Title', authors: 'Author Y', year: 2023, source: 'Crossref', doi: '10.1000/det' },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'getDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-det-555',
      decision: 'PENDING',
      rationale: null,
    });

    const { rerender } = render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Pobrano 1 grup z API backendu/i)).toBeInTheDocument();
    const initialMatchesCount = screen.getAllByText(/Zgodne \(Identical\)/i).length;

    // Rerender component
    rerender(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(screen.getAllByText(/Zgodne \(Identical\)/i).length).toBe(initialMatchesCount);
  });

  it('performs exactly one GET duplicate-groups call and ZERO per-card GET decision calls on page load', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 2,
      groups: [
        {
          group_id: 'grp-no-n1-1',
          reason: 'Zgodność DOI',
          records_count: 2,
          status: 'PENDING',
          rationale: null,
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1000/one' }],
          records: [
            { id: 'r1', title: 'Paper 1A', authors: 'A', year: 2021, source: 'S1' },
            { id: 'r2', title: 'Paper 1B', authors: 'B', year: 2021, source: 'S2' },
          ],
        },
        {
          group_id: 'grp-no-n1-2',
          reason: 'Zgodność PMID',
          records_count: 2,
          status: 'APPROVE',
          rationale: 'Pre-approved rationale',
          shared_identifiers: [{ identifier_type: 'pmid', value: '7788' }],
          records: [
            { id: 'r3', title: 'Paper 2A', authors: 'C', year: 2022, source: 'S3' },
            { id: 'r4', title: 'Paper 2B', authors: 'D', year: 2022, source: 'S4' },
          ],
        },
      ],
    };

    const getGroupsSpy = vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    const getDecisionSpy = vi.spyOn(projectApiService, 'getDuplicateGroupDecision');

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/grp-no-n1-1/i)).toBeInTheDocument();
    expect(screen.getByText(/grp-no-n1-2/i)).toBeInTheDocument();

    // 1 group call made, 0 decision calls made for cards
    expect(getGroupsSpy).toHaveBeenCalledTimes(1);
    expect(getDecisionSpy).toHaveBeenCalledTimes(0);

    // Initial statuses rendered from group.status
    expect(screen.getByText(/Pending Review/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Approved/i).length).toBeGreaterThan(0);
  });

  it('updates summary metrics dynamically when a decision is recorded', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 2,
      groups: [
        {
          group_id: 'grp-summary-1',
          reason: 'Zgodność DOI',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1000/s1' }],
          records: [
            { id: 'r1', title: 'Summary Test Paper 1', authors: 'A', year: 2021, source: 'S1' },
            { id: 'r2', title: 'Summary Test Paper 2', authors: 'B', year: 2021, source: 'S2' },
          ],
        },
        {
          group_id: 'grp-summary-2',
          reason: 'Zgodność PMID',
          records_count: 2,
          status: 'PENDING',
          shared_identifiers: [{ identifier_type: 'pmid', value: '9900' }],
          records: [
            { id: 'r3', title: 'Summary Test Paper 3', authors: 'C', year: 2022, source: 'S3' },
            { id: 'r4', title: 'Summary Test Paper 4', authors: 'D', year: 2022, source: 'S4' },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);
    vi.spyOn(projectApiService, 'postDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-summary-1',
      decision: 'APPROVE',
      rationale: 'Approved via GUI test',
    });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Summary Test Paper 1/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Uruchom deduplikację/i }));

    // Verify initial summary counts: Total: 2, Pending: 2, Approve: 0, Reject: 0
    expect(await screen.findByText(/Oczekujące grupy duplikatów \(2\)/i)).toBeInTheDocument();

    // Click Approve on first group
    const approveBtns = screen.getAllByRole('button', { name: /Zatwierdź/i });
    fireEvent.click(approveBtns[0]);

    // Verify summary counts update immediately: Pending becomes 1
    expect(await screen.findByText(/Oczekujące grupy duplikatów \(1\)/i)).toBeInTheDocument();
  });
});
