import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ContextWorkspace } from '../src/components/synthesis/ContextWorkspace';
import { EvidenceSynthesisPage } from '../src/pages/EvidenceSynthesisPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { synthesisApi } from '../src/services/api/synthesisApi';
import { ContextWorkspaceData } from '../src/types/synthesis';

const mockWorkspaceData: ContextWorkspaceData = {
  project_id: 'proj-123',
  categories: [
    {
      category_id: 'market_competition',
      name: 'Market Competition',
      project_id: 'proj-123',
      description: 'Competitive pressure influencing lean–energy outcomes.',
      display_order: 1,
    },
  ],
  assignments: [
    {
      assignment_id: 'link-1',
      project_id: 'proj-123',
      analytical_relation_id: 'rel-1',
      group_item_id: 'group-item-1',
      publication_id: 'pub-1',
      latest_revision_id: 'rev-1',
      source_context_text: 'Adoption was higher in deregulated electricity markets.',
      analytical_context_category_id: 'market_competition',
      context_impact: 'STRENGTHEN',
      approval_state: 'pending',
      approved_by: null,
      approved_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      assignment_id: 'link-2',
      project_id: 'proj-123',
      analytical_relation_id: 'rel-2',
      group_item_id: 'group-item-2',
      publication_id: 'pub-2',
      latest_revision_id: 'rev-2',
      source_context_text: '',
      analytical_context_category_id: null,
      context_impact: 'ENABLE',
      approval_state: 'pending',
      approved_by: null,
      approved_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ],
  stats: {
    context_evidence_count: 1,
    distinct_publication_count: 2,
    distinct_analytical_relation_count: 2,
    distinct_mechanism_pathway_count: 1,
  },
};

describe('ContextWorkspace Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders workspace with KPI stats, taxonomy, and assignment rows', async () => {
    vi.spyOn(synthesisApi, 'getContextWorkspace').mockResolvedValue(mockWorkspaceData);

    render(<ContextWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Context Synthesis & Moderating Factors')).toBeInTheDocument();
    });

    expect(screen.getByText('Context Evidence')).toBeInTheDocument();
    expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Market Competition').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Adoption was higher in deregulated electricity markets.')).toBeInTheDocument();
    expect(screen.getByText('No moderating conditions extracted for this relation')).toBeInTheDocument();
    expect(screen.getByTestId('context-state-link-1')).toHaveTextContent('pending');
    expect(screen.getByText('unassigned')).toBeInTheDocument();
  });

  it('handles context category creation modal submission', async () => {
    vi.spyOn(synthesisApi, 'getContextWorkspace').mockResolvedValue(mockWorkspaceData);
    const createSpy = vi.spyOn(synthesisApi, 'createContextCategory').mockResolvedValue({
      category_id: 'regulatory_support',
      name: 'Regulatory Support',
      project_id: 'proj-123',
      description: 'Policy incentives accelerating adoption.',
      display_order: 2,
    });

    render(<ContextWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('add-context-category-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('add-context-category-btn'));

    expect(screen.getByTestId('context-category-id-input')).toBeInTheDocument();
    expect(screen.getByText('Create Category')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('context-category-id-input'), { target: { value: 'regulatory_support' } });
    fireEvent.change(screen.getByTestId('context-category-name-input'), { target: { value: 'Regulatory Support' } });
    fireEvent.change(screen.getByTestId('context-category-desc-input'), {
      target: { value: 'Policy incentives accelerating adoption.' },
    });

    fireEvent.click(screen.getByTestId('save-context-category-submit-btn'));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('proj-123', {
        category_id: 'regulatory_support',
        name: 'Regulatory Support',
        description: 'Policy incentives accelerating adoption.',
      });
    });
  });

  it('remaps a categorized assignment when the category changes', async () => {
    vi.spyOn(synthesisApi, 'getContextWorkspace').mockResolvedValue(mockWorkspaceData);
    const remapSpy = vi.spyOn(synthesisApi, 'remapContextAssignment').mockResolvedValue({} as any);

    render(<ContextWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('context-category-link-1')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('context-category-link-1'), {
      target: { value: 'market_competition' },
    });

    await waitFor(() => {
      expect(remapSpy).toHaveBeenCalledWith('proj-123', 'link-1', {
        category_id: 'market_competition',
        context_impact: 'STRENGTHEN',
      });
    });
  });

  it('changes context impact via the impact select', async () => {
    vi.spyOn(synthesisApi, 'getContextWorkspace').mockResolvedValue(mockWorkspaceData);
    const remapSpy = vi.spyOn(synthesisApi, 'remapContextAssignment').mockResolvedValue({} as any);

    render(<ContextWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('context-impact-link-1')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('context-impact-link-1'), {
      target: { value: 'WEAKEN' },
    });

    await waitFor(() => {
      expect(remapSpy).toHaveBeenCalledWith('proj-123', 'link-1', {
        category_id: 'market_competition',
        context_impact: 'WEAKEN',
      });
    });
  });

  it('navigates to the Context tab within EvidenceSynthesisPage', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue({
      project_id: 'proj-123',
      lean_categories: [],
      energy_categories: [],
      lean_terms: [],
      energy_terms: [],
      stats: {
        total_lean_terms: 0,
        total_energy_terms: 0,
        total_terms: 0,
        mapped_count: 0,
        approved_count: 0,
      },
    });
    vi.spyOn(synthesisApi, 'getMatrix').mockResolvedValue({
      project_id: 'proj-123',
      lean_categories: [],
      energy_categories: [],
      cells: [],
      total_relations: 0,
      total_publications: 0,
      unclassified_relations_count: 0,
    });
    vi.spyOn(synthesisApi, 'getContextWorkspace').mockResolvedValue(mockWorkspaceData);

    render(
      <MemoryRouter initialEntries={['/projects/proj-123/synthesis']}>
        <Routes>
          <Route
            path="/projects/:projectId/synthesis"
            element={
              <ProjectProvider>
                <EvidenceSynthesisPage />
              </ProjectProvider>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByTestId('synthesis-tab-context')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('synthesis-tab-context'));

    await waitFor(() => {
      expect(screen.getByText('Context Synthesis & Moderating Factors')).toBeInTheDocument();
    });
  });

  it('renders error state gracefully when API fails', async () => {
    vi.spyOn(synthesisApi, 'getContextWorkspace').mockRejectedValue(new Error('Network error'));

    render(<ContextWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Error loading context synthesis workspace')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });
});