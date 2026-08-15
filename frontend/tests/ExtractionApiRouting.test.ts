import { afterEach, describe, expect, it, vi } from 'vitest';
import { extractionApi } from '../src/services/api/extractionApi';

describe('extraction API routing', () => {
  afterEach(() => vi.restoreAllMocks());

  it('queries eligibility through the backend /api/v1 namespace', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        project_id: 'project-1',
        total_publications: 0,
        eligible_count: 0,
        items: [],
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await extractionApi.getExtractionEligibility('project-1', 'reviewer-1');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/projects/project-1/extraction/eligibility?reviewer_id=reviewer-1',
    );
  });
});
