import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { projectApiService } from '../src/services/api/projectApi';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { WorkflowStepper } from '../src/components/workflow/WorkflowStepper';
import { RUNTIME_MODE } from '../src/config/version';

const TestComponent = () => {
  const { projects, activeProject, loading, error } = useProject();
  if (loading) return <div>Ładowanie...</div>;
  return (
    <>
      {error ? <div>Błąd: {error}</div> : null}
      <div data-testid="project-count">{projects.length}</div>
      <div data-testid="active-project">{activeProject ? activeProject.title : 'Brak aktywnego'}</div>
      {projects.length === 0 ? <div>Brak projektów</div> : null}
      <WorkflowStepper />
    </>
  );
};

const renderProvider = (path = '/projects') => render(
  <ProjectProvider>
    <MemoryRouter initialEntries={[path]}>
      <TestComponent />
    </MemoryRouter>
  </ProjectProvider>
);

const realProject = {
  id: 'project-real-1',
  title: 'Real Project',
  description: 'Real project description',
  protocolVersion: '1.0',
  status: 'active' as const,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
  nextAction: { title: '', description: '', targetStageId: 'search' as const, actionLabel: '', severity: 'normal' as const },
  conceptGroups: [],
  searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
  providers: [], imports: [], normalization: [],
  deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' as const },
  duplicateGroups: [],
  screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' as const },
  qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' as const },
  prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
};

describe('No Mock Projects Fallback Safety Guarantee', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('projectApiService.getProjects throws Error on network failure and does not return mock projects', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(projectApiService.getProjects()).rejects.toThrow(
      'Nie udało się połączyć z backendem. Sprawdź połączenie.'
    );
  });

  it('projectApiService.getProjects throws Error on HTTP 500 error response and does not return mock projects', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Internal Server Error' }), { status: 500 })
    );

    await expect(projectApiService.getProjects()).rejects.toThrow(
      'Internal Server Error (HTTP 500).'
    );
  });

  it('ProjectProvider displays an API error with no projects, active project, or project links', async () => {
    localStorage.setItem('slr_active_project_id', 'stale-project');
    vi.spyOn(projectApiService, 'getProjects').mockRejectedValue(
      new Error('Błąd połączenia z serwerem API')
    );

    renderProvider();

    await waitFor(() => {
      expect(screen.getByText(/Błąd: Błąd połączenia z serwerem API/i)).toBeInTheDocument();
    });

    expect(screen.getByTestId('project-count')).toHaveTextContent('0');
    expect(screen.getByTestId('active-project')).toHaveTextContent('Brak aktywnego');
    expect(localStorage.getItem('slr_active_project_id')).toBeNull();
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.queryByText(/Lean Management/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI Architecture/i)).not.toBeInTheDocument();
  });

  it('ProjectProvider renders an empty list with no active project or project links', async () => {
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([]);

    renderProvider();

    await waitFor(() => {
      expect(screen.getByText('Brak projektów')).toBeInTheDocument();
    });

    expect(screen.getByTestId('project-count')).toHaveTextContent('0');
    expect(screen.getByTestId('active-project')).toHaveTextContent('Brak aktywnego');
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.queryByText(/Lean Management/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI Architecture/i)).not.toBeInTheDocument();
  });

  it('clears a stale saved project ID without selecting another project', async () => {
    localStorage.setItem('slr_active_project_id', 'deleted-project');
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([realProject]);

    renderProvider();

    await waitFor(() => {
      expect(screen.getByTestId('project-count')).toHaveTextContent('1');
    });

    expect(screen.getByTestId('active-project')).toHaveTextContent('Brak aktywnego');
    expect(localStorage.getItem('slr_active_project_id')).toBeNull();
  });

  it('renders and activates a real project with routes containing its real ID', async () => {
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([realProject]);

    renderProvider('/projects/project-real-1/dashboard');

    await waitFor(() => {
      expect(screen.getByTestId('project-count')).toHaveTextContent('1');
    });

    expect(screen.getByTestId('active-project')).toHaveTextContent('Real Project');
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThan(0);
    expect(links.every((link) => link.getAttribute('href')?.includes('/projects/project-real-1/'))).toBe(true);
    expect(links.some((link) => link.getAttribute('href')?.includes('/projects//'))).toBe(false);
  });

  it('does not mention Hybrid Data Mode or Demo Project Metadata in RUNTIME_MODE', () => {
    expect(RUNTIME_MODE).not.toContain('Hybrid Data Mode');
    expect(RUNTIME_MODE).not.toContain('Demo Project Metadata');
  });
});
