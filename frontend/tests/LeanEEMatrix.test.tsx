import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LeanEEMatrix } from '../src/components/synthesis/LeanEEMatrix';
import { EvidenceSynthesisPage } from '../src/pages/EvidenceSynthesisPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { synthesisApi } from '../src/services/api/synthesisApi';
import {
  MatrixCellDetail,
  SynthesisMatrix,
} from '../src/types/synthesis';

const mockMatrix: SynthesisMatrix = {
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
      category_id: 'elec',
      name: 'Direct Electricity',
      project_id: 'proj-123',
      description: 'Electricity consumption',
      display_order: 1,
    },
    {
      category_id: 'fuel',
      name: 'Thermal Energy',
      project_id: 'proj-123',
      description: 'Gas / thermal fuels',
      display_order: 2,
    },
  ],
  cells: [
    {
      lean_category_id: '5s',
      lean_category_name: '5S & Visual Management',
      energy_category_id: 'elec',
      energy_category_name: 'Direct Electricity',
      relation_count: 2,
      publication_count: 1,
      direction_distribution: { positive: 2 },
      evidence_character_distribution: { empirical: 2 },
    },
    {
      lean_category_id: '5s',
      lean_category_name: '5S & Visual Management',
      energy_category_id: 'fuel',
      energy_category_name: 'Thermal Energy',
      relation_count: 0,
      publication_count: 0,
      direction_distribution: {},
      evidence_character_distribution: {},
    },
    {
      lean_category_id: 'vsm',
      lean_category_name: 'Value Stream Mapping',
      energy_category_id: 'elec',
      energy_category_name: 'Direct Electricity',
      relation_count: 1,
      publication_count: 1,
      direction_distribution: { positive: 1 },
      evidence_character_distribution: { estimated: 1 },
    },
    {
      lean_category_id: 'vsm',
      lean_category_name: 'Value Stream Mapping',
      energy_category_id: 'fuel',
      energy_category_name: 'Thermal Energy',
      relation_count: 0,
      publication_count: 0,
      direction_distribution: {},
      evidence_character_distribution: {},
    },
  ],
  total_relations: 3,
  total_publications: 2,
  unclassified_relations_count: 1,
};

const mockCellDetail: MatrixCellDetail = {
  lean_category: {
    category_id: '5s',
    name: '5S & Visual Management',
    project_id: 'proj-123',
    description: '5S tools',
    display_order: 1,
  },
  energy_category: {
    category_id: 'elec',
    name: 'Direct Electricity',
    project_id: 'proj-123',
    description: 'Electricity consumption',
    display_order: 1,
  },
  relation_count: 2,
  publication_count: 1,
  direction_distribution: { positive: 2 },
  evidence_character_distribution: { empirical: 2 },
  relations: [
    {
      relation: {
        relation_id: 'rel-1',
        project_id: 'proj-123',
        publication_id: 'pub-1',
        latest_revision_id: 'rev-1',
        group_item_id: 'group-uuid-1',
        item_index: 1,
        source_practice: '5S Visual Controls',
        analytical_lean_category_id: '5s',
        source_effect: 'Machine Standby Power',
        analytical_energy_category_id: 'elec',
        direction: 'positive',
        magnitude: 50.0,
        original_unit: 'kWh',
        converted_value: null,
        evidence_character: 'empirical',
        context_summary: null,
        approval_state: 'approved',
        created_at: '2026-08-15T00:00:00Z',
        updated_at: '2026-08-15T00:00:00Z',
      },
      publication_title: 'Energy Efficiency through 5S in Automotive Plant',
      publication_year: 2023,
      source_quote: 'Shutting down inactive machines saved 50 kWh daily.',
      source_page: '14',
      source_section: 'Results',
      qa_profile: {
        assessment_id: 'qa-1',
        template_id: 'tmpl-1',
        reviewer_id: 'reviewer-alpha',
        criteria_assessments: [
          {
            criterion_id: 'crit-1',
            question_text: 'Are measurement methods explicitly described?',
            response_value: 'YES',
            justification: 'Metered energy data logged hourly.',
          },
        ],
      },
    },
  ],
};

