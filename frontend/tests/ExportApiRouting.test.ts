import { afterEach, describe, expect, it, vi } from 'vitest';
import { exportApi, ExportApiError } from '../src/services/api/exportApi';
import { extractionApi } from '../src/services/api/extractionApi';

describe('Stage 9 Export API routing and backend contract boundary', () => {
  afterEach(() => vi.restoreAllMocks());

  it('routes exportBibtex to GET /api/v1/projects/:projectId/exports/bibtex', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('@article{test, title={Test}}', {
        status: 200,
        headers: { 'Content-Type': 'application/x-bibtex' },
      }),
    );

    const blob = await exportApi.exportBibtex('project-123');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-123/exports/bibtex');
    expect(blob).toBeInstanceOf(Blob);
  });

  it('routes exportRis to GET /api/v1/projects/:projectId/exports/ris', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('TY  - JOUR\nTI  - Test\nER  - \n', {
        status: 200,
        headers: { 'Content-Type': 'application/x-research-info-systems' },
      }),
    );

    const blob = await exportApi.exportRis('project-123');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-123/exports/ris');
    expect(blob).toBeInstanceOf(Blob);
  });

  it('routes exportXlsx to GET /api/v1/projects/:projectId/exports/xlsx with reviewer_id query', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
        status: 200,
        headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
      }),
    );

    const blob = await exportApi.exportXlsx('project-123', 'reviewer-a');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-123/exports/xlsx?reviewer_id=reviewer-a');
    expect(blob).toBeInstanceOf(Blob);
  });

  it('routes exportPrismaSvg to GET /api/v1/projects/:projectId/prisma/flow.svg with reviewer_id query', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('<svg xmlns="http://www.w3.org/2000/svg"></svg>', {
        status: 200,
        headers: { 'Content-Type': 'image/svg+xml' },
      }),
    );

    const blob = await exportApi.exportPrismaSvg('project-123', 'reviewer-a');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-123/prisma/flow.svg?reviewer_id=reviewer-a');
    expect(blob).toBeInstanceOf(Blob);
  });

  it('routes exportPrismaPdf to GET /api/v1/projects/:projectId/prisma/flow.pdf with reviewer_id query', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('%PDF-1.4', {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      }),
    );

    const blob = await exportApi.exportPrismaPdf('project-123', 'reviewer-a');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-123/prisma/flow.pdf?reviewer_id=reviewer-a');
    expect(blob).toBeInstanceOf(Blob);
  });

  it('routes extractionApi.exportDataset for CSV to GET /api/v1/projects/:projectId/extraction/export', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('project_id,publication_id\n123,456', {
        status: 200,
        headers: { 'Content-Type': 'text/csv' },
      }),
    );

    const blob = await extractionApi.exportDataset('project-123', 'csv', 'publications', 'reviewer-a');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/projects/project-123/extraction/export?format=csv&dataset=publications&reviewer_id=reviewer-a',
    );
    expect(blob).toBeInstanceOf(Blob);
  });

  it('routes extractionApi.exportDataset for JSON to GET /api/v1/projects/:projectId/extraction/export', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('[]', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const blob = await extractionApi.exportDataset('project-123', 'json', 'publications', 'reviewer-a');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/projects/project-123/extraction/export?format=json&dataset=publications&reviewer_id=reviewer-a',
    );
    expect(blob).toBeInstanceOf(Blob);
  });

  it('surfaces backend error details in ExportApiError on failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Project not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(exportApi.exportBibtex('missing-proj')).rejects.toEqual(
      expect.objectContaining<Partial<ExportApiError>>({
        status: 404,
        message: 'Project not found',
      }),
    );
  });
});
