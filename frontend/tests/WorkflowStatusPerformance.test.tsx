import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectProvider } from '../src/context/ProjectContext';
import { ProjectDashboardPage } from '../src/pages/ProjectDashboardPage';
import { projectApiService } from '../src/services/api/projectApi';
import { screeningApi } from '../src/services/api/screeningApi';
import { qualityAssessmentApi } from '../src/services/api/qualityAssessmentApi';
import { extractionApi } from '../src/services/api/extractionApi';

const project: any = {
  id: 'lean_energy', title: 'Lean Energy', description: '', protocolVersion: '1.0', status: 'active',
  createdAt: '', updatedAt: '', nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
  conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
  providers: [], imports: [], normalization: [],
  deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
  duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
  qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
  prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
};

const groups = Array.from({ length: 100 }, (_, i) => ({
  group_id: `g-${i}`, reason: 'DOI', records_count: 2, status: 'PENDING' as const, shared_identifiers: [], records: [],
}));

describe('Workflow status performance on a large dataset', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([project]);
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({ project_id: 'lean_energy', total_groups_count: 100, groups } as any);
    vi.spyOn(projectApiService, 'getPrismaMetrics').mockResolvedValue({ project_id: 'lean_energy' } as any);
    vi.spyOn(projectApiService, 'getResumableFetchAllSearches').mockResolvedValue([]);
    vi.spyOn(screeningApi, 'getOverview').mockResolvedValue({
      project_id: 'lean_energy', reviewer_id: 'default_reviewer', ready: true, readiness_status: 'ready',
      working_collection_count: 1000, canonical_records_count: 1000, unresolved_duplicate_groups: 0, criteria: [],
      progress: { total: 1000, unscreened: 500, included: 0, excluded: 0, uncertain: 0, completed: 500 },
    } as any);
    vi.spyOn(screeningApi, 'getFullTextOverview').mockResolvedValue({ project_id: 'lean_energy', ready: false, eligible_records_count: 0, progress: null } as any);
    vi.spyOn(qualityAssessmentApi, 'getOverview').mockResolvedValue(null as any);
    vi.spyOn(extractionApi, 'getExtractionProgress').mockResolvedValue({ total_eligible_publications: 0, complete_count: 0, in_progress_count: 0 } as any);
  });

  it('renders 100 duplicate groups and 1000 screening records within the threshold', async () => {
    const started = performance.now();
    render(
      <MemoryRouter initialEntries={['/projects/lean_energy/dashboard']}>
        <ProjectProvider>
          <Routes>
            <Route path="/projects/:projectId/dashboard" element={<ProjectDashboardPage />} />
          </Routes>
        </ProjectProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText('100 grup')).toBeInTheDocument(), { timeout: 3000 });
    await waitFor(() => expect(screen.getAllByText('500/1000 oceniono').length).toBeGreaterThan(0), { timeout: 3000 });
    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(3000);
  });
});
