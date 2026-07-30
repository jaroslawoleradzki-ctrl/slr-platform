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
});
