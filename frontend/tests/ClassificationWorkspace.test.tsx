import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ClassificationWorkspace } from '../src/components/synthesis/ClassificationWorkspace';
import { EvidenceSynthesisPage } from '../src/pages/EvidenceSynthesisPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { synthesisApi } from '../src/services/api/synthesisApi';
import { TerminologyClassificationWorkspace } from '../src/types/synthesis';

const mockWorkspace: TerminologyClassificationWorkspace = {
  project_id: 'proj-123',
  lean_categories: [
    {
      category_id: '5s',
      name: '5S & Visual Management',
      project_id: 'proj-123',
      description: '5S workplace tools',
      display_order: 1,
    },
    {
      category_id: 'vsm',
      name: 'Value Stream Mapping',
      project_id: 'proj-123',
      description: 'VSM process mapping',
      display_order: 2,
    },
  ],
  energy_categories: [
    {
      category_id: 'elec_direct',
      name: 'Direct Electricity Reduction',
      project_id: 'proj-123',
      description: 'kWh electricity reduction',
      display_order: 1,
    },
  ],
  lean_terms: [
    {
      project_id: 'proj-123',
      term_type: 'lean_practice',
      source_value: '5S Visual Standard',
      occurrence_count: 3,
      publication_count: 2,
      analytical_category_id: null,
      analytical_category_name: null,
      approval_state: 'pending',
      approved_by: null,
      approved_at: null,
      mapping_id: null,
    },
    {
      project_id: 'proj-123',
      term_type: 'lean_practice',
      source_value: 'VSM Stream Analysis',
      occurrence_count: 1,
      publication_count: 1,
      analytical_category_id: 'vsm',
      analytical_category_name: 'Value Stream Mapping',
      approval_state: 'approved',
      approved_by: 'reviewer-1',
      approved_at: '2026-08-15T08:00:00Z',
      mapping_id: '00000000-0000-0000-0000-000000000001',
    },
  ],
  energy_terms: [
    {
      project_id: 'proj-123',
      term_type: 'energy_effect',
      source_value: '15% electricity consumption reduction',
      occurrence_count: 2,
      publication_count: 2,
      analytical_category_id: 'elec_direct',
      analytical_category_name: 'Direct Electricity Reduction',
      approval_state: 'pending',
      approved_by: null,
      approved_at: null,
      mapping_id: '00000000-0000-0000-0000-000000000002',
    },
  ],
  stats: {
    total_lean_terms: 2,
    total_energy_terms: 1,
    total_terms: 3,
    mapped_count: 2,
    approved_count: 1,
  },
};

describe('ClassificationWorkspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders summary stats and Lean source terms by default', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue(mockWorkspace);

    render(<ClassificationWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Terminology Classification Workspace')).toBeInTheDocument();
    });

    // Check stats
    expect(screen.getByText('Lean Practice Terms')).toBeInTheDocument();
    expect(screen.getByText('Energy Effect Terms')).toBeInTheDocument();

    // Check source terms table
    expect(screen.getByText('5S Visual Standard')).toBeInTheDocument();
    expect(screen.getByText('VSM Stream Analysis')).toBeInTheDocument();
    expect(screen.getAllByText('Unmapped').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Approved').length).toBeGreaterThan(0);
  });

  it('switches to Energy Effects tab and shows energy terms', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue(mockWorkspace);

    render(<ClassificationWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('5S Visual Standard')).toBeInTheDocument();
    });

    const energyTabBtn = screen.getByTestId('energy-tab-btn');
    fireEvent.click(energyTabBtn);

    await waitFor(() => {
      expect(screen.getByText('15% electricity consumption reduction')).toBeInTheDocument();
      expect(screen.getAllByText('Pending Approval').length).toBeGreaterThan(0);
    });
  });

  it('selects an analytical category for an unmapped term', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue(mockWorkspace);
    const setMappingSpy = vi.spyOn(synthesisApi, 'setTermMapping').mockResolvedValue({
      mapping_id: 'map-new',
      project_id: 'proj-123',
      term_type: 'lean_practice',
      source_value: '5S Visual Standard',
      analytical_category_id: '5s',
      approval_state: 'pending',
      approved_by: null,
      approved_at: null,
    });

    render(<ClassificationWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('5S Visual Standard')).toBeInTheDocument();
    });

    const selects = screen.getAllByRole('combobox');
    // First select is status filter, second is category select for 5S Visual Standard
    fireEvent.change(selects[1], { target: { value: '5s' } });

    await waitFor(() => {
      expect(setMappingSpy).toHaveBeenCalledWith('proj-123', {
        term_type: 'lean_practice',
        source_value: '5S Visual Standard',
        analytical_category_id: '5s',
      });
    });
  });

  it('explicitly approves a pending mapping', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue(mockWorkspace);
    const approveSpy = vi.spyOn(synthesisApi, 'approveTermMapping').mockResolvedValue({
      mapping_id: '00000000-0000-0000-0000-000000000002',
      project_id: 'proj-123',
      term_type: 'energy_effect',
      source_value: '15% electricity consumption reduction',
      analytical_category_id: 'elec_direct',
      approval_state: 'approved',
      approved_by: 'reviewer-1',
      approved_at: '2026-08-15T08:30:00Z',
    });

    render(<ClassificationWorkspace projectId="proj-123" />);

    // Switch to Energy tab where pending mapping is located
    await waitFor(() => {
      expect(screen.getByTestId('energy-tab-btn')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('energy-tab-btn'));

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Approve'));

    await waitFor(() => {
      expect(approveSpy).toHaveBeenCalledWith('proj-123', {
        term_type: 'energy_effect',
        source_value: '15% electricity consumption reduction',
        reviewer_id: 'reviewer-1',
      });
    });
  });

  it('manages analytical categories through modal', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue(mockWorkspace);
    const createCatSpy = vi.spyOn(synthesisApi, 'createLeanCategory').mockResolvedValue({
      category_id: 'kaizen',
      name: 'Kaizen & Continuous Improvement',
      project_id: 'proj-123',
      description: 'Continuous improvement',
      display_order: 3,
    });

    render(<ClassificationWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Manage Categories/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Manage Categories/i }));

    expect(screen.getByText('Manage Lean Practice Categories')).toBeInTheDocument();

    const idInput = screen.getByPlaceholderText('e.g. 5s');
    const nameInput = screen.getByPlaceholderText('e.g. 5S & Visual Management');

    fireEvent.change(idInput, { target: { value: 'kaizen' } });
    fireEvent.change(nameInput, { target: { value: 'Kaizen & Continuous Improvement' } });

    const submitBtn = screen.getByText('Add Category');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(createCatSpy).toHaveBeenCalledWith('proj-123', {
        category_id: 'kaizen',
        name: 'Kaizen & Continuous Improvement',
        description: null,
        display_order: 0,
      });
    });
  });

  it('renders EvidenceSynthesisPage navigation to ClassificationWorkspace', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue(mockWorkspace);

    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/proj-123/synthesis']}>
          <Routes>
            <Route path="/projects/:projectId/synthesis" element={<EvidenceSynthesisPage />} />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Evidence Synthesis')).toBeInTheDocument();
      expect(screen.getByText('Terminology Classification')).toBeInTheDocument();
      expect(screen.getByText('Terminology Classification Workspace')).toBeInTheDocument();
    });
  });
});
