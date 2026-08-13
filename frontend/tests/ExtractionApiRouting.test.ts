import { afterEach, describe, expect, it, vi } from 'vitest';
import { extractionApi } from '../src/services/api/extractionApi';

describe('extraction API namespace', () => {
  afterEach(() => vi.restoreAllMocks());

  it('calls extraction endpoints under /api/v1/projects', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ project_id: 'project-1', template_id: 't', template_version: '1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await extractionApi.getProjectConfiguration('project-1');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-1/extraction/configuration');
  });
});
