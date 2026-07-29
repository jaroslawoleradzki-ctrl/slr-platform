import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { DeduplicationPage } from '../src/pages/DeduplicationPage';
import { projectApiService } from '../src/services/api/projectApi';
import { ApiDuplicateGroupListResponse } from '../src/types';

describe('DeduplicationPage Read-Only API Integration', () => {
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

  it('renders duplicate candidate groups and shared identifiers on API success', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-test-101',
          reason: 'Zgodność identyfikatorów (DOI: 10.1016/j.jclepro.2021.102834)',
          records_count: 2,
          shared_identifiers: [{ identifier_type: 'doi', value: '10.1016/j.jclepro.2021.102834' }],
          records: [
            {
              id: 'rec-001',
              title: 'Lean Energy Management in Automotive Manufacturing',
              authors: 'Smith, J., Kowalski, P.',
              year: 2021,
              source: 'OpenAlex',
              doi: '10.1016/j.jclepro.2021.102834',
            },
            {
              id: 'rec-002',
              title: 'Lean Energy Management in Auto Production',
              authors: 'Smith, John, Kowalski, Piotr',
              year: 2021,
              source: 'Crossref',
              doi: '10.1016/j.jclepro.2021.102834',
            },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Lean Energy Management in Automotive Manufacturing/i)).toBeInTheDocument();
    expect(screen.getAllByText(/10.1016\/j.jclepro.2021.102834/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Duplicate Groups Awaiting Human Review \(1\)/i)).toBeInTheDocument();
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

  it('renders error alert and retry button on API failure without mock fallback', async () => {
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockRejectedValue(new Error('Błąd serwera API backend (HTTP 500)'));

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Błąd połączenia z API Deduplikacji/i)).toBeInTheDocument();
    expect(screen.getByText(/Błąd serwera API backend \(HTTP 500\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/Candidate Duplicate Group #1/i)).not.toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Spróbuj ponownie/i });
    expect(retryBtn).toBeInTheDocument();
  });

  it('displays disabled action buttons with Phase 6.4 notice', async () => {
    const mockResponse: ApiDuplicateGroupListResponse = {
      project_id: 'lean_energy',
      total_groups_count: 1,
      groups: [
        {
          group_id: 'grp-test-202',
          reason: 'Zgodność identyfikatora PMID',
          records_count: 2,
          shared_identifiers: [{ identifier_type: 'pmid', value: '31204912' }],
          records: [
            { id: 'r1', title: 'Kaizen electricity reduction', authors: 'Müller, H.', year: 2019, source: 'Semantic Scholar', pmid: '31204912' },
            { id: 'r2', title: 'Kaizen electricity reduction', authors: 'Muller, H.', year: 2019, source: 'RIS file', pmid: '31204912' },
          ],
        },
      ],
    };

    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(mockResponse);

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Zatwierdź \(Podgląd API\)/i)).toBeInTheDocument();
    const approveBtn = screen.getByRole('button', { name: /Zatwierdź \(Podgląd API\)/i });
    expect(approveBtn).toBeDisabled();

    expect(screen.getByText(/Tryb Podglądu \(Read-Only Preview\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Phase 6.4/i)).toBeInTheDocument();
  });
});
