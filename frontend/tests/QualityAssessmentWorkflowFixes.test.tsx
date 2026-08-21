import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QualityAssessmentPage } from '../src/pages/QualityAssessmentPage';
import {
  qualityAssessmentApi,
  QualityAssessmentRecordDetail,
  PublicationRecord,
  QualityAssessmentToolCriterion,
  QualityAssessmentTemplate,
} from '../src/services/api/qualityAssessmentApi';
import { ProjectProvider, computeWorkflowStatus } from '../src/context/ProjectContext';
import { ProjectDashboardPage } from '../src/pages/ProjectDashboardPage';
import { projectApiService } from '../src/services/api/projectApi';
import { screeningApi } from '../src/services/api/screeningApi';
import { extractionApi } from '../src/services/api/extractionApi';

const mockCriteria: QualityAssessmentToolCriterion[] = [
  {
    criterion_id: 'crit-1',
    template_id: 'tmpl-1',
    question: 'Is the research objective clearly stated?',
    guidance: 'Check introduction and aim.',
    is_required: true,
    display_order: 1,
  },
  {
    criterion_id: 'crit-2',
    template_id: 'tmpl-1',
    question: 'Was the data collection methodology sound?',
    guidance: 'Check method section.',
    is_required: true,
    display_order: 2,
  },
];

const mockTemplate: QualityAssessmentTemplate = {
  template_id: 'tmpl-1',
  tool_id: 'tool-1',
  template_key: 'slr_qa',
  name: 'Standard SLR QA Template',
  version: 1,
  description: 'QA Template',
  is_active: true,
  criteria: mockCriteria,
};

const mockPub1: PublicationRecord = {
  record_id: 'pub-001',
  title: 'Paper One: Energy Optimization in Manufacturing',
  abstract: 'Abstract of paper 1',
  authors: [{ display_name: 'Author A' }],
  publication_year: 2024,
  venue: { name: 'Journal of Cleaner Production' },
  doi: '10.1016/j.jclepro.2024.01',
  urls: [],
};

const mockPub2: PublicationRecord = {
  record_id: 'pub-002',
  title: 'Paper Two: Lean Production and Environmental Performance',
  abstract: 'Abstract of paper 2',
  authors: [{ display_name: 'Author B' }],
  publication_year: 2023,
  venue: { name: 'International Journal of Operations' },
  doi: '10.1016/j.ijop.2023.02',
  urls: [],
};

const mockPub3: PublicationRecord = {
  record_id: 'pub-003',
  title: 'Paper Three: Sustainable Circular Economy Systems',
  abstract: 'Abstract of paper 3',
  authors: [{ display_name: 'Author C' }],
  publication_year: 2022,
  venue: { name: 'Resources, Conservation and Recycling' },
  doi: '10.1016/j.resconrec.2022.03',
  urls: [],
};

const mockDetailPub1: QualityAssessmentRecordDetail = {
  project_id: 'proj-fix',
  publication: mockPub1,
  reviewer_id: 'rev_tester',
  template: mockTemplate,
  latest_assessment: null,
  is_currently_eligible: true,
  history: [],
};

const mockDetailPub2: QualityAssessmentRecordDetail = {
  project_id: 'proj-fix',
  publication: mockPub2,
  reviewer_id: 'rev_tester',
  template: mockTemplate,
  latest_assessment: null,
  is_currently_eligible: true,
  history: [],
};

const mockDetailPub3: QualityAssessmentRecordDetail = {
  project_id: 'proj-fix',
  publication: mockPub3,
  reviewer_id: 'rev_tester',
  template: mockTemplate,
  latest_assessment: null,
  is_currently_eligible: true,
  history: [],
};

