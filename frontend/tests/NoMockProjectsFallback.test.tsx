import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { projectApiService } from '../src/services/api/projectApi';
import { ProjectProvider, useProject } from '../src/context/ProjectContext';
import { RUNTIME_MODE } from '../src/config/version';

const TestComponent = () => {
  const { projects, activeProject, loading, error } = useProject();
  if (loading) return <div>Ładowanie...</div>;
  if (error) return <div>Błąd: {error}</div>;
  if (projects.length === 0) return <div>Brak projektów</div>;
  return (
    <div>
      <div data-testid="active-project">{activeProject ? activeProject.title : 'Brak aktywnego'}</div>
      <ul>
        {projects.map((p) => (
          <li key={p.id}>{p.title}</li>
        ))}
      </ul>
    </div>
  );
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

  it('ProjectProvider displays error message and 0 projects when API fails', async () => {
    vi.spyOn(projectApiService, 'getProjects').mockRejectedValue(
      new Error('Błąd połączenia z serwerem API')
    );

    render(
      <ProjectProvider>
        <MemoryRouter>
          <TestComponent />
        </MemoryRouter>
      </ProjectProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Błąd: Błąd połączenia z serwerem API/i)).toBeInTheDocument();
    });

    expect(screen.queryByText(/Lean Management/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI Architecture/i)).not.toBeInTheDocument();
  });

  it('ProjectProvider renders empty list when DB has 0 projects', async () => {
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([]);

    render(
      <ProjectProvider>
        <MemoryRouter>
          <TestComponent />
        </MemoryRouter>
      </ProjectProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Brak projektów')).toBeInTheDocument();
    });

    expect(screen.queryByText(/Lean Management/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI Architecture/i)).not.toBeInTheDocument();
  });

  it('does not mention Hybrid Data Mode or Demo Project Metadata in RUNTIME_MODE', () => {
    expect(RUNTIME_MODE).not.toContain('Hybrid Data Mode');
    expect(RUNTIME_MODE).not.toContain('Demo Project Metadata');
  });
});
