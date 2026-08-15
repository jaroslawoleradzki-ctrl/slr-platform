import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExtractionApiError, extractionApi } from '../src/services/api/extractionApi';

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
      '/api/v1/projects/project-1/extraction/eligibility?reviewer_id=reviewer-1',
    );
  });

  it('surfaces a missing extraction record so the eligible-candidate UI can handle it explicitly', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Extraction record was not found.' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(
      extractionApi.getExtractionRecord('project-1', 'publication-1'),
    ).rejects.toEqual(expect.objectContaining<Partial<ExtractionApiError>>({
      statusCode: 404,
      message: 'Extraction record was not found.',
    }));
  });

  it('lists template versions and saves project configuration through /api/v1', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('[]', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        project_id: 'project-1',
        template_id: 'generic-clinical',
        template_version: '2.1.0',
        configured_at: '2026-08-15T00:00:00Z',
        updated_at: '2026-08-15T00:00:00Z',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));

    await extractionApi.listExtractionTemplates();
    await extractionApi.setProjectConfiguration('project-1', 'generic-clinical', '2.1.0');

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/v1/extraction-templates');
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/projects/project-1/extraction/configuration',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ template_id: 'generic-clinical', template_version: '2.1.0' }),
      }),
    );
  });
});
