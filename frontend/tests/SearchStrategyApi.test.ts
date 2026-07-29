import { afterEach, describe, expect, it, vi } from 'vitest';
import { projectApiService } from '../src/services/api/projectApi';

const strategy = {
  filters: {
    publicationYearFrom: 2020,
    publicationYearTo: 2024,
    languages: ['en'],
    publicationTypes: ['article'],
    fullTextOnly: false,
  },
  providers: ['openalex'],
  conceptGroups: [{ id: 'g1', name: 'Lean', terms: ['Kaizen'] }],
};

describe('Search Strategy frontend-backend contract', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends the editable strategy and maps the backend response', async () => {
    const backendResponse = {
      project_id: 'lean_energy',
      status: 'validated' as const,
      rendered_query: '("Kaizen")',
      providers: ['openalex'],
      publication_year_from: 2020,
      publication_year_to: 2024,
      executed_at: '2026-07-29T15:00:00Z',
      result_count: 1,
      results: [{
        id: 'result-1',
        title: 'Controlled result',
        authors: ['Author One'],
        year: 2021,
        provider: 'openalex' as const,
        source_id: 'W1',
        doi: null,
      }],
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await projectApiService.executeSearchStrategy('lean_energy', strategy);

    expect(result).toEqual(backendResponse);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/projects/lean_energy/search-strategy/executions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          publication_year_from: 2020,
          publication_year_to: 2024,
          providers: ['openalex'],
          concept_groups: [{ id: 'g1', name: 'Lean', terms: ['Kaizen'] }],
        }),
      })
    );
  });

  it('uses a string FastAPI detail as the primary error reason', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Project is unavailable' }), { status: 404 })
    );

    await expect(projectApiService.executeSearchStrategy('lean_energy', strategy))
      .rejects.toThrow('Project is unavailable (HTTP 404)');
  });

  it('formats a Pydantic validation error list without raw objects', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        detail: [
          {
            loc: ['body', 'publication_year_from'],
            msg: 'Input should be greater than or equal to 1000',
            type: 'greater_than_equal',
          },
        ],
      }), { status: 422 })
    );

    await expect(projectApiService.executeSearchStrategy('lean_energy', strategy))
      .rejects.toThrow(
        'Niepoprawne dane strategii: publication_year_from: Input should be greater than or equal to 1000 (HTTP 422)'
      );
  });

  it.each([
    ['non-JSON response', new Response('<html>Error</html>', { status: 500 })],
    ['empty response', new Response(null, { status: 500 })],
    ['unexpected JSON', new Response(JSON.stringify({ error: { code: 12 } }), { status: 500 })],
  ])('uses a safe fallback for %s', async (_caseName, response) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);

    await expect(projectApiService.executeSearchStrategy('lean_energy', strategy))
      .rejects.toThrow('Nie udało się wykonać strategii (HTTP 500)');
  });

  it('maps a network failure to a user-safe message', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(projectApiService.executeSearchStrategy('lean_energy', strategy))
      .rejects.toThrow('Nie udało się połączyć z backendem');
  });

  it('imports exactly the selected search records', async () => {
    const record = {
      id: 'result-1',
      title: 'Selected result',
      authors: ['Author One'],
      year: 2021,
      provider: 'openalex' as const,
      source_id: 'W1',
      doi: null,
    };
    const backendResponse = {
      project_id: 'lean_energy',
      imported_count: 1,
      skipped_count: 0,
      total_requested: 1,
      working_collection_count: 6,
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await projectApiService.importSearchResults(
      'lean_energy',
      [record]
    );

    expect(result).toEqual(backendResponse);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/projects/lean_energy/search-results/imports',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ records: [record] }),
      })
    );
  });
});
