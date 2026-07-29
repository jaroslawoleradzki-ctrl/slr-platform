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
    const actionBar = screen.getByTestId('search-strategy-action-bar');
    expect(actionBar).toBeVisible();
    expect(actionBar).toContainElement(screen.getByRole('button', { name: 'Wykonaj' }));
    expect(actionBar).toContainElement(screen.getByRole('button', { name: 'Powtórz' }));
    expect(screen.getAllByLabelText(/Nazwa grupy/).length).toBeGreaterThan(1);
    expect(screen.getAllByTestId('concept-term-tag').length).toBeGreaterThan(1);
    expect(screen.getAllByTestId('group-operator-separator').length).toBeGreaterThan(0);
    expect(screen.getByTestId('boolean-query-preview')).toHaveTextContent('Lean Management');
    expect(screen.getByText('Wyniki wyszukiwania')).toBeInTheDocument();
    expect(screen.getByText('Brak wykonanych wyszukiwań.')).toBeInTheDocument();
  });
});
