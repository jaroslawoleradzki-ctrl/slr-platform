import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ProjectProvider } from '../src/context/ProjectContext';
import { WorkflowStepper } from '../src/components/workflow/WorkflowStepper';
import { Sidebar } from '../src/components/layout/Sidebar';
import {
  getStageStatusPresentation,
} from '../src/components/workflow/stageStatusPresentation';
import {
  getWorkflowStageState,
  WORKFLOW_STAGES,
} from '../src/config/workflowStages';
import { projectApiService } from '../src/services/api/projectApi';
import { qualityAssessmentApi } from '../src/services/api/qualityAssessmentApi';
import { screeningApi } from '../src/services/api/screeningApi';
import { WorkflowNavigationStatus, WorkflowStageState } from '../src/types';

describe('stageStatusPresentation — shared status model', () => {
  const states: WorkflowStageState[] = [
    'not_started',
    'in_progress',
    'pending_action',
    'completed',
    'warning',
    'error',
    'not_available',
  ];

  it('gives every workflow state a distinct human-readable label', () => {
    const labels = states.map((state) => getStageStatusPresentation(state).label);
    expect(new Set(labels).size).toBe(states.length);
    expect(getStageStatusPresentation('pending_action').label).toBe('Wymaga działania');
    expect(getStageStatusPresentation('error').label).toBe('Błąd');
  });

  it('pairs states with distinct glyphs so colour is not the only signal', () => {
    const glyphNames = new Set(
      states.map((state) => {
        const { icon } = getStageStatusPresentation(state);
        if (!React.isValidElement(icon)) return String(icon);
        return ((icon.type as { name?: string; displayName?: string }).name
          ?? (icon.type as { displayName?: string }).displayName
          ?? String(icon.type));
      })
    );
    // completed=CheckCircle2, in_progress=CircleDot, pending_action/warning/error=Alert*,
    // not_started/not_available=Clock — at least four distinct glyphs across seven states
    expect(glyphNames.size).toBeGreaterThanOrEqual(4);
  });
});

describe('getWorkflowStageState — single source of stage states', () => {
  const status = (
    overrides: Partial<Record<'dataExtraction' | 'exports' | 'qualityAssessment', WorkflowStageState>>
  ): WorkflowNavigationStatus =>
    ({
      search: { state: 'not_started', label: null },
      sources: { state: 'not_started', label: null },
      normalization: { state: 'not_started', label: null },
      deduplication: {
        state: 'not_started',
        totalGroups: 0,
        pendingGroups: 0,
        approvedGroups: 0,
        rejectedGroups: 0,
        label: null,
      },
      screening: { state: 'not_started', label: null },
      fullTextScreening: { state: 'not_started', label: null },
      qualityAssessment: { state: overrides.qualityAssessment ?? 'not_started', label: null },
      dataExtraction: { state: overrides.dataExtraction ?? 'not_started', label: null },
      exports: { state: overrides.exports ?? 'not_available', label: null },
    }) as unknown as WorkflowNavigationStatus;

  it('maps stages to their own status key', () => {
    const s = status({ qualityAssessment: 'pending_action', exports: 'pending_action' });
    expect(getWorkflowStageState(s, WORKFLOW_STAGES[5])).toBe('pending_action'); // QA
    expect(getWorkflowStageState(s, WORKFLOW_STAGES[8])).toBe('pending_action'); // Exports
    expect(getWorkflowStageState(s, WORKFLOW_STAGES[6])).toBe('not_started'); // Extraction untouched
  });

  it('derives Evidence Synthesis from upstream progress instead of hardcoding', () => {
    const idle = status({});
    const extractionDone = status({ dataExtraction: 'completed' });
    const exportReady = status({ exports: 'pending_action' });

    expect(getWorkflowStageState(idle, WORKFLOW_STAGES[7])).toBe('not_started');
    expect(getWorkflowStageState(extractionDone, WORKFLOW_STAGES[7])).toBe('in_progress');
    expect(getWorkflowStageState(exportReady, WORKFLOW_STAGES[7])).toBe('in_progress');
  });

  it('falls back to not_started when no status payload exists yet', () => {
    expect(getWorkflowStageState(null, WORKFLOW_STAGES[6])).toBe('not_started');
    expect(getWorkflowStageState(null, WORKFLOW_STAGES[7])).toBe('not_started');
  });
});

