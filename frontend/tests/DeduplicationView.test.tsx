import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { DeduplicationPage } from '../src/pages/DeduplicationPage';
import { projectApiService } from '../src/services/api/projectApi';
import { ApiDuplicateGroupListResponse } from '../src/types';

describe('DeduplicationPage Read-Only API Integration & Review Decisions', () => {
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
          status: 'PENDING',
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
    expect(screen.getByText(/Pending/i)).toBeInTheDocument();
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

  it('handles approve click, saving state, success state and badge update', async () => {
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
    const postSpy = vi.spyOn(projectApiService, 'postDuplicateGroupDecision').mockResolvedValue({
      project_id: 'lean_energy',
      group_id: 'grp-test-303',
      decision: 'APPROVE',
    });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Test Paper A/i)).toBeInTheDocument();

    const approveBtn = screen.getByRole('button', { name: /Approve/i });
    expect(approveBtn).not.toBeDisabled();

    fireEvent.click(approveBtn);

    expect(postSpy).toHaveBeenCalledWith('lean_energy', 'grp-test-303', 'APPROVE');
    expect(await screen.findByText(/Approved/i)).toBeInTheDocument();
    expect(screen.getByText(/Saved/i)).toBeInTheDocument();
  });

  it('handles reject click, error state, and retry action', async () => {
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
    const postSpy = vi
      .spyOn(projectApiService, 'postDuplicateGroupDecision')
      .mockRejectedValueOnce(new Error('Błąd połączenia z serwerem'))
      .mockResolvedValueOnce({ project_id: 'lean_energy', group_id: 'grp-test-404', decision: 'REJECT' });

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dedup']}>
          <DeduplicationPage />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Reject Test Paper A/i)).toBeInTheDocument();

    const rejectBtn = screen.getByRole('button', { name: /Reject/i });
    fireEvent.click(rejectBtn);

    expect(await screen.findByText(/Error: Błąd połączenia z serwerem/i)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    expect(retryBtn).toBeInTheDocument();

    fireEvent.click(retryBtn);

    expect(await screen.findByText(/Rejected/i)).toBeInTheDocument();
    expect(postSpy).toHaveBeenCalledTimes(2);
  });
});
