import { API_BASE_URL } from '../../config/api';

export class ExportApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ExportApiError';
  }
}

async function handleBlobResponse(res: Response, fallbackMessage: string): Promise<Blob> {
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ExportApiError(res.status, errData.detail || fallbackMessage);
  }
  return res.blob();
}

export const exportApi = {
  async exportBibtex(projectId: string): Promise<Blob> {
    const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/exports/bibtex`);
    return handleBlobResponse(res, 'Failed to export BibTeX dataset');
  },

  async exportRis(projectId: string): Promise<Blob> {
    const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/exports/ris`);
    return handleBlobResponse(res, 'Failed to export RIS dataset');
  },

  async exportXlsx(projectId: string, reviewerId?: string): Promise<Blob> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/exports/xlsx${query}`);
    return handleBlobResponse(res, 'Failed to export XLSX research matrix');
  },

  async exportPrismaSvg(projectId: string, reviewerId?: string): Promise<Blob> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/prisma/flow.svg${query}`);
    return handleBlobResponse(res, 'Failed to export PRISMA SVG diagram');
  },

  async exportPrismaPdf(projectId: string, reviewerId?: string): Promise<Blob> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/prisma/flow.pdf${query}`);
    return handleBlobResponse(res, 'Failed to export PRISMA PDF diagram');
  },
};
