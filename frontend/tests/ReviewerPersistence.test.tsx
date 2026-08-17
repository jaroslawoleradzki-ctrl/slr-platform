import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QualityAssessmentPage } from '../src/pages/QualityAssessmentPage';
import { qualityAssessmentApi } from '../src/services/api/qualityAssessmentApi';
import { REVIEWER_IDENTITY_STORAGE_KEY } from '../src/hooks/useReviewerIdentity';

const STORAGE_KEY = REVIEWER_IDENTITY_STORAGE_KEY;
const LEGACY_DUPLICATE_KEY = 'slr_qa_reviewer_legacy';

const mockTool = {
  tool_id: 'casp',
  name: 'CASP Tool',
  description: 'CASP Appraisal Tools',
  is_active: true,
  templates: [
    {
      template_id: 'tmpl-v1',
      tool_id: 'casp',
      template_key: 'cohort',
      name: 'CASP Cohort v1',
      version: 1,
      description: 'Cohort study checklist v1',
      is_active: true,
      criteria: [
        {
          criterion_id: 'crit-1',
          template_id: 'tmpl-v1',
          display_order: 1,
          question: 'Did the study address a clearly focused issue?',
          guidance: 'Look for population, risk factor, outcome',
          is_required: true,
        },
      ],
    },
  ],
};

const mockPubRecord = {
  record_id: 'pub-100',
  title: 'Lean Energy Effectiveness Study',
  authors: [{ display_name: 'Dr. Alice Smith' }],
  publication_year: 2024,
  venue: { name: 'Journal of Clean Energy' },
  doi: '10.1016/j.clean.2024.01.001',
  abstract: 'Comprehensive study of lean energy frameworks in industrial facilities.',
  urls: ['https://doi.org/10.1016/j.clean.2024.01.001'],
};

const mockDetailReady = {
  project_id: 'proj-1',
  publication: mockPubRecord,
  reviewer_id: 'jarek',
  is_currently_eligible: true,
  template: mockTool.templates[0],
  latest_assessment: null,
  history: [],
};

const renderPage = (initialPath = '/projects/proj-1/quality-assessment') =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
        <Route
          path="/projects/:projectId/quality-assessment/:publicationId"
          element={<QualityAssessmentPage />}
        />
      </Routes>
    </MemoryRouter>
  );

const installApiMocks = () => {
  vi.spyOn(qualityAssessmentApi, 'getTools').mockResolvedValue([mockTool]);
  vi.spyOn(qualityAssessmentApi, 'getConfiguration').mockResolvedValue({
    project_id: 'proj-1',
    tool_id: 'casp',
    template_id: 'tmpl-v1',
    template_key: 'cohort',
    template_name: 'CASP Cohort v1',
    version: 1,
    configured_at: '2026-08-11T00:00:00Z',
  });
  vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValue({
    readiness: 'ready',
    tool_id: 'casp',
    template_id: 'tmpl-v1',
    template_version: 1,
    total_eligible: 1,
    total_assessed: 0,
    total_remaining: 1,
  });
  vi.spyOn(qualityAssessmentApi, 'listRecords').mockResolvedValue({
    items: [{ publication: mockPubRecord, has_assessment: false, latest_assessment: null }],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
  });
  vi.spyOn(qualityAssessmentApi, 'getRecordDetail').mockResolvedValue(mockDetailReady);
  vi.spyOn(qualityAssessmentApi, 'saveAssessment').mockResolvedValue({
    assessment_id: 'ass-new',
    project_id: 'proj-1',
    publication_id: 'pub-100',
    reviewer_id: 'jarek',
    template_id: 'tmpl-v1',
    assessed_at: '2026-08-11T09:00:00Z',
    responses: [],
  });
};

