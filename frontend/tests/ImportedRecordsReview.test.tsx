import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { FileDropzone } from '../src/components/imports/FileDropzone';
import { ImportedRecordsModal } from '../src/components/imports/ImportedRecordsModal';
import { projectApiService } from '../src/services/api/projectApi';
import { ImportFileRecord, ImportedRecordsPageResponse } from '../src/types';

vi.mock('../src/context/ProjectContext', () => ({
  useProject: () => ({
    activeProject: { id: 'test_project', name: 'Test Project' },
    importBibliographicFile: vi.fn(),
  }),
}));

const mockImports: ImportFileRecord[] = [
  {
    id: 'imp-123',
    filename: 'crossref_batch_1.ris',
    importedAt: '2026-09-22T10:00:00Z',
    recordsCount: 25,
    status: 'success',
    sourceType: 'provider',
    provider: 'crossref',
    query: 'lean energy management',
    format: null,
  },
];

const mockPageResponse: ImportedRecordsPageResponse = {
  project_id: 'test_project',
  import_id: 'imp-123',
  total: 2,
  offset: 0,
  limit: 20,
  total_imported: 2,
  retained_count: 1,
  removed_count: 1,
  items: [
    {
      record_id: 'rec-1',
      project_id: 'test_project',
      import_id: 'imp-123',
      title: 'Active Energy Harvesting Optimization',
      authors: ['Alice Smith', 'Bob Jones'],
      publication_year: 2024,
      venue_name: 'IEEE Transactions on Energy',
      doi: '10.1109/energy.2024.1',
      abstract: 'Detailed study on energy optimization methods in manufacturing.',
      provider: 'crossref',
      source_record_id: 'cr-rec-1',
      pre_screening_status: 'retained',
      removal_reason: null,
      removal_notes: null,
      decided_at: null,
      reviewer_id: null,
    },
    {
      record_id: 'rec-2',
      project_id: 'test_project',
      import_id: 'imp-123',
      title: 'Call for Papers: Energy Summit 2025',
      authors: ['Conference Editorial Board'],
      publication_year: 2024,
      venue_name: 'Energy Bulletin',
      doi: null,
      abstract: 'Submissions are invited for the annual energy summit.',
      provider: 'crossref',
      source_record_id: 'cr-rec-2',
      pre_screening_status: 'removed',
      removal_reason: 'retrieval_artefact',
      removal_notes: 'Non-scholarly CFP notice',
      decided_at: '2026-09-22T11:00:00Z',
      reviewer_id: 'reviewer_1',
    },
  ],
};

