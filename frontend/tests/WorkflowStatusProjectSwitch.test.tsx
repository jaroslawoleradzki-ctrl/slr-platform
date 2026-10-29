import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { projectApiService } from '../src/services/api/projectApi';
import { screeningApi } from '../src/services/api/screeningApi';
import { qualityAssessmentApi } from '../src/services/api/qualityAssessmentApi';
import { extractionApi } from '../src/services/api/extractionApi';

const makeProject = (id: string, title: string) => ({
  id,
  title,
  description: '',
  protocolVersion: '1.0',
  status: 'active',
  createdAt: '',
  updatedAt: '',
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
});

const PROJECT_A = makeProject('project-a', 'Project A');
const PROJECT_B = makeProject('project-b', 'Project B');

const Probe = () => {
  const { activeProject, workflowStatus, duplicateData, setActiveProjectId } = useProject();
  return (
    <div>
      <div data-testid="active">{activeProject?.id ?? ''}</div>
      <div data-testid="dedup-workflow">{workflowStatus?.deduplication.totalGroups ?? ''}</div>
      <div data-testid="dedup-read-model">{duplicateData?.total_groups_count ?? ''}</div>
      <div data-testid="prisma">{activeProject?.prismaMetrics?.totalIdentified ?? ''}</div>
      <button type="button" onClick={() => setActiveProjectId('project-b')}>go-b</button>
      <button type="button" onClick={() => setActiveProjectId('project-a')}>go-a</button>
    </div>
  );
};

const groupsFor = (count: number) => ({
  project_id: 'irrelevant',
  total_groups_count: count,
  groups: Array.from({ length: count }, (_, i) => ({
    group_id: `g-${i}`, reason: 'DOI', records_count: 2, status: 'PENDING' as const, shared_identifiers: [], records: [],
  })),
});

const metricsFor = (total: number) => ({
  project_id: 'irrelevant',
  records_identified_providers: 0,
  records_identified_imports: total,
  total_identified: total,
  records_after_normalization: total,
  records_before_dedup: total,
  records_after_technical_merger: total,
  duplicate_groups_pending_review: 0,
  records_screened_title_abstract: 0,
  records_screened_full_text: 0,
  studies_included_synthesis: 0,
  manual_source_breakdown: {},
});

describe('workflow status project switch isolation', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([PROJECT_A, PROJECT_B] as any);
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockImplementation(async (projectId: string) => {
      const count = projectId === 'project-a' ? 3 : 7;
      return { ...groupsFor(count), project_id: projectId } as any;
    });
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockImplementation(async (projectId: string) => {
      const total = projectId === 'project-a' ? 100 : 200;
      return { ...metricsFor(total), project_id: projectId } as any;
    });
    vi.spyOn(projectApiService, 'getResumableFetchAllSearches').mockResolvedValue([]);
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue({
      project_id: 'irrelevant', reviewer_id: 'default_reviewer', ready: true, readiness_status: 'ready',
      working_collection_count: 0, canonical_records_count: 0, unresolved_duplicate_groups: 0, criteria: [],
      progress: { total: 0, unscreened: 0, included: 0, excluded: 0, uncertain: 0, completed: 0 },
    } as any);
    vi.spyOn(screeningApi, 'getFullTextOverview').mockResolvedValue({ ready: false, progress: null, eligible_records_count: 0 } as any);
    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValue(null as any);
    vi.spyOn(extractionApi, 'getExtractionProgress').mockResolvedValue({ total_eligible_publications: 0, complete_count: 0, in_progress_count: 0 } as any);
  });

  it('shows only the active project data after switching A -> B -> A', async () => {
    render(<ProjectProvider><Probe /></ProjectProvider>);

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('project-a'));
    await waitFor(() => expect(screen.getByTestId('dedup-workflow')).toHaveTextContent('3'));
    expect(screen.getByTestId('dedup-read-model')).toHaveTextContent('3');
    expect(screen.getByTestId('prisma')).toHaveTextContent('100');

    fireEvent.click(screen.getByRole('button', { name: 'go-b' }));

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('project-b'));
    await waitFor(() => expect(screen.getByTestId('dedup-workflow')).toHaveTextContent('7'));
    expect(screen.getByTestId('dedup-read-model')).toHaveTextContent('7');
    expect(screen.getByTestId('prisma')).toHaveTextContent('200');

    fireEvent.click(screen.getByRole('button', { name: 'go-a' }));

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('project-a'));
    await waitFor(() => expect(screen.getByTestId('dedup-workflow')).toHaveTextContent('3'));
    expect(screen.getByTestId('dedup-read-model')).toHaveTextContent('3');
    expect(screen.getByTestId('prisma')).toHaveTextContent('100');
  });
});
