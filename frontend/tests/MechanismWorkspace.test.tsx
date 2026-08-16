import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { MechanismWorkspace } from '../src/components/synthesis/MechanismWorkspace';
import { EvidenceSynthesisPage } from '../src/pages/EvidenceSynthesisPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { synthesisApi } from '../src/services/api/synthesisApi';
import { MechanismWorkspaceData } from '../src/types/synthesis';

const mockWorkspaceData: MechanismWorkspaceData = {
  project_id: 'proj-123',
  categories: [
    {
      category_id: 'idle_reduction',
      name: 'Idle-Time Reduction',
      project_id: 'proj-123',
      description: 'Minimizing standby power consumption.',
      display_order: 1,
    },
  ],
  pathways: [
    {
      pathway: {
        pathway_id: 'pathway-1',
        project_id: 'proj-123',
        analytical_relation_id: 'rel-1',
        group_item_id: 'group-item-1',
        publication_id: 'pub-1',
        latest_revision_id: 'rev-1',
        source_mechanism_text: 'Turned off conveyor belts during shift changes to cut electricity draw.',
        analytical_mechanism_category_id: 'idle_reduction',
        is_review_synthesized: false,
        approval_state: 'approved',
        approved_by: 'reviewer_1',
        approved_at: '2024-01-01T00:00:00Z',
        notes: 'Verbatim quote from section 3.2.',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      publication_title: 'Lean Manufacturing in Auto Plants',
      publication_year: 2023,
      source_practice: '5S Workstations',
      source_effect: 'Electricity Draw',
      analytical_lean_category_id: '5s',
      analytical_lean_category_name: '5S & Visual Management',
      analytical_energy_category_id: 'elec',
      analytical_energy_category_name: 'Direct Electricity',
      analytical_mechanism_category_name: 'Idle-Time Reduction',
      direction: 'positive',
      evidence_character: 'empirical',
      qa_profile: {
        assessment_id: 'qa-1',
        template_id: 'tmpl-1',
        reviewer_id: 'reviewer_1',
        criteria_assessments: [
          {
            criterion_id: 'c-1',
            question_text: 'QA1: Clear study objectives?',
            response_value: 'Yes',
            justification: 'Objectives detailed in intro.',
          },
        ],
      },
    },
  ],
  synthesis_chains: [
    {
      lean_category_id: '5s',
      lean_category_name: '5S & Visual Management',
      mechanism_category_id: 'idle_reduction',
      mechanism_category_name: 'Idle-Time Reduction',
      energy_category_id: 'elec',
      energy_category_name: 'Direct Electricity',
      pathway_count: 1,
      publication_count: 1,
      relation_count: 1,
      pathways: [],
    },
  ],
  stats: {
    total_pathways: 1,
    mapped_count: 1,
    unmapped_count: 0,
    approved_count: 1,
    total_publications: 1,
  },
};

describe('MechanismWorkspace Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders workspace with KPI stats, category tags, and pathway cards', async () => {
    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockResolvedValue(mockWorkspaceData);

    render(<MechanismWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Mechanism Synthesis & Impact Pathways')).toBeInTheDocument();
    });

    expect(screen.getByText('Mapped Categories')).toBeInTheDocument();
    expect(screen.getAllByText('Idle-Time Reduction').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Turned off conveyor belts during shift changes to cut electricity draw.')).toBeInTheDocument();
    expect(screen.getByText('SOURCE_REPORTED')).toBeInTheDocument();
    expect(screen.getByText('APPROVED')).toBeInTheDocument();
  });

  it('handles category creation modal submission', async () => {
    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockResolvedValue(mockWorkspaceData);
    const createSpy = vi.spyOn(synthesisApi, 'createMechanismCategory').mockResolvedValue({
      category_id: 'thermal_recovery',
      name: 'Thermal Heat Recovery',
      project_id: 'proj-123',
      description: 'Recovering flue heat.',
      display_order: 2,
    });

    render(<MechanismWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('add-mechanism-category-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('add-mechanism-category-btn'));

    expect(screen.getByText('Create Mechanism Category')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('category-id-input'), { target: { value: 'thermal_recovery' } });
    fireEvent.change(screen.getByTestId('category-name-input'), { target: { value: 'Thermal Heat Recovery' } });
    fireEvent.change(screen.getByTestId('category-desc-input'), { target: { value: 'Recovering flue heat.' } });

    fireEvent.click(screen.getByTestId('save-category-submit-btn'));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('proj-123', {
        category_id: 'thermal_recovery',
        name: 'Thermal Heat Recovery',
        description: 'Recovering flue heat.',
      });
    });
  });

  it('handles pathway category assignment and approval', async () => {
    const unapprovedData: MechanismWorkspaceData = {
      ...mockWorkspaceData,
      pathways: [
        {
          ...mockWorkspaceData.pathways[0],
          pathway: {
            ...mockWorkspaceData.pathways[0].pathway,
            analytical_mechanism_category_id: null,
            approval_state: 'pending',
          },
        },
      ],
      stats: {
        ...mockWorkspaceData.stats,
        mapped_count: 0,
        unmapped_count: 1,
        approved_count: 0,
      },
    };

    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockResolvedValue(unapprovedData);
    const assignSpy = vi.spyOn(synthesisApi, 'assignMechanismPathway').mockResolvedValue({} as any);

    render(<MechanismWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('select-category-pathway-1')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('select-category-pathway-1'), {
      target: { value: 'idle_reduction' },
    });

    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith('proj-123', 'pathway-1', {
        category_id: 'idle_reduction',
        is_review_synthesized: false,
      });
    });
  });

  it('toggles QA criterion profile accordion', async () => {
    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockResolvedValue(mockWorkspaceData);

    render(<MechanismWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Show QA Criterion Profile (Phase 8)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Show QA Criterion Profile (Phase 8)'));

    await waitFor(() => {
      expect(screen.getByText('QA1: Clear study objectives?')).toBeInTheDocument();
      expect(screen.getByText('Hide QA Profile')).toBeInTheDocument();
    });
  });

  it('navigates seamlessly across Classification, Matrix, and Mechanism tabs in EvidenceSynthesisPage', async () => {
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
    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockResolvedValue(mockWorkspaceData);

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

    // Initial tab is 1. Terminology Classification
    expect(screen.getByTestId('synthesis-tab-classification')).toBeInTheDocument();
    expect(screen.getByTestId('synthesis-tab-matrix')).toBeInTheDocument();
    expect(screen.getByTestId('synthesis-tab-mechanisms')).toBeInTheDocument();

    // Click Matrix Tab
    fireEvent.click(screen.getByTestId('synthesis-tab-matrix'));
    await waitFor(() => {
      expect(screen.getByText(/Lean Practice × Energy Effect/i)).toBeInTheDocument();
    });

    // Click Mechanisms Tab
    fireEvent.click(screen.getByTestId('synthesis-tab-mechanisms'));
    await waitFor(() => {
      expect(screen.getByText('Mechanism Synthesis & Impact Pathways')).toBeInTheDocument();
    });
  });

  it('renders error state gracefully when API fails', async () => {
    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockRejectedValue(new Error('Network error'));

    render(<MechanismWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Error loading mechanism synthesis workspace')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });
});
