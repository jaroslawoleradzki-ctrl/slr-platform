import { afterEach, describe, expect, it, vi } from 'vitest';
import { projectApiService } from '../src/services/api/projectApi';

describe('duplicate groups API first-load errors', () => {
  afterEach(() => vi.restoreAllMocks());

  it('returns the backend response on the first successful GET', async () => {
    const result = { project_id: 'project-a', total_groups_count: 0, groups: [] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(result), { status: 200 }),
    );

    await expect(projectApiService.getDuplicateGroups('project-a')).resolves.toEqual(result);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/projects/project-a/duplicate-groups',
      { headers: { Accept: 'application/json' } },
    );
  });

  it('keeps an HTTP 5xx response distinct from a network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{"detail":"database unavailable"}', { status: 503 }),
    );
    await expect(projectApiService.getDuplicateGroups('project-a'))
      .rejects.toThrow('HTTP 503');

    vi.restoreAllMocks();
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(projectApiService.getDuplicateGroups('project-b'))
      .rejects.toThrow(TypeError);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/projects/project-b/duplicate-groups',
      { headers: { Accept: 'application/json' } },
    );
  });
});
