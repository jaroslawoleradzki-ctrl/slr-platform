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
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
  },
  {
    id: 'ai_architecture',
    title: 'AI Architecture Review',
    description: 'Architecture review description',
    protocolVersion: '1.0',
    status: 'active',
    createdAt: '2026-07-15T10:00:00Z',
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
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
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
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
  },
];

describe('ProjectsPage & Project Management UX & Navigation', () => {
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

  const renderComponent = (initialRoute = '/projects') =>
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId/dashboard" element={<div data-testid="dashboard-view">Dashboard Workspace Target</div>} />
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
    expect(screen.getByText('AI Architecture Review')).toBeInTheDocument();
    expect(screen.getByText('Aktywne Projekty (2)')).toBeInTheDocument();
    expect(screen.getByText('Zarchiwizowane (1)')).toBeInTheDocument();
  });

  it('opens non-selected project on Otwórz button click and navigates to workspace dashboard', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('AI Architecture Review')).toBeInTheDocument();
    });

    const openButtons = screen.getAllByRole('button', { name: 'Otwórz' });
    expect(openButtons.length).toBe(2);

    // Click Otwórz on 2nd project (AI Architecture Review)
    fireEvent.click(openButtons[1]);

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-view')).toBeInTheDocument();
    });

    expect(localStorage.getItem('slr_active_project_id')).toBe('ai_architecture');
  });

  it('opens already-selected project on Otwórz button click and still navigates to workspace dashboard', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Lean Management and Energy Efficiency')).toBeInTheDocument();
    });

    const openButtons = screen.getAllByRole('button', { name: 'Otwórz' });
    // Click Otwórz on 1st project (Lean Management, which is currently selected)
    fireEvent.click(openButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-view')).toBeInTheDocument();
    });
  });

  it('clicking project title or card area opens the project', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('AI Architecture Review')).toBeInTheDocument();
    });

    // Click title
    fireEvent.click(screen.getByText('AI Architecture Review'));

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-view')).toBeInTheDocument();
    });
  });

  it('clicking Edit button opens modal and does NOT trigger open navigation', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('AI Architecture Review')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByRole('button', { name: 'Edytuj' });
    fireEvent.click(editButtons[1]);

    await waitFor(() => {
      expect(screen.getByText('Edycja Metadanych Projektu')).toBeInTheDocument();
    });

    // Navigation to dashboard was NOT triggered
    expect(screen.queryByTestId('dashboard-view')).not.toBeInTheDocument();
  });

  it('clicking Archive button opens confirmation modal and does NOT trigger open navigation', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('AI Architecture Review')).toBeInTheDocument();
    });

    const archiveButtons = screen.getAllByRole('button', { name: 'Archiwizuj' });
    fireEvent.click(archiveButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Czy na pewno chcesz zarchiwizować ten projekt?')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('dashboard-view')).not.toBeInTheDocument();
  });

  it('confirming archive on active project removes it from active list and sets fallback active project', async () => {
    const archiveSpy = vi.spyOn(projectApiService, 'archiveProject').mockImplementation(async () => {
      vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
        { ...MOCK_API_PROJECTS[0], status: 'archived' },
        MOCK_API_PROJECTS[1],
        MOCK_API_PROJECTS[2],
      ]);
      return { ...MOCK_API_PROJECTS[0], status: 'archived' };
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Lean Management and Energy Efficiency')).toBeInTheDocument();
    });

    const archiveButtons = screen.getAllByRole('button', { name: 'Archiwizuj' });
    fireEvent.click(archiveButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Czy na pewno chcesz zarchiwizować ten projekt?')).toBeInTheDocument();
    });

    // Confirm archive
    const confirmButtons = screen.getAllByRole('button', { name: 'Zarchiwizuj Projekt' });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(archiveSpy).toHaveBeenCalledWith('lean_energy');
    });

    // active project fallback set to remaining active project (ai_architecture)
    expect(localStorage.getItem('slr_active_project_id')).toBe('ai_architecture');
  });

  it('restores archived project back to active list', async () => {
    const restoreSpy = vi.spyOn(projectApiService, 'restoreProject').mockResolvedValue({
      ...MOCK_API_PROJECTS[2],
      status: 'active',
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Zarchiwizowane (1)')).toBeInTheDocument();
    });

    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      MOCK_API_PROJECTS[0],
      MOCK_API_PROJECTS[1],
      { ...MOCK_API_PROJECTS[2], status: 'active' },
    ]);

    fireEvent.click(screen.getByText('Zarchiwizowane (1)'));

    await waitFor(() => {
      expect(screen.getByText('Archived Literature Review')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Przywróć' }));

    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith('archived_review');
    });
  });

  it('persists selected active project ID in localStorage across reloads', async () => {
    localStorage.setItem('slr_active_project_id', 'ai_architecture');

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('AI Architecture Review')).toBeInTheDocument();
    });

    expect(localStorage.getItem('slr_active_project_id')).toBe('ai_architecture');
  });
});
