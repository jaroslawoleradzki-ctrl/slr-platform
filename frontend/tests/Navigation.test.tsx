import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { AppShell } from '../src/components/layout/AppShell';
import { SearchStrategyPage } from '../src/pages/SearchStrategyPage';

describe('Navigation Routing', () => {
  it('renders search strategy page under /search route', async () => {
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/search']}>
          <Routes>
            <Route path="/projects/:projectId" element={<AppShell />}>
              <Route path="search" element={<SearchStrategyPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(await screen.findByText(/Definicja Strategii Wyszukiwania/i)).toBeInTheDocument();
  });
});