describe('WorkflowStepper — compact overview bar (integration)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      {
        id: 'lean_energy',
        title: 'Lean Management Project',
        description: '',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '2026-08-01T00:00:00Z',
        updatedAt: '2026-08-01T00:00:00Z',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
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
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({
      project_id: 'lean_energy',
      total_groups_count: 3,
      groups: Array.from({ length: 3 }, (_, i) => ({
        group_id: `g-${i}`,
        reason: 'DOI match',
        records_count: 2,
        status: 'PENDING' as const,
        shared_identifiers: [],
        records: [],
      })),
    });
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue({
      project_id: 'lean_energy',
      reviewer_id: 'default_reviewer',
      ready: true,
      readiness_status: 'ready',
      working_collection_count: 0,
      canonical_records_count: 0,
      unresolved_duplicate_groups: 3,
      criteria: [],
      progress: { total: 0, unscreened: 0, included: 0, excluded: 0, uncertain: 0, completed: 0 },
    });
    vi.spyOn(screeningApi, 'getFullTextOverview').mockResolvedValue({
      project_id: 'lean_energy',
      reviewer_id: 'default_reviewer',
      ready: false,
      readiness_status: 'waiting_for_title_abstract',
      eligible_records_count: 0,
      working_collection_count: 0,
      canonical_records_count: 0,
      unresolved_duplicate_groups: 3,
      criteria: [],
      progress: null,
    });
    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValue({
      readiness: 'no_quality_assessment_configuration',
      tool_id: null,
      template_id: null,
      template_version: null,
      total_eligible: 0,
      total_assessed: 0,
      total_remaining: 0,
    });
  });

  const renderStepper = () =>
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/search']}>
          <WorkflowStepper />
          <Sidebar />
        </MemoryRouter>
      </ProjectProvider>
    );

  it('renders nine compact steps with short labels', async () => {
    renderStepper();
    await waitFor(() => expect(screen.getByTestId('workflow-stepper')).toBeInTheDocument());
    for (const short of ['Search', 'Sources', 'Normalize', 'Dedupe', 'Screening', 'QA', 'Extraction', 'Synthesis', 'Export']) {
      expect(screen.getByText(new RegExp(`^${'\\d+'}\\. ${short}$`))).toBeInTheDocument();
    }
  });

  it('links QA through the canonical /quality-assessment path', async () => {
    renderStepper();
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /6\. QA/u })).toHaveAttribute(
        'href',
        '/projects/lean_energy/quality-assessment'
      )
    );
  });

  it('surfaces requires-configuration and pending-review states without hardcodes', async () => {
    renderStepper();

    const stepper = await waitFor(() => {
      const el = screen.getByTestId('workflow-stepper');
      expect(el).toBeInTheDocument();
      return el;
    });

    // Sidebar: dedupe pending review badge + QA configuration pill (detailed view)
    await waitFor(() => expect(screen.getByText('3 do oceny')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('Wymaga konfiguracji')).toBeInTheDocument());

    // Top bar: compact chip for dedupe keeps only the numeric alert…
    expect(within(stepper).getByText(/^4\. Dedupe$/u)).toBeInTheDocument();
    expect(within(stepper).getByText(/^3$/u)).toBeInTheDocument();

    // …and tooltips carry full stage names plus state details.
    const qaLink = within(stepper).getByRole('link', { name: /6\. QA/u });
    expect(qaLink.getAttribute('title')).toMatch(/Quality Assessment/u);
    expect(qaLink.getAttribute('title')).toMatch(/Wymaga działania|Wymaga konfiguracji/u);
  });
});
