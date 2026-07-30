import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { SearchStrategyPage } from '../src/pages/SearchStrategyPage';
import { projectApiService } from '../src/services/api/projectApi';

vi.mock('../src/context/ProjectContext', () => ({
  useProject: () => ({ activeProject: { id: 'lean_energy' } }),
}));

describe('Search Strategy backend persistence', () => {
  it('loads saved data again after the page is remounted', async () => {
    const get = vi.spyOn(projectApiService, 'getSearchStrategy')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        strategy_id: '10000000-0000-0000-0000-000000000001',
        project_id: 'lean_energy',
        name: 'Persisted after refresh',
        description: null,
        research_questions: ['RQ'],
        concept_groups: [{ group_id: 'g1', name: 'Group', terms: ['term'], operator: 'or' }],
        group_operator: 'and',
        constraints: {
          publication_year_from: null,
          publication_year_to: null,
          languages: [],
          publication_types: [],
          additional_limits: {},
        },
        providers: ['openalex'],
        queries: [{
          query_id: '20000000-0000-0000-0000-000000000001',
          name: 'Query',
          expression: { node_type: 'term', value: 'term' },
          version: 1,
          description: null,
          created_by: null,
          notes: null,
          created_at: '2026-07-30T10:00:00Z',
        }],
        version: 1,
        created_at: '2026-07-30T10:00:00Z',
        updated_at: '2026-07-30T10:00:00Z',
      });

    const first = render(<MemoryRouter><SearchStrategyPage /></MemoryRouter>);
    await screen.findByText(/nie ma jeszcze zapisanej strategii/);
    first.unmount();
    render(<MemoryRouter><SearchStrategyPage /></MemoryRouter>);

    expect(await screen.findByDisplayValue('Group')).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });
});