describe('Imported Records Review & Pre-Screening Modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "Przeglądaj rekordy" button in FileDropzone import history', () => {
    render(
      <MemoryRouter>
        <FileDropzone imports={mockImports} projectId="test_project" />
      </MemoryRouter>,
    );

    expect(screen.getByText('Przeglądaj rekordy')).toBeInTheDocument();
  });

  it('opens ImportedRecordsModal and displays records, metadata and counts', async () => {
    const getImportedRecordsSpy = vi
      .spyOn(projectApiService, 'getImportedRecords')
      .mockResolvedValue(mockPageResponse);

    render(
      <MemoryRouter>
        <ImportedRecordsModal
          isOpen={true}
          onClose={vi.fn()}
          projectId="test_project"
          importId="imp-123"
          importTitle="Crossref Retrieval"
        />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getImportedRecordsSpy).toHaveBeenCalledWith('test_project', 'imp-123', {
        search: undefined,
        status_filter: undefined,
        offset: 0,
        limit: 20,
      });
    });

    // Counts check
    expect(screen.getByText('Łącznie pobrano')).toBeInTheDocument();
    expect(screen.getByText('Zachowane do Screeningu')).toBeInTheDocument();
    expect(screen.getByText('Usunięte przed Screeningiem')).toBeInTheDocument();

    // Record titles check
    expect(screen.getByText('Active Energy Harvesting Optimization')).toBeInTheDocument();
    expect(screen.getByText('Call for Papers: Energy Summit 2025')).toBeInTheDocument();

    // Authors & venue check
    expect(screen.getByText(/Alice Smith; Bob Jones/)).toBeInTheDocument();
    expect(screen.getByText(/IEEE Transactions on Energy/)).toBeInTheDocument();
    expect(screen.getByText(/DOI: 10.1109\/energy.2024.1/)).toBeInTheDocument();

    // PRISMA invariant notice
    expect(screen.getByText(/Reguła PRISMA:/)).toBeInTheDocument();
  });

  it('allows expanding and viewing abstract', async () => {
    vi.spyOn(projectApiService, 'getImportedRecords').mockResolvedValue(mockPageResponse);

    render(
      <MemoryRouter>
        <ImportedRecordsModal
          isOpen={true}
          onClose={vi.fn()}
          projectId="test_project"
          importId="imp-123"
          importTitle="Crossref Retrieval"
        />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Active Energy Harvesting Optimization')).toBeInTheDocument();
    });

    const expandButtons = screen.getAllByText('Pokaż abstrakt');
    expect(expandButtons.length).toBeGreaterThan(0);
    fireEvent.click(expandButtons[0]);

    expect(
      screen.getByText('Detailed study on energy optimization methods in manufacturing.'),
    ).toBeInTheDocument();
  });

  it('triggers manual removal flow with controlled reasons and audit trail', async () => {
    vi.spyOn(projectApiService, 'getImportedRecords').mockResolvedValue(mockPageResponse);
    const removeSpy = vi
      .spyOn(projectApiService, 'removeImportedRecord')
      .mockResolvedValue({
        ...mockPageResponse.items[0],
        pre_screening_status: 'removed',
        removal_reason: 'clearly_outside_scope',
      });

    render(
      <MemoryRouter>
        <ImportedRecordsModal
          isOpen={true}
          onClose={vi.fn()}
          projectId="test_project"
          importId="imp-123"
          importTitle="Crossref Retrieval"
        />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Active Energy Harvesting Optimization')).toBeInTheDocument();
    });

    // Click "Usuń z korpusu" for retained record
    const removeBtn = screen.getByText('Usuń z korpusu');
    fireEvent.click(removeBtn);

    // Removal confirmation modal appears
    expect(screen.getByText('Usuń Rekord przed Screeningiem')).toBeInTheDocument();

    // Select reason
    const reasonSelect = screen.getByRole('combobox');
    fireEvent.change(reasonSelect, { target: { value: 'clearly_outside_scope' } });

    // Confirm removal
    const confirmBtn = screen.getByText('Zatwierdź usunięcie');
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(removeSpy).toHaveBeenCalledWith(
        'test_project',
        'imp-123',
        'rec-1',
        expect.objectContaining({
          reason: 'clearly_outside_scope',
        }),
      );
    });
  });

  it('triggers restore (Undo) for removed records', async () => {
    vi.spyOn(projectApiService, 'getImportedRecords').mockResolvedValue(mockPageResponse);
    const restoreSpy = vi
      .spyOn(projectApiService, 'restoreImportedRecord')
      .mockResolvedValue({
        ...mockPageResponse.items[1],
        pre_screening_status: 'retained',
        removal_reason: null,
      });

    render(
      <MemoryRouter>
        <ImportedRecordsModal
          isOpen={true}
          onClose={vi.fn()}
          projectId="test_project"
          importId="imp-123"
          importTitle="Crossref Retrieval"
        />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Call for Papers: Energy Summit 2025')).toBeInTheDocument();
    });

    const restoreBtn = screen.getByText('Przywróć (Undo)');
    fireEvent.click(restoreBtn);

    await waitFor(() => {
      expect(restoreSpy).toHaveBeenCalledWith(
        'test_project',
        'imp-123',
        'rec-2',
        expect.objectContaining({
          reviewer_id: 'default_reviewer',
        }),
      );
    });
  });
});
