import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider } from '../src/context/ProjectContext';
import { NormalizationPage } from '../src/pages/NormalizationPage';
import { projectApiService } from '../src/services/api/projectApi';
import { NormalizationResponse } from '../src/types';

describe('Normalization page', () => {
  afterEach(() => vi.restoreAllMocks());

  const renderPage = () => render(
    <ProjectProvider>
      <NormalizationPage />
    </ProjectProvider>,
  );

  it('does not show demo counts before normalization and loads real summary after run', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    let executed = false;
    const result: NormalizationResponse = {
      run_id: 'run-1',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 5,
      clean_records: 5,
      warnings_count: 0,
      errors_count: 0,
      rules_applied: ['DOI normalized'],
      audit_trail: ['DOI normalized: 2'],
      started_at: '2026-07-30T11:59:59Z',
      completed_at: '2026-07-30T12:00:00Z',
      executed_at: '2026-07-30T12:00:00Z',
    };
    vi.spyOn(projectApiService, 'getNormalization').mockImplementation(async () => executed ? result : null);
    vi.spyOn(projectApiService, 'runNormalization').mockImplementation(async () => {
      executed = true;
      return result;
    });
    renderPage();

    expect(screen.queryByText('2,105')).not.toBeInTheDocument();
    expect(screen.getByText('Normalizacja nie została jeszcze uruchomiona dla tego projektu.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Uruchom normalizację' }));
    await waitFor(() => expect(screen.getByText('DOI normalized: 2')).toBeInTheDocument());
    expect(screen.getAllByText('5')).toHaveLength(2);
  });

  it('shows an empty neutral state when no execution exists', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    renderPage();
    await waitFor(() => expect(screen.getByText('Normalizacja nie została jeszcze uruchomiona dla tego projektu.')).toBeInTheDocument());
    expect(screen.queryByText('63')).not.toBeInTheDocument();
  });

  it('renders a persisted result returned by GET on entry', async () => {
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue({
      run_id: 'persisted-run',
      project_id: 'lean_energy',
      status: 'completed',
      processed_records: 7,
      clean_records: 6,
      warnings_count: 1,
      errors_count: 0,
      rules_applied: ['DOI normalized'],
      audit_trail: ['DOI normalized: 1'],
      started_at: '2026-07-30T11:59:59Z',
      completed_at: '2026-07-30T12:00:00Z',
      executed_at: '2026-07-30T12:00:00Z',
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('DOI normalized: 1')).toBeInTheDocument());
    expect(screen.getByText('7')).toBeInTheDocument();
  });
});
