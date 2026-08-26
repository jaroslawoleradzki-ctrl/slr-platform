import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FetchAllProgressPanel } from '../src/components/search/FetchAllProgressPanel';
import { FetchAllProviderProgress, FetchAllStatusResult } from '../src/types';

const provider = (
  id: string,
  status: FetchAllProviderProgress['status'],
  overrides: Partial<FetchAllProviderProgress> = {}
): FetchAllProviderProgress => ({
  provider: id,
  status,
  fetched_count: 100,
  kept_count: 90,
  pages_fetched: 3,
  total_reported: 250,
  limit_reached: false,
  message: null,
  ...overrides,
});

const buildJob = (
  jobStatus: FetchAllStatusResult['status'],
  providers: FetchAllProviderProgress[]
): FetchAllStatusResult => ({
  job_id: 'job-1',
  project_id: 'p1',
  status: jobStatus,
  started_at: '2026-08-26T10:00:00Z',
  finished_at: jobStatus === 'running' ? null : '2026-08-26T10:05:00Z',
  providers,
  fetched_total: 300,
  kept_total: 270,
  message: null,
  result: null,
});

describe('FetchAllProgressPanel — provider status rows', () => {
  it('renders all six provider states with distinct labels', () => {
    const finishedJob = buildJob('completed', [
      provider('openalex', 'complete'),
      provider('crossref', 'partial'),
      provider('semantic_scholar', 'failed'),
    ]);
    const mixedJob = buildJob('cancelled', [
      provider('openalex', 'pending'),
      provider('crossref', 'running'),
      provider('semantic_scholar', 'cancelled'),
    ]);

    const { rerender } = render(<FetchAllProgressPanel progress={finishedJob} starting={false} />);
    expect(screen.getByTestId('fetch-all-provider-row-openalex')).toHaveTextContent('Zakończono');
    expect(screen.getByTestId('fetch-all-provider-row-crossref')).toHaveTextContent('Zakończono częściowo');
    expect(screen.getByTestId('fetch-all-provider-row-semantic_scholar')).toHaveTextContent('Błąd');

    rerender(<FetchAllProgressPanel key="second" progress={mixedJob} starting={false} />);
    expect(screen.getByTestId('fetch-all-provider-row-openalex')).toHaveTextContent('Oczekuje…');
    expect(screen.getByTestId('fetch-all-provider-row-crossref')).toHaveTextContent('Pobieranie…');
    expect(screen.getByTestId('fetch-all-provider-row-semantic_scholar')).toHaveTextContent('Anulowano');
  });

  it('shows reported totals with a tilde and a dash fallback, plus limit notes', () => {
    const job = buildJob('completed', [
      provider('openalex', 'partial', { total_reported: 12345, limit_reached: true }),
      provider('crossref', 'failed', { total_reported: null, message: 'HTTP 500' }),
    ]);
    render(<FetchAllProgressPanel progress={job} starting={false} />);

    const openalexRow = screen.getByTestId('fetch-all-provider-row-openalex');
    expect(openalexRow).toHaveTextContent(/~12\s*345/u);
    expect(openalexRow).toHaveTextContent('osiągnięto limit możliwy do pobrania z API');

    const crossrefRow = screen.getByTestId('fetch-all-provider-row-crossref');
    expect(crossrefRow).toHaveTextContent('–');
    expect(
      screen.getByText(/Niekompletne dane: OpenAlex — częściowo.*Crossref — błąd \(HTTP 500\)/u)
    ).toBeInTheDocument();
  });

  it('offers cancellation only while running and keeps totals visible afterwards', () => {
    const onCancel = vi.fn();
    const { rerender } = render(
      <FetchAllProgressPanel
        progress={buildJob('running', [provider('openalex', 'complete')])}
        starting={false}
        onCancel={onCancel}
      />
    );
    expect(screen.getByRole('button', { name: 'Anuluj pobieranie' })).toBeInTheDocument();

    rerender(
      <FetchAllProgressPanel
        key="finished"
        progress={buildJob('cancelled', [provider('openalex', 'cancelled')])}
        starting={false}
        onCancel={onCancel}
      />
    );
    expect(screen.queryByRole('button', { name: 'Anuluj pobieranie' })).not.toBeInTheDocument();
    expect(screen.getByText(/Łącznie pobrano:\s*300/u)).toBeInTheDocument();
    expect(screen.getByText(/Po lokalnych filtrach:\s*270/u)).toBeInTheDocument();
  });

  it('renders a starting placeholder before any job payload arrives', () => {
    render(<FetchAllProgressPanel progress={null} starting />);
    expect(screen.getByRole('status')).toHaveTextContent('Rozpoczynanie pobierania');
  });
});
