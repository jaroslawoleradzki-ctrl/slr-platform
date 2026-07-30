import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { AppShell } from '../src/components/layout/AppShell';
import { SearchStrategyPage } from '../src/pages/SearchStrategyPage';
import { projectApiService } from '../src/services/api/projectApi';

describe('Navigation Routing', () => {
  it('renders search strategy page under /search route', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
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

    expect(await screen.findByRole('heading', { name: /Definicja strategii wyszukiwania/i })).toBeInTheDocument();
    const actionBar = screen.getByTestId('search-strategy-action-bar');
    expect(actionBar).toBeVisible();
    expect(actionBar).toContainElement(screen.getByRole('button', { name: 'Zapisz' }));
    expect(actionBar).toContainElement(screen.getByRole('button', { name: 'Szukaj' }));
    expect(screen.queryByRole('button', { name: /Powtórz|Ponów/ })).not.toBeInTheDocument();
    expect(screen.getByTestId('boolean-query-preview')).toHaveTextContent('Dodaj grupy i terminy');
  });
});
