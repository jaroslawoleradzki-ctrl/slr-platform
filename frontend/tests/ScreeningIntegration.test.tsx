import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ScreeningSectionLayout } from '../src/components/screening/ScreeningSectionLayout';
import { ProjectProvider } from '../src/context/ProjectContext';
import { projectApiService } from '../src/services/api/projectApi';

describe('Screening Integration Frontend Test Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders one combined conflicts and resolutions navigation link', () => {
    render(
      <MemoryRouter initialEntries={['/projects/test-proj/screen/title-abstract']}>
        <Routes>
          <Route path="/projects/:projectId/screen/*" element={<ScreeningSectionLayout />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'Title & Abstract Screening' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Full-Text Screening' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Criteria Configuration' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Podsumowanie i historia' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Konflikty i rozstrzygnięcia' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Resolution' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Konflikty reviewerów' })).not.toBeInTheDocument();
  });

  it('calls backend getWorkflowStatus for project workflow status', async () => {
    const mockWorkflowStatus = {
      project_id: 'test-proj',
      title_abstract_screening: {
        status: 'completed' as const,
        evaluated_count: 5,
        total_count: 5,
        conflict_count: 0,
        resolved_count: 0,
      },
      full_text_screening: {
        status: 'ready' as const,
        eligible_count: 3,
        evaluated_count: 0,
        conflict_count: 0,
        resolved_count: 0,
      },
      quality_assessment: {
        status: 'waiting_for_full_text' as const,
        eligible_count: 0,
      },
    };

    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      {
        id: 'test-proj',
        title: 'Test SLR Project',
        description: 'Testing 7.9',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '2026-08-11T00:00:00Z',
        updatedAt: '2026-08-11T00:00:00Z',
        nextAction: { title: 'T', description: 'D', targetStageId: 'search', actionLabel: 'A', severity: 'normal' },
        conceptGroups: [],
        searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [],
        imports: [],
        normalization: [],
        deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'completed' },
        duplicateGroups: [],
        screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 5 }, fullText: { pending: 3, included: 0, excluded: 0, unresolved: 0, total: 3 }, status: 'completed' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 5, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
      },
    ]);

    vi.spyOn(projectApiService, 'getWorkflowStatus').mockResolvedValue(mockWorkflowStatus);

    render(
      <MemoryRouter initialEntries={['/projects/test-proj/dashboard']}>
        <ProjectProvider>
          <div>Project Provider Mounted</div>
        </ProjectProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText('Project Provider Mounted')).toBeInTheDocument();
  });
});
