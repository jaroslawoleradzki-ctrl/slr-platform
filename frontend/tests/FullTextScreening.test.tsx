import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { FullTextScreeningPage } from '../src/pages/FullTextScreeningPage';
import { screeningApi } from '../src/services/api/screeningApi';

const record = { publication_id: 'paper-a', title: 'Full paper', abstract: 'Full abstract', authors: [], publication_year: 2024, publication_date: null, identifiers: [], doi: null, venue: null, publisher: null, document_type: null, language: 'en', keywords: [], urls: [], open_access: true, status: 'unscreened' as const, latest_decision: null, automatic_assessments: [], availability: { status: 'unknown' as const, external_url: null, notes: null } };
const criterion = { criterion_id: 'criterion-a', project_id: 'project-a', name: 'Population', description: null, criterion_type: 'inclusion' as const, screening_stage: 'full_text' as const, display_order: 0, is_active: true, is_required: true };

describe('Full Text Screening GUI', () => {
  beforeEach(() => {
    localStorage.setItem('slr_screening_reviewer_id', 'alice'); vi.restoreAllMocks();
    vi.spyOn(screeningApi, 'getFullTextOverview').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'alice', ready: true, readiness_status: 'ready', eligible_records_count: 1, working_collection_count: 1, canonical_records_count: 1, unresolved_duplicate_groups: 0, criteria: [criterion], progress: { total: 1, unscreened: 1, included: 0, excluded: 0, uncertain: 0, completed: 0 } });
    vi.spyOn(screeningApi, 'listFullTextRecords').mockResolvedValue({ project_id: 'project-a', reviewer_id: 'alice', ready: true, status_filter: 'unscreened', total: 1, offset: 0, limit: 50, items: [record] });
    vi.spyOn(screeningApi, 'listDecisionHistory').mockResolvedValue({ items: [], total: 0 });
  });
  it('renders eligible record, availability and only allows a valid structured exclusion reason', async () => {
    render(<MemoryRouter initialEntries={['/projects/project-a/screen/full-text']}><Routes><Route path="/projects/:projectId/screen/full-text" element={<FullTextScreeningPage />} /><Route path="/projects/:projectId/screen/full-text/:publicationId" element={<FullTextScreeningPage />} /></Routes></MemoryRouter>);
    await screen.findByText('Full paper');
    expect(screen.getByText('Dostępność pełnego tekstu')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Wyklucz' }));
    expect(screen.getByText('Najpierw oceń kryteria, aby wskazać uzasadniony powód.')).toBeInTheDocument();
  });
});