describe('Reviewer identity persistence (bugfix/reviewer-persistence)', () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_DUPLICATE_KEY);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_DUPLICATE_KEY);
  });

  it('A. no stored reviewer -> reviewer prompt/modal appears', () => {
    installApiMocks();

    renderPage();

    expect(screen.getByText('Identyfikator Recenzenta')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Reviewer identifier' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rozpocznij Ocenę Jakości' })).toBeInTheDocument();
    expect(qualityAssessmentApi.getOverview).not.toHaveBeenCalled();
  });

  it('B. stored reviewer is restored and modal does not appear', async () => {
    localStorage.setItem(STORAGE_KEY, 'jarek');
    installApiMocks();

    renderPage();

    await screen.findByText('Lean Energy Effectiveness Study');
    expect(screen.queryByText('Identyfikator Recenzenta')).not.toBeInTheDocument();
    expect(screen.getByText('Recenzent: jarek')).toBeInTheDocument();
  });

  it('C. entering "  jarek  " is trimmed and persisted canonically', async () => {
    installApiMocks();

    renderPage();

    const input = screen.getByRole('textbox', { name: 'Reviewer identifier' });
    fireEvent.change(input, { target: { value: '  jarek  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Rozpocznij Ocenę Jakości' }));

    await screen.findByText('Lean Energy Effectiveness Study');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('jarek');
    expect(screen.getByText('Recenzent: jarek')).toBeInTheDocument();
  });

  it('D. remount/hard refresh restores reviewer and does not re-prompt', async () => {
    localStorage.setItem(STORAGE_KEY, 'jarek');
    installApiMocks();

    const first = renderPage();
    await first.findByText('Lean Energy Effectiveness Study');
    first.unmount();

    const second = renderPage();
    await second.findByText('Lean Energy Effectiveness Study');

    expect(screen.queryByText('Identyfikator Recenzenta')).not.toBeInTheDocument();
    expect(localStorage.getItem(STORAGE_KEY)).toBe('jarek');
    expect(screen.getByText('Recenzent: jarek')).toBeInTheDocument();

    second.unmount();
  });

  it('E. QA API calls use the restored reviewer "jarek"', async () => {
    localStorage.setItem(STORAGE_KEY, 'jarek');
    installApiMocks();

    renderPage();
    await screen.findByText('Lean Energy Effectiveness Study');

    fireEvent.click(screen.getAllByRole('button', { name: 'TAK' })[0]);
    const textareas = screen.getAllByLabelText('Uzasadnienie (wymagane w przypadku wyboru odpowiedzi):', {
      exact: false,
    });
    fireEvent.change(textareas[0], { target: { value: 'Well-defined cohort.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));

    await waitFor(() => {
      expect(qualityAssessmentApi.saveAssessment).toHaveBeenCalledWith('proj-1', {
        reviewer_id: 'jarek',
        publication_id: 'pub-100',
        responses: [
          {
            criterion_id: 'crit-1',
            response_value: 'YES',
            justification: 'Well-defined cohort.',
          },
        ],
      });
    });

    expect(qualityAssessmentApi.getOverview).toHaveBeenCalledWith('proj-1', 'jarek');
  });

  it('F. change reviewer "jarek" -> "anna" updates canonical storage and subsequent API calls', async () => {
    localStorage.setItem(STORAGE_KEY, 'jarek');
    installApiMocks();

    renderPage();
    await screen.findByText('Lean Energy Effectiveness Study');

    // confirmDiscard() should be false (no unsaved changes), so the change button is directly clickable
    fireEvent.click(screen.getByRole('button', { name: /Recenzent: jarek/ }));

    const dialog = await screen.findByText('Zmień Reviewera');
    expect(dialog).toBeInTheDocument();

    const input = screen.getByRole('textbox', { name: 'Reviewer identifier' });
    fireEvent.change(input, { target: { value: '  anna  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz i Przełącz' }));

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY)).toBe('anna');
    });
    expect(screen.getByText('Recenzent: anna')).toBeInTheDocument();
    expect(qualityAssessmentApi.getOverview).toHaveBeenLastCalledWith('proj-1', 'anna');
  });

  it('G. whitespace-only reviewer is rejected and not persisted', async () => {
    installApiMocks();

    renderPage();

    const input = screen.getByRole('textbox', { name: 'Reviewer identifier' });
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Rozpocznij Ocenę Jakości' }));

    expect(await screen.findByText(/Identyfikator recenzenta nie może być pusty/i)).toBeInTheDocument();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(screen.getByText('Identyfikator Recenzenta')).toBeInTheDocument();
  });

  it('H. legacy duplicate storage key no longer controls Quality Assessment', async () => {
    localStorage.setItem(LEGACY_DUPLICATE_KEY, 'legacy_user');
    installApiMocks();

    renderPage();

    // The legacy key must NOT be the source of truth; modal must appear.
    expect(screen.getByText('Identyfikator Recenzenta')).toBeInTheDocument();
    expect(screen.queryByText('Recenzent: legacy_user')).not.toBeInTheDocument();

    // Submit a real reviewer via the canonical path.
    const input = screen.getByRole('textbox', { name: 'Reviewer identifier' });
    fireEvent.change(input, { target: { value: 'jarek' } });
    fireEvent.click(screen.getByRole('button', { name: 'Rozpocznij Ocenę Jakości' }));

    await screen.findByText('Lean Energy Effectiveness Study');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('jarek');
    expect(localStorage.getItem(LEGACY_DUPLICATE_KEY)).toBe('legacy_user');
  });
});