describe('Quality Assessment & Workflow Regression Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('slr_screening_reviewer_id', 'rev_tester');

    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValue({
      readiness: 'ready',
      tool_id: 'tool-1',
      template_id: 'tmpl-1',
      template_version: 1,
      total_eligible: 3,
      total_assessed: 0,
      total_remaining: 3,
    });

    vi.spyOn(qualityAssessmentApi, 'saveAssessment').mockResolvedValue({
      assessment_id: 'asm-1',
      project_id: 'proj-fix',
      publication_id: 'pub-001',
      reviewer_id: 'rev_tester',
      template_id: 'tmpl-1',
      responses: [],
      assessed_at: '2026-08-17T12:00:00Z',
    });
  });

  it('Issue 1: YES response allows empty justification; NO requires non-blank justification', async () => {
    vi.spyOn(qualityAssessmentApi, 'listRecords').mockResolvedValue({
      items: [
        { publication: mockPub1, has_assessment: false, latest_assessment: null },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail').mockResolvedValue(mockDetailPub1);

    render(
      <MemoryRouter initialEntries={['/projects/proj-fix/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Paper One: Energy Optimization in Manufacturing');

    const saveBtn = screen.getByRole('button', { name: 'Zapisz' });
    expect(saveBtn).toBeDisabled();

    // Answer Q1 with YES, Q2 with YES -> Save should be enabled immediately without justifications
    const takButtons = screen.getAllByRole('button', { name: 'TAK' });
    fireEvent.click(takButtons[0]); // Q1 -> YES
    fireEvent.click(takButtons[1]); // Q2 -> YES

    expect(saveBtn).not.toBeDisabled();

    // Now change Q1 to NIE (NO) -> Save should become disabled because justification is missing
    const nieButtons = screen.getAllByRole('button', { name: 'NIE' });
    fireEvent.click(nieButtons[0]); // Q1 -> NO

    expect(saveBtn).toBeDisabled();
    expect(screen.getByText(/Wymagane jest wprowadzenie niepustego uzasadnienia/i)).toBeInTheDocument();

    // Enter non-blank justification for Q1
    const textareas = screen.getAllByPlaceholderText(/Wprowadź uzasadnienie/i);
    fireEvent.change(textareas[0], { target: { value: 'Methodology missing control group.' } });

    expect(saveBtn).not.toBeDisabled();

    // Change Q2 to NIE MOŻNA OKREŚLIĆ -> Save disabled until justification provided
    const cannotButtons = screen.getAllByRole('button', { name: 'NIE MOŻNA OKREŚLIĆ' });
    fireEvent.click(cannotButtons[1]); // Q2 -> CANNOT_DETERMINE

    expect(saveBtn).toBeDisabled();

    fireEvent.change(textareas[1], { target: { value: 'Unclear statistical analysis description.' } });
    expect(saveBtn).not.toBeDisabled();

    // Trigger save and check payload
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(qualityAssessmentApi.saveAssessment).toHaveBeenCalledWith('proj-fix', {
        reviewer_id: 'rev_tester',
        publication_id: 'pub-001',
        responses: [
          {
            criterion_id: 'crit-1',
            response_value: 'NO',
            justification: 'Methodology missing control group.',
          },
          {
            criterion_id: 'crit-2',
            response_value: 'CANNOT_DETERMINE',
            justification: 'Unclear statistical analysis description.',
          },
        ],
      });
    });
  });

  it('Issue 2A: Middle UNASSESSED item advances sequentially to next forward item', async () => {
    // Initial 3 items. User is currently assessing item 2 (middle item).
    vi.spyOn(qualityAssessmentApi, 'listRecords')
      .mockResolvedValueOnce({
        items: [
          { publication: mockPub1, has_assessment: false, latest_assessment: null },
          { publication: mockPub2, has_assessment: false, latest_assessment: null },
          { publication: mockPub3, has_assessment: false, latest_assessment: null },
        ],
        total: 3,
        page: 1,
        page_size: 20,
        total_pages: 1,
      })
      .mockResolvedValueOnce({
        // After pub2 is saved, unassessed list has pub1 and pub3
        items: [
          { publication: mockPub1, has_assessment: false, latest_assessment: null },
          { publication: mockPub3, has_assessment: false, latest_assessment: null },
        ],
        total: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
      });

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail')
      .mockResolvedValueOnce(mockDetailPub2)
      .mockResolvedValueOnce(mockDetailPub3);

    render(
      <MemoryRouter initialEntries={['/projects/proj-fix/quality-assessment/pub-002']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Paper Two: Lean Production and Environmental Performance');

    const takButtons = screen.getAllByRole('button', { name: 'TAK' });
    fireEvent.click(takButtons[0]);
    fireEvent.click(takButtons[1]);

    const saveNextBtn = screen.getByRole('button', { name: 'Zapisz i następny' });
    fireEvent.click(saveNextBtn);

    // Advances forward to Paper Three (index 1 in refreshed list)
    await screen.findByText('Paper Three: Sustainable Circular Economy Systems');
  });

  it('Issue 2B: Last UNASSESSED item does not jump backward to earlier unassessed records', async () => {
    // Initial 2 items. User is assessing item 2 (last item).
    vi.spyOn(qualityAssessmentApi, 'listRecords')
      .mockResolvedValueOnce({
        items: [
          { publication: mockPub1, has_assessment: false, latest_assessment: null },
          { publication: mockPub2, has_assessment: false, latest_assessment: null },
        ],
        total: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
      })
      .mockResolvedValueOnce({
        // After pub2 is saved, only pub1 remains unassessed
        items: [
          { publication: mockPub1, has_assessment: false, latest_assessment: null },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
      });

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail')
      .mockResolvedValue(mockDetailPub2);

    render(
      <MemoryRouter initialEntries={['/projects/proj-fix/quality-assessment/pub-002']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Paper Two: Lean Production and Environmental Performance');

    const takButtons = screen.getAllByRole('button', { name: 'TAK' });
    fireEvent.click(takButtons[0]);
    fireEvent.click(takButtons[1]);

    const saveNextBtn = screen.getByRole('button', { name: 'Zapisz i następny' });
    fireEvent.click(saveNextBtn);

    // Stays on Paper Two with its refreshed saved state without jumping backward to Paper One
    await waitFor(() => {
      expect(screen.getByText('Paper Two: Lean Production and Environmental Performance')).toBeInTheDocument();
    });
  });

  it('Issue 2C: Saving only remaining UNASSESSED item transitions to empty/completed list', async () => {
    vi.spyOn(qualityAssessmentApi, 'listRecords')
      .mockResolvedValueOnce({
        items: [
          { publication: mockPub1, has_assessment: false, latest_assessment: null },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      });

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail')
      .mockResolvedValueOnce(mockDetailPub1);

    render(
      <MemoryRouter initialEntries={['/projects/proj-fix/quality-assessment/pub-001']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Paper One: Energy Optimization in Manufacturing');

    const takButtons = screen.getAllByRole('button', { name: 'TAK' });
    fireEvent.click(takButtons[0]);
    fireEvent.click(takButtons[1]);

    const saveNextBtn = screen.getByRole('button', { name: 'Zapisz i następny' });
    fireEvent.click(saveNextBtn);

    await waitFor(() => {
      expect(screen.getByText('Brak publikacji w wybranym filtrze')).toBeInTheDocument();
    });
  });

  it('Issue 2D: In ALL filter, Save and Next on the last item stays on that record without backward jump', async () => {
    const assessedPub1 = {
      assessment_id: 'asm-1',
      project_id: 'proj-fix',
      publication_id: 'pub-001',
      reviewer_id: 'rev_tester',
      template_id: 'tmpl-1',
      responses: [],
      assessed_at: '2026-08-17T12:00:00Z',
    };
    const assessedPub2 = {
      assessment_id: 'asm-2',
      project_id: 'proj-fix',
      publication_id: 'pub-002',
      reviewer_id: 'rev_tester',
      template_id: 'tmpl-1',
      responses: [],
      assessed_at: '2026-08-17T12:00:00Z',
    };

    vi.spyOn(qualityAssessmentApi, 'listRecords').mockResolvedValue({
      items: [
        { publication: mockPub1, has_assessment: true, latest_assessment: assessedPub1 },
        { publication: mockPub2, has_assessment: true, latest_assessment: assessedPub2 },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });

    const mockDetailPub2Assessed: QualityAssessmentRecordDetail = {
      ...mockDetailPub2,
      latest_assessment: assessedPub2,
    };

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail').mockResolvedValue(mockDetailPub2Assessed);

    render(
      <MemoryRouter initialEntries={['/projects/proj-fix/quality-assessment/pub-002?status=all']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Paper Two: Lean Production and Environmental Performance');

    const takButtons = screen.getAllByRole('button', { name: 'TAK' });
    fireEvent.click(takButtons[0]);
    fireEvent.click(takButtons[1]);

    const saveNextBtn = screen.getByRole('button', { name: 'Zapisz i następny' });
    fireEvent.click(saveNextBtn);

    // Stays on Paper Two
    await screen.findByText('Paper Two: Lean Production and Environmental Performance');
  });

  it('Issue 7: Filter buttons switch between unassessed, all, and assessed', async () => {
    const listRecordsSpy = vi.spyOn(qualityAssessmentApi, 'listRecords').mockResolvedValue({
      items: [{ publication: mockPub1, has_assessment: false, latest_assessment: null }],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });

    vi.spyOn(qualityAssessmentApi, 'getRecordDetail').mockResolvedValue(mockDetailPub1);

    render(
      <MemoryRouter initialEntries={['/projects/proj-fix/quality-assessment']}>
        <Routes>
          <Route path="/projects/:projectId/quality-assessment" element={<QualityAssessmentPage />} />
          <Route path="/projects/:projectId/quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Paper One: Energy Optimization in Manufacturing');

    // Click "Wszystkie" filter
    const allFilterBtn = screen.getByRole('button', { name: 'Wszystkie' });
    fireEvent.click(allFilterBtn);

    await waitFor(() => {
      expect(listRecordsSpy).toHaveBeenCalledWith('proj-fix', 'rev_tester', 'all', 1, 20);
    });

    // Click "Ocenione" filter
    const assessedFilterBtn = screen.getByRole('button', { name: 'Ocenione' });
    fireEvent.click(assessedFilterBtn);

    await waitFor(() => {
      expect(listRecordsSpy).toHaveBeenCalledWith('proj-fix', 'rev_tester', 'assessed', 1, 20);
    });
  });

  it('Issue 4 & 5: Dashboard reflects live workflow progression for screening, QA, extraction, and derived exports', async () => {
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      {
        id: 'proj-fix',
        title: 'Lean SLR Project',
        description: 'Test project description',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '2026-08-01T00:00:00Z',
        updatedAt: '2026-08-17T00:00:00Z',
        nextAction: { title: 'Next', description: 'Desc', targetStageId: 'search', actionLabel: 'Go', severity: 'normal' },
        conceptGroups: [],
        searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [],
        imports: [],
        normalization: [],
        deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [],
        screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
      },
    ]);

    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue({
      strategy_id: 'str-1',
      project_id: 'proj-fix',
      name: 'Search Strategy',
      description: null,
      research_questions: [],
      concept_groups: [{ group_id: 'cg-1', name: 'Lean', terms: ['lean'], operator: 'or' }],
      group_operator: 'and',
      constraints: {
        publication_year_from: null,
        publication_year_to: null,
        languages: [],
        publication_types: [],
        additional_limits: {},
      },
      providers: ['openalex'],
      queries: [],
      version: 1,
      created_at: '',
      updated_at: '',
    });
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([
      { import_id: 'imp-1', project_id: 'proj-fix', source_type: 'file', filename: 'export.bib', format: 'BibTeX', provider: 'scopus', query: '', total_available: 10, records_count: 10, status: 'success', warnings: [], created_at: '' },
    ]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue({
      run_id: 'norm-1',
      project_id: 'proj-fix',
      status: 'completed',
      processed_records: 10,
      clean_records: 10,
      warnings_count: 0,
      errors_count: 0,
      rules_applied: [],
      audit_trail: [],
      started_at: '',
      completed_at: '',
      executed_at: '',
    });
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({
      project_id: 'proj-fix',
      total_groups_count: 0,
      groups: [],
    });
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue({
      project_id: 'proj-fix',
      reviewer_id: 'rev_tester',
      ready: true,
      readiness_status: 'ready',
      working_collection_count: 10,
      canonical_records_count: 10,
      unresolved_duplicate_groups: 0,
      criteria: [],
      progress: { total: 10, unscreened: 0, included: 10, excluded: 0, uncertain: 0, completed: 10 },
    });
    vi.spyOn(screeningApi, 'getFullTextOverview').mockResolvedValue({
      project_id: 'proj-fix',
      reviewer_id: 'rev_tester',
      ready: true,
      readiness_status: 'ready',
      working_collection_count: 2,
      canonical_records_count: 2,
      unresolved_duplicate_groups: 0,
      eligible_records_count: 2,
      criteria: [],
      progress: { total: 2, unscreened: 0, included: 2, excluded: 0, uncertain: 0, completed: 2 },
    });
    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValue({
      readiness: 'ready',
      tool_id: 'tool-1',
      template_id: 'tmpl-1',
      template_version: 1,
      total_eligible: 2,
      total_assessed: 2,
      total_remaining: 0,
    });
    vi.spyOn(extractionApi, 'getExtractionProgress').mockResolvedValue({
      project_id: 'proj-fix',
      total_eligible_publications: 2,
      not_started_count: 0,
      in_progress_count: 0,
      needs_review_count: 0,
      complete_count: 2,
      completion_percentage: 100,
    });

    localStorage.setItem('slr_active_project_id', 'proj-fix');

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/proj-fix/dashboard']}>
          <Routes>
            <Route path="/projects/:projectId/dashboard" element={<ProjectDashboardPage />} />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

    await screen.findByText('Lean SLR Project');

    // Check all stage cards are rendered with live states
    expect(screen.getByText('5. Title & Abstract Screening')).toBeInTheDocument();
    expect(screen.getByText('5b. Full-Text Screening')).toBeInTheDocument();
    expect(screen.getByText('6. Quality Assessment')).toBeInTheDocument();
    expect(screen.getByText('7. Data Extraction')).toBeInTheDocument();
    expect(screen.getByText('8. Exports & PRISMA')).toBeInTheDocument();

    // Verify completed stages show "Skończono"
    await waitFor(() => {
      expect(screen.getByText('Ocena jakościowa zakończona')).toBeInTheDocument();
      expect(screen.getByText('Ekstrakcja zakończona')).toBeInTheDocument();
    });
  });

  it('Stage 8 (Exports & PRISMA): Derived availability is actionable (pending_action), NOT completed merely from upstream data', () => {
    // 1. Upstream incomplete -> exports not_available
    const statusIncomplete = computeWorkflowStatus(
      null, null, null, null, null, null, null, null
    );
    expect(statusIncomplete.exports.state).toBe('not_available');
    expect(statusIncomplete.exports.label).toBe('Niedostępne');

    // 2. Upstream screening completed -> exports available/actionable (pending_action)
    const statusUpstreamDone = computeWorkflowStatus(
      null,
      null,
      null,
      null,
      {
        project_id: 'p1',
        reviewer_id: 'r1',
        ready: true,
        readiness_status: 'ready',
        working_collection_count: 10,
        canonical_records_count: 10,
        unresolved_duplicate_groups: 0,
        criteria: [],
        progress: { total: 10, unscreened: 0, included: 10, excluded: 0, uncertain: 0, completed: 10 },
      },
      null,
      null,
      null
    );
    expect(statusUpstreamDone.exports.state).toBe('pending_action');
    expect(statusUpstreamDone.exports.label).toBe('Dostępne');

    // 3. Upstream completed does NOT mark Stage 8 as 'completed'
    expect(statusUpstreamDone.exports.state).not.toBe('completed');
  });
});
