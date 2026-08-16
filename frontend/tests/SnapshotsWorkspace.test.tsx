import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SnapshotsWorkspace } from '../src/components/synthesis/SnapshotsWorkspace';
import { EvidenceSynthesisPage } from '../src/pages/EvidenceSynthesisPage';
import { ProjectProvider } from '../src/context/ProjectContext';
import { synthesisApi } from '../src/services/api/synthesisApi';
import { SynthesisSnapshot, SynthesisSnapshotDetail } from '../src/types/synthesis';

const mockSnapshots: SynthesisSnapshot[] = [
  {
    snapshot_id: 'snap-1',
    project_id: 'proj-123',
    version: 1,
    actor: 'lead_researcher',
    extraction_dataset_hash: 'a'.repeat(64),
    classification_version: 'b'.repeat(64),
    content_hash: 'c'.repeat(64),
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    snapshot_id: 'snap-2',
    project_id: 'proj-123',
    version: 2,
    actor: 'reviewer_1',
    extraction_dataset_hash: 'd'.repeat(64),
    classification_version: 'e'.repeat(64),
    content_hash: 'f'.repeat(64),
    created_at: '2024-02-01T00:00:00Z',
  },
];

const mockDetail: SynthesisSnapshotDetail = {
  ...mockSnapshots[0],
  content: {
    project_id: 'proj-123',
    relations: [
      {
        relation_id: 'rel-1',
        project_id: 'proj-123',
        publication_id: 'pub-1',
        latest_revision_id: 'rev-1',
        group_item_id: 'group-1',
        item_index: 1,
        source_practice: 'SMED Setup',
        analytical_lean_category_id: null,
        source_effect: 'Compressed Air',
        analytical_energy_category_id: null,
        direction: 'positive',
        magnitude: null,
        original_unit: null,
        converted_value: null,
        evidence_character: 'empirical',
        context_summary: null,
        approval_state: 'approved',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ],
    mechanism_pathways: [],
    context_assignments: [],
    research_gaps: [],
    research_gap_links: [],
    term_mappings: [],
    lean_categories: [],
    energy_categories: [],
    mechanism_categories: [],
    context_categories: [],
    qa_profiles: [],
  },
};

describe('SnapshotsWorkspace Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('E1: renders workspace header with snapshots list', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Synthesis Snapshots')).toBeInTheDocument();
    });
    expect(screen.getByText('Snapshot Versions (2)')).toBeInTheDocument();
    expect(screen.getByTestId('snapshot-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('snapshot-row-2')).toBeInTheDocument();
    expect(screen.getByTestId('create-snapshot-btn')).toBeInTheDocument();
  });

  it('E2: empty state shows no auto-creation message', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue([]);

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByText('Snapshot Versions (0)')).toBeInTheDocument();
    });
    expect(screen.getByText(/never created automatically/i)).toBeInTheDocument();
  });

  it('E3: create snapshot flow creates and refreshes list', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue([]);
    const createSpy = vi.spyOn(synthesisApi, 'createSnapshot').mockResolvedValue(mockDetail);
    vi.spyOn(synthesisApi, 'getSnapshot').mockResolvedValue(mockDetail);
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('create-snapshot-btn')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('snapshot-actor-input'), {
      target: { value: 'lead_researcher' },
    });
    fireEvent.click(screen.getByTestId('create-snapshot-btn'));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('proj-123', { actor: 'lead_researcher' });
    });
    await waitFor(() => {
      expect(screen.getByTestId('snapshot-detail-panel')).toBeInTheDocument();
    });
  });

  it('E4: create snapshot requires non-empty actor', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue([]);
    const createSpy = vi.spyOn(synthesisApi, 'createSnapshot');

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('create-snapshot-btn')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('snapshot-actor-input'), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByTestId('create-snapshot-btn'));

    await waitFor(() => {
      expect(screen.getByText('Actor is required.')).toBeInTheDocument();
    });
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('E5: selecting a snapshot loads detail with hashes', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);
    const getSpy = vi.spyOn(synthesisApi, 'getSnapshot').mockResolvedValue(mockDetail);

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-row-1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('snapshot-row-1'));

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith('proj-123', 1);
    });
    expect(screen.getByTestId('snapshot-detail-panel')).toBeInTheDocument();
    expect(screen.getByTestId('dataset-hash')).toBeInTheDocument();
    expect(screen.getByText(/Extraction Dataset Hash/i)).toBeInTheDocument();
  });

  it('E6: snapshot detail shows frozen content counts', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);
    vi.spyOn(synthesisApi, 'getSnapshot').mockResolvedValue(mockDetail);

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-row-1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('snapshot-row-1'));

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-stat-relations')).toBeInTheDocument();
    });
    expect(screen.getByTestId('snapshot-stat-relations').textContent).toContain('1');
  });

  it('E7: JSON export produces preview', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);
    vi.spyOn(synthesisApi, 'getSnapshot').mockResolvedValue(mockDetail);
    const exportSpy = vi.spyOn(synthesisApi, 'exportSnapshot').mockResolvedValue({
      snapshot_id: 'snap-1',
      project_id: 'proj-123',
      version: 1,
      actor: 'lead_researcher',
      created_at: '2024-01-01T00:00:00Z',
      format: 'json',
      extraction_dataset_hash: 'a'.repeat(64),
      classification_version: 'b'.repeat(64),
      content_hash: 'c'.repeat(64),
      content: mockDetail.content,
      content_csv: null,
    });

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-row-1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('snapshot-row-1'));

    await waitFor(() => {
      expect(screen.getByTestId('export-json-btn')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('export-json-btn'));

    await waitFor(() => {
      expect(exportSpy).toHaveBeenCalledWith('proj-123', 1, 'json');
    });
    expect(screen.getByTestId('export-preview')).toBeInTheDocument();
    expect(screen.getByTestId('download-export-btn')).toBeInTheDocument();
  });

  it('E8: CSV export shows relations matrix', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);
    vi.spyOn(synthesisApi, 'getSnapshot').mockResolvedValue(mockDetail);
    const exportSpy = vi.spyOn(synthesisApi, 'exportSnapshot').mockResolvedValue({
      snapshot_id: 'snap-1',
      project_id: 'proj-123',
      version: 1,
      actor: 'lead_researcher',
      created_at: '2024-01-01T00:00:00Z',
      format: 'csv',
      extraction_dataset_hash: null,
      classification_version: null,
      content_hash: null,
      content: null,
      content_csv: 'source_practice,direction\nSMED Setup,positive\n',
    });

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-row-1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('snapshot-row-1'));

    await waitFor(() => {
      expect(screen.getByTestId('export-csv-btn')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('export-csv-btn'));

    await waitFor(() => {
      expect(exportSpy).toHaveBeenCalledWith('proj-123', 1, 'csv');
    });
    expect(screen.getByText('CSV Relations Matrix')).toBeInTheDocument();
  });

  it('E9: snapshot tab is accessible in EvidenceSynthesisPage', async () => {
    render(
      <MemoryRouter initialEntries={['/projects/proj-123/synthesis']}>
        <ProjectProvider>
          <Routes>
            <Route path="/projects/:projectId/synthesis" element={<EvidenceSynthesisPage />} />
          </Routes>
        </ProjectProvider>
      </MemoryRouter>
    );

    expect(screen.getByTestId('synthesis-tab-snapshots')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('synthesis-tab-snapshots'));
    expect(screen.getAllByText(/Synthesis Snapshots/i).length).toBeGreaterThan(0);
  });

  it('E10: download button creates a blob', async () => {
    vi.spyOn(synthesisApi, 'listSnapshots').mockResolvedValue(mockSnapshots);
    vi.spyOn(synthesisApi, 'getSnapshot').mockResolvedValue(mockDetail);
    vi.spyOn(synthesisApi, 'exportSnapshot').mockResolvedValue({
      snapshot_id: 'snap-1',
      project_id: 'proj-123',
      version: 1,
      actor: 'lead_researcher',
      created_at: '2024-01-01T00:00:00Z',
      format: 'json',
      extraction_dataset_hash: 'a'.repeat(64),
      classification_version: 'b'.repeat(64),
      content_hash: 'c'.repeat(64),
      content: mockDetail.content,
      content_csv: null,
    });
    // jsdom does not provide createObjectURL; define it before spying
    (URL as any).createObjectURL = (() => 'blob:fake') as any;
    (URL as any).revokeObjectURL = (() => {}) as any;
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL');
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL');

    render(<SnapshotsWorkspace projectId="proj-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-row-1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('snapshot-row-1'));
    await waitFor(() => {
      expect(screen.getByTestId('export-json-btn')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('export-json-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('download-export-btn')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('download-export-btn'));

    expect(createObjectURLSpy).toHaveBeenCalled();
    expect(revokeSpy).toHaveBeenCalled();
  });
});
