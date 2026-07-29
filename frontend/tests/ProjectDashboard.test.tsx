import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { ProjectDashboardPage } from '../src/pages/ProjectDashboardPage';

describe('ProjectDashboardPage', () => {
  it('renders Next Action card and dynamic PRISMA flow chart', async () => {
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dashboard']}>
          <Routes>
            <Route path="/projects/:projectId/dashboard" element={<ProjectDashboardPage />} />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Kolejny Krok Procesu/i)).toBeInTheDocument();
    expect(screen.getByText(/Dynamic PRISMA 2020 Flow Diagram/i)).toBeInTheDocument();
    expect(screen.getByText(/Ocena Grup Duplikatów/i)).toBeInTheDocument();
  });
});
