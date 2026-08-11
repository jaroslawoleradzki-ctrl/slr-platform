import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ScreeningAuditPage } from '../src/pages/ScreeningAuditPage';
import { screeningApi } from '../src/services/api/screeningApi';

describe('Screening audit page', () => {
  beforeEach(() => {
    localStorage.setItem('slr_screening_reviewer_id', 'alice');
    vi.restoreAllMocks();
    vi.spyOn(screeningApi, 'getReport').mockResolvedValue({
      project_id: 'project-a', reviewer_id: 'alice', ready: true,
      readiness_status: 'ready', working_collection_count: 2,
      canonical_records_count: 2,
      title_abstract: { total_eligible: 2, screened: 1, remaining: 1, included: 1, excluded: 0, uncertain: 0 },
      full_text: { total_eligible: 1, screened: 0, remaining: 1, included: 0, excluded: 0, uncertain: 0 },
      transitions: { canonical_input: 2, title_abstract_screened: 1, title_abstract_included: 1, full_text_eligible: 1, full_text_screened: 0, full_text_included: 0 },
      full_text_exclusion_reasons: [],
    });
    vi.spyOn(screeningApi, 'getAudit').mockResolvedValue({ total: 0, offset: 0, limit: 25, items: [] });
  });

  it('renders reviewer-scoped progress and the empty audit state', async () => {
    render(<MemoryRouter initialEntries={['/projects/project-a/screen/audit']}><Routes><Route path="/projects/:projectId/screen/audit" element={<ScreeningAuditPage />} /></Routes></MemoryRouter>);

    expect(await screen.findByText('Podsumowanie i historia')).toBeInTheDocument();
    expect(screen.getByText('1 / 2 ocenionych')).toBeInTheDocument();
    expect(screen.getByText('Brak historii')).toBeInTheDocument();
  });
});
