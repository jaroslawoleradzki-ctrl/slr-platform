import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { DeduplicationPage } from '../src/pages/DeduplicationPage';
import { projectApiService } from '../src/services/api/projectApi';
import { ApiDuplicateGroupListResponse } from '../src/types';

describe('DeduplicationPage Phase 6.5 — Duplicate Comparison & Review UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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

    expect(screen.getByText(/Pobieranie grup kandydatów z API backendu/i)).toBeInTheDocument();
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
