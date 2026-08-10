import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { ProjectsPage } from '../src/pages/ProjectsPage';
import { projectApiService } from '../src/services/api/projectApi';
import { SLRProject } from '../src/types';

const MOCK_API_PROJECTS: SLRProject[] = [
  {
    id: 'lean_energy',
    title: 'Lean Management and Energy Efficiency',
    description: 'Systematic review description',
    protocolVersion: '0.6',
    status: 'active',
    createdAt: '2026-07-01T10:00:00Z',
    updatedAt: '2026-07-28T16:45:00Z',
    nextAction: { title: 'Next Action', description: 'Desc', targetStageId: 'search', actionLabel: 'Label', severity: 'normal' },
    conceptGroups: [],
    searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
    providers: [],
    imports: [],
    normalization: [],
    deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
    duplicateGroups: [],
    screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
    qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
  },
  {
    id: 'archived_review',
    title: 'Archived Literature Review',
    description: 'Old review scope',
    protocolVersion: '0.1',
    status: 'archived',
    createdAt: '2026-06-01T10:00:00Z',
    updatedAt: '2026-06-28T16:45:00Z',
    nextAction: { title: 'Done', description: 'Desc', targetStageId: 'search', actionLabel: 'Label', severity: 'normal' },
    conceptGroups: [],
    searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
    providers: [],
    imports: [],
    normalization: [],
    deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
    duplicateGroups: [],
    screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
    qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
  },
];

describe('ProjectsPage & Project Management', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();

    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue(MOCK_API_PROJECTS);
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue({
      project_id: 'lean_energy',
      total_groups_count: 0,
      groups: [],
    });
  });

  const renderComponent = () =>
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects']}>
          <Routes>
            <Route path="/projects" element={<ProjectsPage />} />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

  it('renders active projects list on initial load', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Zarządzanie Projektami SLR')).toBeInTheDocument();
    });

    expect(screen.getByText('Lean Management and Energy Efficiency')).toBeInTheDocument();
    expect(screen.getByText('Aktywne Projekty (1)')).toBeInTheDocument();
    expect(screen.getByText('Zarchiwizowane (1)')).toBeInTheDocument();
  });

  it('switches between active and archived tabs', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Lean Management and Energy Efficiency')).toBeInTheDocument();
    });

    // Click Archived tab
    fireEvent.click(screen.getByText('Zarchiwizowane (1)'));

    await waitFor(() => {
      expect(screen.getByText('Archived Literature Review')).toBeInTheDocument();
    });
  });

  it('opens create project modal and submits new project', async () => {
    const createSpy = vi.spyOn(projectApiService, 'createProject').mockResolvedValue({
      ...MOCK_API_PROJECTS[0],
      id: 'new-ai-review-123456',
      title: 'New AI Review',
      description: 'Scope for AI',
      protocolVersion: '1.0',
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Lean Management and Energy Efficiency')).toBeInTheDocument();
    });

    // Click Create Project button
    fireEvent.click(screen.getByText('+ Utwórz Nowy Projekt'));

    expect(screen.getByText('Utwórz Nowy Projekt SLR')).toBeInTheDocument();

    // Fill form
    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: 'New AI Review' } });
    fireEvent.change(inputs[1], { target: { value: 'Scope for AI' } });

    // Submit
    fireEvent.click(screen.getByRole('button', { name: 'Utwórz Projekt' }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('New AI Review', 'Scope for AI', '1.0');
    });
  });
});
