import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QualityAssessmentPage } from '../src/pages/QualityAssessmentPage';
import { qualityAssessmentApi, QualityAssessmentApiError } from '../src/services/api/qualityAssessmentApi';

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
        {
          criterion_id: 'crit-2',
          template_id: 'tmpl-v1',
          display_order: 2,
          question: 'Was the cohort recruited in an acceptable way?',
          guidance: 'Look for selection bias',
          is_required: false,
        },
      ],
    },
    {
      template_id: 'tmpl-v2',
      tool_id: 'casp',
      template_key: 'cohort',
      name: 'CASP Cohort v2',
      version: 2,
      description: 'Cohort study checklist v2',
      is_active: true,
      criteria: [
        {
          criterion_id: 'crit-1-v2',
          template_id: 'tmpl-v2',
          display_order: 1,
          question: 'Did the study address a clearly focused issue? (v2)',
          guidance: 'v2 guidance',
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
  reviewer_id: 'rev_tester',
  is_currently_eligible: true,
  template: mockTool.templates[0],
  latest_assessment: null,
  history: [],
};

const mockDetailWithHistory = {
  ...mockDetailReady,
  latest_assessment: {
    assessment_id: 'ass-1',
    project_id: 'proj-1',
    publication_id: 'pub-100',
    reviewer_id: 'rev_tester',
    template_id: 'tmpl-v1',
    assessed_at: '2026-08-11T08:00:00Z',
    responses: [
      {
        response_id: 'resp-1',
        assessment_id: 'ass-1',
        criterion_id: 'crit-1',
        response_value: 'YES' as const,
        justification: 'Clear research question',
        question_snapshot: 'Did the study address a clearly focused issue?',
        guidance_snapshot: 'Look for population',
        is_required_snapshot: true,
      },
    ],
  },
  history: [
    {
      assessment_id: 'ass-1',
      project_id: 'proj-1',
      publication_id: 'pub-100',
      reviewer_id: 'rev_tester',
      template_id: 'tmpl-v1',
      assessed_at: '2026-08-11T08:00:00Z',
      responses: [
        {
          response_id: 'resp-1',
          assessment_id: 'ass-1',
          criterion_id: 'crit-1',
          response_value: 'YES' as const,
          justification: 'Clear research question',
          question_snapshot: 'Did the study address a clearly focused issue?',
          guidance_snapshot: 'Look for population',
          is_required_snapshot: true,
        },
      ],
    },
  ],
};

describe('Quality Assessment GUI (Phase 8.4)', () => {
  beforeEach(() => {
    localStorage.setItem('slr_screening_reviewer_id', 'rev_tester');
    vi.restoreAllMocks();

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
      reviewer_id: 'rev_tester',
      template_id: 'tmpl-v1',
      assessed_at: '2026-08-11T09:00:00Z',
      responses: [],
    });
  });

  it('1. REVIEWER: prompts for reviewer identity if missing, persists to localStorage and reloads', async () => {
    localStorage.removeItem('slr_screening_reviewer_id');

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Identyfikator Recenzenta')).toBeInTheDocument();
    const input = screen.getByRole('textbox', { name: 'Reviewer identifier' });
    fireEvent.change(input, { target: { value: 'bob' } });
    fireEvent.click(screen.getByRole('button', { name: 'Rozpocznij Ocenę Jakości' }));

    await screen.findByText('Lean Energy Effectiveness Study');
    expect(localStorage.getItem('slr_screening_reviewer_id')).toBe('bob');
  });

  it('2. READINESS: renders blocking alert when project configuration is missing', async () => {
    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValueOnce({
      readiness: 'no_quality_assessment_configuration',
      tool_id: null,
      template_id: null,
      template_version: null,
      total_eligible: 0,
      total_assessed: 0,
      total_remaining: 0,
    });

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/configuration" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Brak skonfigurowanego kwestionariusza oceny jakości (Quality Assessment)');
    fireEvent.click(screen.getByRole('button', { name: 'Skonfiguruj Szablon Quality Assessment' }));
    await screen.findByText('Konfiguracja Szablonu Oceny Jakościowej (Quality Assessment)');
  });

  it('3. READINESS: renders empty eligible alert when no publications are included in Full-Text', async () => {
    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValueOnce({
      readiness: 'no_eligible_publications',
      tool_id: 'casp',
      template_id: 'tmpl-v1',
      template_version: 1,
      total_eligible: 0,
      total_assessed: 0,
      total_remaining: 0,
    });

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Brak zakwalifikowanych publikacji do Oceny Jakości');
  });

  it('4. RECORD & CRITERIA: renders publication metadata, abstract, active tool/template context and response options (TAK/NIE/NIE MOŻNA OKREŚLIĆ)', async () => {
    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Lean Energy Effectiveness Study');
    expect(screen.getByText('Aktywne Narzędzie Oceny: CASP Cohort v1 (v1)')).toBeInTheDocument();
    expect(screen.getByText(/Did the study address a clearly focused issue/i)).toBeInTheDocument();
    expect(screen.getByText('Wytyczne: Look for population, risk factor, outcome')).toBeInTheDocument();

    // Verify response buttons TAK, NIE, NIE MOŻNA OKREŚLIĆ exist (no raw browser radios)
    expect(screen.getAllByRole('button', { name: 'TAK' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'NIE' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'NIE MOŻNA OKREŚLIĆ' }).length).toBeGreaterThan(0);
  });

  it('5. SAVE & VALIDATION: allows optional justification for YES, requires non-blank justification for NO', async () => {
    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Lean Energy Effectiveness Study');

    const saveBtn = screen.getByRole('button', { name: 'Zapisz' });
    expect(saveBtn).toBeDisabled();

    // 1. Select NIE for criterion 1 -> save must remain disabled without justification
    const nieBtns = screen.getAllByRole('button', { name: 'NIE' });
    fireEvent.click(nieBtns[0]);
    expect(saveBtn).toBeDisabled();

    // 2. Select TAK for criterion 1 -> save is enabled immediately (justification optional)
    const takBtns = screen.getAllByRole('button', { name: 'TAK' });
    fireEvent.click(takBtns[0]);
    expect(saveBtn).not.toBeDisabled();

    // 3. Switch back to NIE -> save becomes disabled again
    fireEvent.click(nieBtns[0]);
    expect(saveBtn).toBeDisabled();

    // 4. Provide justification for NIE -> save becomes enabled
    const textareas = screen.getAllByLabelText(/Uzasadnienie/i);
    fireEvent.change(textareas[0], { target: { value: 'Well defined reason for NO response.' } });
    expect(saveBtn).not.toBeDisabled();

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(qualityAssessmentApi.saveAssessment).toHaveBeenCalledWith('proj-1', {
        reviewer_id: 'rev_tester',
        publication_id: 'pub-100',
        responses: [
          {
            criterion_id: 'crit-1',
            response_value: 'NO',
            justification: 'Well defined reason for NO response.',
          },
        ],
      });
    });
  });

  it('6. UNASSESSED SAVE & NEXT INVARIANT: Save & Next on UNASSESSED does not skip next publication', async () => {
    const pub2 = { ...mockPubRecord, record_id: 'pub-200', title: 'Second Included Paper' };

    vi.spyOn(qualityAssessmentApi, 'listRecords')
      .mockResolvedValueOnce({
        items: [
          { publication: mockPubRecord, has_assessment: false, latest_assessment: null },
          { publication: pub2, has_assessment: false, latest_assessment: null },
        ],
        total: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
      })
      .mockResolvedValueOnce({
        items: [{ publication: pub2, has_assessment: false, latest_assessment: null }],
        total: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
      });

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail')
      .mockResolvedValueOnce(mockDetailReady)
      .mockResolvedValueOnce({
        ...mockDetailReady,
        publication: pub2,
      });

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Lean Energy Effectiveness Study');

    fireEvent.click(screen.getAllByRole('button', { name: 'TAK' })[0]);

    const saveNextBtn = screen.getByRole('button', { name: 'Zapisz i następny' });
    fireEvent.click(saveNextBtn);

    await screen.findByText('Second Included Paper');
  });

  it('7. HISTORY: displays previous assessments audit log and preserves historical template version', async () => {
    vi.spyOn(qualityAssessmentApi, 'getRecordDetail').mockResolvedValue(mockDetailWithHistory as any);

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Lean Energy Effectiveness Study');
    expect(screen.getByText('Historia Ocen Publikacji (1)')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Historia Ocen Publikacji (1)'));
    await screen.findByText('Uzasadnienie: "Clear research question"');
  });

  it('8. CONFIGURATION GUI: allows changing QA tool and template with explicit confirmation prompt', async () => {
    vi.spyOn(qualityAssessmentApi, 'updateConfiguration').mockResolvedValue({
      project_id: 'proj-1',
      tool_id: 'casp',
      template_id: 'tmpl-v2',
      template_key: 'cohort',
      template_name: 'CASP Cohort v2',
      version: 2,
      configured_at: '2026-08-11T09:00:00Z',
    });

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment/configuration']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment/configuration" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Konfiguracja Szablonu Oceny Jakościowej (Quality Assessment)');
    expect(screen.getByText('Aktualnie Skonfigurowany Szablon')).toBeInTheDocument();

    const templateSelect = screen.getByLabelText('2. Szablon i Wersja Kwestionariusza (Template Version):');
    fireEvent.change(templateSelect, { target: { value: 'tmpl-v2' } });

    fireEvent.click(screen.getByRole('button', { name: 'Zapisz Konfigurację QA' }));

    await waitFor(() => {
      expect(qualityAssessmentApi.updateConfiguration).toHaveBeenCalledWith('proj-1', 'casp', 'tmpl-v2', false);
    });
  });

  it('9. CONFIG UX: no existing configuration (404 / no active config) is NOT rendered as generic error and configuration form remains available', async () => {
    vi.spyOn(qualityAssessmentApi, 'getConfiguration').mockRejectedValueOnce(
      new QualityAssessmentApiError(
        404,
        "Project 'proj-1' has no active Quality Assessment configuration."
      )
    );

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment/configuration']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment/configuration" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Konfiguracja Szablonu Oceny Jakościowej (Quality Assessment)');
    // Ensures NO red error alert is rendered
    expect(screen.queryByText(/Wystąpił błąd/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/has no active Quality Assessment configuration/i)).not.toBeInTheDocument();

    // Form remains available for selecting a tool/template
    expect(screen.getByText('Wybór Narzędzia i Wersji Szablonu')).toBeInTheDocument();
    expect(screen.getByLabelText('1. Narzędzie Oceny Jakościowej (Tool):')).toBeInTheDocument();
  });

  it('10. CONFIG UX: empty tool/template catalog renders neutral empty state and disables Save button', async () => {
    vi.spyOn(qualityAssessmentApi, 'getTools').mockResolvedValueOnce([]);
    vi.spyOn(qualityAssessmentApi, 'getConfiguration').mockResolvedValueOnce(null);

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment/configuration']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment/configuration" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Konfiguracja Szablonu Oceny Jakościowej (Quality Assessment)');
    expect(screen.getByText('Brak dostępnych aktywnych narzędzi lub szablonów oceny jakości.')).toBeInTheDocument();
    expect(screen.queryByText(/Wystąpił błąd/i)).not.toBeInTheDocument();

    const saveBtn = screen.getByRole('button', { name: 'Zapisz Konfigurację QA' });
    expect(saveBtn).toBeDisabled();
  });

  it('11. CONFIG UX: real API failure (e.g. 500 Server Error) still renders error alert', async () => {
    vi.spyOn(qualityAssessmentApi, 'getTools').mockRejectedValueOnce(
      new QualityAssessmentApiError(500, 'Database connection failed')
    );

    render(
      <MemoryRouter initialEntries={['/projects/proj-1/quality-assessment/configuration']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment/configuration" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Database connection failed');
  });
});
