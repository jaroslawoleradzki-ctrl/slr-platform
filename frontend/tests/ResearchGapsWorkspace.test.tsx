import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ResearchGapsWorkspace } from '../src/components/synthesis/ResearchGapsWorkspace';
import { EvidenceSynthesisPage } from '../src/pages/EvidenceSynthesisPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { synthesisApi } from '../src/services/api/synthesisApi';
import { ResearchGapWorkspaceData } from '../src/types/synthesis';

const mockWorkspaceData: ResearchGapWorkspaceData = {
  project_id: 'proj-123',
  gaps: [
    {
      gap: {
        gap_id: 'gap-1',
        project_id: 'proj-123',
        gap_type: 'mechanism',
        title: 'Compressed Air Efficiency vs SMED Interaction',
        rationale:
          'No synthesis studies examine the interaction between SMED setup-time reductions and compressed air leakage losses; linked matrix evidence is sparse.',
        researcher_id: 'lead_researcher',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      links: [
        {
          link_id: 'link-1',
          project_id: 'proj-123',
          gap_id: 'gap-1',
          link_type: 'analytical_relation',
          target_id: 'rel-1',
          group_item_id: 'group-item-1',
          publication_id: 'pub-1',
          latest_revision_id: 'rev-1',
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
    },
  ],
  stats: {
    total_gaps: 1,
    thematic_count: 0,
    mechanism_count: 1,
    methodological_count: 0,
    contextual_count: 0,
    inconsistent_evidence_count: 0,
    linked_publication_count: 1,
  },
};

const mockCandidates = [
  {
    link_type: 'analytical_relation' as const,
    target_id: 'rel-2',
    group_item_id: 'group-item-2',
    publication_id: 'pub-2',
    latest_revision_id: 'rev-2',
    traceable: true,
    label: 'analytical_relation #group-item-2',
    publication_title: 'Energy Efficiency in Lean Systems',
    publication_year: 2024,
    qa_profile: {
      assessment_id: 'qa-2',
      template_id: 'tmpl-2',
      reviewer_id: 'reviewer_1',
      criteria_assessments: [
        {
          criterion_id: 'c-1',
          question_text: 'QA1: Clear study objectives?',
          response_value: 'YES',
          justification: 'Objectives detailed in the introduction.',
        },
        {
          criterion_id: 'c-2',
          question_text: 'QA2: Were data collection methods described?',
          response_value: 'NO',
          justification: null,
        },
      ],
    },
  },
  {
    link_type: 'mechanism_pathway' as const,
    target_id: 'pathway-9',
    group_item_id: 'group-item-9',
    publication_id: 'pub-9',
    latest_revision_id: 'rev-9',
    traceable: false,
    label: 'mechanism_pathway #group-item-9',
    publication_title: 'Pending Extraction',
    publication_year: null,
    qa_profile: null,
  },
];

describe('ResearchGapsWorkspace Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders workspace with KPI stats, type sections, and gap cards', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Research Gap Synthesis')).toBeInTheDocument();
    });

    expect(screen.getByText('Total Gaps')).toBeInTheDocument();
    expect(screen.getByText('Mechanism Gap')).toBeInTheDocument();
    expect(screen.getByText('Compressed Air Efficiency vs SMED Interaction')).toBeInTheDocument();
    expect(screen.getByText('Analytical Relation')).toBeInTheDocument();
    expect(screen.getByTestId('add-research-gap-btn')).toBeInTheDocument();
  });

  it('handles gap creation modal submission', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);
    const createSpy = vi.spyOn(synthesisApi, 'createResearchGap').mockResolvedValue({
      gap_id: 'gap-2',
      project_id: 'proj-123',
      gap_type: 'contextual',
      title: 'Regional Energy Price Sensitivity',
      rationale: 'Linked context-factor evidence shows price elasticity varies by region with no synthesis coverage.',
      researcher_id: 'lead_researcher',
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    });

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('add-research-gap-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('add-research-gap-btn'));

    expect(screen.getByText('Create Research Gap')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('gap-type-select'), { target: { value: 'contextual' } });
    fireEvent.change(screen.getByTestId('gap-title-input'), { target: { value: 'Regional Energy Price Sensitivity' } });
    fireEvent.change(screen.getByTestId('gap-rationale-input'), {
      target: {
        value: 'Linked context-factor evidence shows price elasticity varies by region with no synthesis coverage.',
      },
    });
    fireEvent.change(screen.getByTestId('gap-researcher-input'), { target: { value: 'lead_researcher' } });

    fireEvent.click(screen.getByTestId('save-gap-submit-btn'));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('proj-123', {
        gap_type: 'contextual',
        title: 'Regional Energy Price Sensitivity',
        rationale: 'Linked context-factor evidence shows price elasticity varies by region with no synthesis coverage.',
        researcher_id: 'lead_researcher',
      });
    });
  });

  it('rejects gap creation when rationale is empty', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);
    const createSpy = vi.spyOn(synthesisApi, 'createResearchGap');

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('add-research-gap-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('add-research-gap-btn'));
    fireEvent.change(screen.getByTestId('gap-title-input'), { target: { value: 'Unjustified Gap' } });
    fireEvent.click(screen.getByTestId('save-gap-submit-btn'));

    await waitFor(() => {
      expect(createSpy).not.toHaveBeenCalled();
      expect(screen.getByText(/never by publication count alone/)).toBeInTheDocument();
    });
  });

  it('links only traceable evidence candidates and blocks untraceable ones', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);
    vi.spyOn(synthesisApi, 'getResearchGapEvidenceCandidates').mockResolvedValue(mockCandidates);
    vi.spyOn(synthesisApi, 'getResearchGap').mockResolvedValue(mockWorkspaceData.gaps[0]);
    const linkSpy = vi.spyOn(synthesisApi, 'linkResearchGapEvidence').mockResolvedValue({
      link_id: 'link-2',
      project_id: 'proj-123',
      gap_id: 'gap-1',
      link_type: 'analytical_relation',
      target_id: 'rel-2',
      group_item_id: 'group-item-2',
      publication_id: 'pub-2',
      latest_revision_id: 'rev-2',
      created_at: '2024-01-02T00:00:00Z',
    });

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('manage-evidence-gap-1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('manage-evidence-gap-1'));

    await waitFor(() => {
      expect(screen.getByText('Supporting Evidence — Compressed Air Efficiency vs SMED Interaction')).toBeInTheDocument();
      expect(screen.getByText('TRACEABLE')).toBeInTheDocument();
      expect(screen.getByText('NOT TRACEABLE')).toBeInTheDocument();
    });

    // Non-traceable candidate link button is disabled
    expect(screen.getByTestId('link-evidence-rel-2')).toBeEnabled();
    expect(screen.getByTestId('link-evidence-pathway-9')).toBeDisabled();

    // Linking traceable candidate succeeds
    fireEvent.click(screen.getByTestId('link-evidence-rel-2'));

    await waitFor(() => {
      expect(linkSpy).toHaveBeenCalledWith('proj-123', 'gap-1', {
        link_type: 'analytical_relation',
        target_id: 'rel-2',
      });
    });
  });

  it('unlinks existing evidence', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);
    vi.spyOn(synthesisApi, 'getResearchGapEvidenceCandidates').mockResolvedValue([]);
    vi.spyOn(synthesisApi, 'getResearchGap').mockResolvedValue(mockWorkspaceData.gaps[0]);
    const unlinkSpy = vi.spyOn(synthesisApi, 'unlinkResearchGapEvidence').mockResolvedValue(undefined);

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('manage-evidence-gap-1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('manage-evidence-gap-1'));

    await waitFor(() => {
      expect(screen.getByText('Linked Evidence (1)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('unlink-evidence-link-1'));

    await waitFor(() => {
      expect(unlinkSpy).toHaveBeenCalledWith('proj-123', 'gap-1', 'link-1');
    });
  });

  it('deletes a research gap after confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);
    const deleteSpy = vi.spyOn(synthesisApi, 'deleteResearchGap').mockResolvedValue(undefined);

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('delete-gap-gap-1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('delete-gap-gap-1'));

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('proj-123', 'gap-1');
      expect(confirmSpy).toHaveBeenCalled();
    });

    confirmSpy.mockRestore();
  });

  it('navigates to the Research Gaps tab in EvidenceSynthesisPage', async () => {
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
    vi.spyOn(synthesisApi, 'getMechanismWorkspace').mockResolvedValue({
      project_id: 'proj-123',
      categories: [],
      pathways: [],
      synthesis_chains: [],
      stats: {
        total_pathways: 0,
        mapped_count: 0,
        unmapped_count: 0,
        approved_count: 0,
        total_publications: 0,
      },
    });
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);

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

    expect(screen.getByTestId('synthesis-tab-research-gaps')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('synthesis-tab-research-gaps'));

    await waitFor(() => {
      expect(screen.getByText('Research Gap Synthesis')).toBeInTheDocument();
      expect(screen.getByText('Compressed Air Efficiency vs SMED Interaction')).toBeInTheDocument();
    });
  });

  it('renders error state gracefully when API fails', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockRejectedValue(new Error('Network error'));

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Error loading research gap workspace')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('exposes criterion-level QA for candidate evidence and makes missing QA explicit', async () => {
    vi.spyOn(synthesisApi, 'getResearchGapWorkspace').mockResolvedValue(mockWorkspaceData);
    vi.spyOn(synthesisApi, 'getResearchGapEvidenceCandidates').mockResolvedValue(mockCandidates);

    render(<ResearchGapsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('manage-evidence-gap-1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('manage-evidence-gap-1'));

    await waitFor(() => {
      expect(screen.getByTestId('toggle-qa-rel-2')).toBeInTheDocument();
    });

    // QA profile present: show criterion-level responses/justifications
    fireEvent.click(screen.getByTestId('toggle-qa-rel-2'));

    await waitFor(() => {
      expect(screen.getByTestId('qa-profile-present')).toBeInTheDocument();
      expect(screen.getByText('Criterion-Level QA Profile — reviewer_1')).toBeInTheDocument();
      expect(screen.getByText('QA1: Clear study objectives?')).toBeInTheDocument();
      expect(screen.getByText('YES')).toBeInTheDocument();
      expect(screen.getByText('Objectives detailed in the introduction.')).toBeInTheDocument();
      expect(screen.getByText('QA2: Were data collection methods described?')).toBeInTheDocument();
      expect(screen.getByText('NO')).toBeInTheDocument();
    });

    // No aggregate score / quality tier is ever rendered
    expect(screen.queryByText(/aggregate/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/quality tier/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence score/i)).not.toBeInTheDocument();

    // Missing QA is explicit: candidate without QA shows a clear notice
    fireEvent.click(screen.getByTestId('toggle-qa-pathway-9'));

    await waitFor(() => {
      expect(screen.getByTestId('qa-profile-missing')).toBeInTheDocument();
      expect(screen.getByText(/No QA profile available/i)).toBeInTheDocument();
    });
  });
});
