import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { AppShell } from '../src/components/layout/AppShell';
import { projectApiService } from '../src/services/api/projectApi';
import { SLRProject } from '../src/types';

const TEST_PROJECT = {
  id: 'project-shell',
  title: 'Shell Test Project',
  protocolVersion: '1.0',
  status: 'active',
} as SLRProject;

describe('AppShell Component', () => {
  it('renders application brand header, project title and sidebar navigation', async () => {
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([TEST_PROJECT]);
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/project-shell/dashboard']}>
          <Routes>
            <Route path="/projects/:projectId" element={<AppShell />}>
              <Route path="dashboard" element={<div>Dashboard Content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText('SLR PLATFORM')).toBeInTheDocument();
    expect(screen.getAllByText(/1. Search Strategy/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4. Deduplication/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /5\. Screening/i })).toHaveLength(2);
    screen.getAllByRole('link', { name: /5\. Screening/i }).forEach((link) => {
      expect(link).toHaveAttribute('href', '/projects/project-shell/screen/title-abstract');
    });
    expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  });
});