describe('LeanEEMatrix Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders matrix grid with Lean rows and Energy columns', async () => {
    vi.spyOn(synthesisApi, 'getMatrix').mockResolvedValue(mockMatrix);

    render(<LeanEEMatrix projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Lean Practice × Energy Effect Analytical Matrix')).toBeInTheDocument();
    });

    // Check row and column headers
    expect(screen.getByText('5S & Visual Management')).toBeInTheDocument();
    expect(screen.getByText('Value Stream Mapping')).toBeInTheDocument();
    expect(screen.getByText('Direct Electricity')).toBeInTheDocument();
    expect(screen.getByText('Thermal Energy')).toBeInTheDocument();

    // Check counts
    expect(screen.getByText('Total Synthesized Relations')).toBeInTheDocument();
    expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);
  });

  it('opens drill-down modal on cell click and allows QA expansion and unit conversion', async () => {
    vi.spyOn(synthesisApi, 'getMatrix').mockResolvedValue(mockMatrix);
    vi.spyOn(synthesisApi, 'getCellDetail').mockResolvedValue(mockCellDetail);
    vi.spyOn(synthesisApi, 'convertUnit').mockResolvedValue({
      transformed_value: 180.0,
      transformed_unit: 'MJ',
      conversion_rule: '1 kWh = 3.6 MJ',
    });
    vi.spyOn(synthesisApi, 'saveConvertedUnit').mockResolvedValue({
      ...mockCellDetail.relations[0].relation,
      converted_value: {
        transformed_value: 180.0,
        transformed_unit: 'MJ',
        conversion_rule: '1 kWh = 3.6 MJ',
      },
    });

    render(<LeanEEMatrix projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('matrix-cell-5s-elec')).toBeInTheDocument();
    });

    // Click on (5s, elec) cell
    fireEvent.click(screen.getByTestId('matrix-cell-5s-elec'));

    // Modal should appear
    await waitFor(() => {
      expect(screen.getByText('Matrix Cell Detail')).toBeInTheDocument();
      expect(screen.getByText('Energy Efficiency through 5S in Automotive Plant')).toBeInTheDocument();
      expect(screen.getByText('5S Visual Controls')).toBeInTheDocument();
      expect(screen.getByText('Machine Standby Power')).toBeInTheDocument();
      expect(screen.getByText('50 kWh')).toBeInTheDocument();
    });

    // Expand QA Profile accordion
    const qaButton = screen.getByText(/QA Profile/);
    fireEvent.click(qaButton);

    await waitFor(() => {
      expect(screen.getByText('QA1: Are measurement methods explicitly described?')).toBeInTheDocument();
      expect(screen.getByText('Metered energy data logged hourly.', { exact: false })).toBeInTheDocument();
    });

    // Preview unit conversion
    const previewBtn = screen.getByText('Preview Calculation');
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(screen.getByText(/Preview:/)).toBeInTheDocument();
      expect(screen.getByText('Save Converted Value')).toBeInTheDocument();
    });

    // Save conversion
    const saveBtn = screen.getByText('Save Converted Value');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText('Converted value saved successfully')).toBeInTheDocument();
    });

    // Close modal
    fireEvent.click(screen.getByTestId('close-cell-modal-btn'));
    await waitFor(() => {
      expect(screen.queryByText('Matrix Cell Detail')).not.toBeInTheDocument();
    });
  });

  it('renders tab navigation in EvidenceSynthesisPage and switches between Classification and Matrix', async () => {
    vi.spyOn(synthesisApi, 'getWorkspace').mockResolvedValue({
      project_id: 'proj-123',
      lean_categories: mockMatrix.lean_categories,
      energy_categories: mockMatrix.energy_categories,
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
    vi.spyOn(synthesisApi, 'getMatrix').mockResolvedValue(mockMatrix);

    render(
      <MemoryRouter initialEntries={['/projects/proj-123/synthesis']}>
        <ProjectProvider>
          <Routes>
            <Route path="/projects/:projectId/synthesis" element={<EvidenceSynthesisPage />} />
          </Routes>
        </ProjectProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('synthesis-tab-classification')).toBeInTheDocument();
      expect(screen.getByTestId('synthesis-tab-matrix')).toBeInTheDocument();
    });

    // Switch to Matrix tab
    fireEvent.click(screen.getByTestId('synthesis-tab-matrix'));

    await waitFor(() => {
      expect(screen.getByText('Lean Practice × Energy Effect Analytical Matrix')).toBeInTheDocument();
    });
  });
});
