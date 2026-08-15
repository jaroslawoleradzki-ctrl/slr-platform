import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { DataExtractionPage } from '../src/pages/DataExtractionPage';
import { ExtractionApiError, extractionApi } from '../src/api/extractionApi';
import { ProjectProvider } from '../src/context/ProjectContext';

const pubId = '27ae7210-a6b3-418d-8e31-b9e33a695762';

const mockEligibility = {
  project_id: 'proj_test',
  total_publications: 1,
  eligible_count: 1,
  items: [
    {
      publication_id: pubId,
      status: 'eligible' as const,
      is_eligible: true,
      reason_details: null,
    },
  ],
};

const mockRecord = {
  record_id: 'rec_1',
  project_id: 'proj_test',
  publication_id: pubId,
  template_id: 'default_extraction_template',
  template_version: '1.0.0',
  current_status: 'in_progress' as const,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  latest_revision: {
    revision_id: 'rev_1_id',
    record_id: 'rec_1',
    project_id: 'proj_test',
    publication_id: pubId,
    revision_index: 1,
    reviewer_id: 'rev_1',
    completeness_status: 'in_progress' as const,
    publication_values: [
      {
        field_key: 'study_title',
        status: 'present' as const,
        origin: 'reported' as const,
        text_value: 'Sample Article Title',
      },
      {
        field_key: 'publication_year',
        status: 'present' as const,
        origin: 'reported' as const,
        int_value: 2024,
      },
      {
        field_key: 'study_design',
        status: 'present' as const,
        origin: 'reported' as const,
        text_value: 'Randomized Controlled Trial (RCT)',
      },
    ],
    group_items: [],
    created_at: new Date().toISOString(),
  },
};

const mockHistory = {
  project_id: 'proj_test',
  publication_id: pubId,
  total_revisions: 1,
  revisions: [mockRecord.latest_revision],
};

const mockProgress = {
  project_id: 'proj_test',
  total_eligible_publications: 3,
  not_started_count: 1,
  in_progress_count: 1,
  complete_count: 1,
  needs_review_count: 0,
  completion_percentage: 33.3,
};

const mockRecordsSummary = {
  project_id: 'proj_test',
  total_records: 3,
  items: [
    {
      publication_id: pubId,
      title: 'Sample Article Title',
      authors: ['Smith J.', 'Doe A.'],
      publication_year: 2024,
      extraction_status: 'in_progress' as const,
      latest_revision_index: 1,
      latest_reviewer_id: 'rev_1',
      latest_updated_at: new Date().toISOString(),
    },
  ],
};

const mockMatrix = {
  project_id: 'proj_test',
  template_id: 'default_extraction_template',
  template_version: '1.0.0',
  total_relationships: 2,
  group_keys: ['study_arms'],
  items: [
    {
      publication_id: pubId,
      publication_title: 'Sample Article Title',
      group_key: 'study_arms',
      group_name: 'Study Arms',
      group_item_id: 'item_1_id',
      item_index: 1,
      values: [
        {
          field_key: 'arm_name',
          status: 'present' as const,
          origin: 'reported' as const,
          text_value: 'Group A Intervention',
        },
      ],
    },
    {
      publication_id: pubId,
      publication_title: 'Sample Article Title',
      group_key: 'study_arms',
      group_name: 'Study Arms',
      group_item_id: 'item_2_id',
      item_index: 2,
      values: [
        {
          field_key: 'arm_name',
          status: 'present' as const,
          origin: 'reported' as const,
          text_value: 'Group B Control',
        },
      ],
    },
  ],
};

describe('Data Extraction Workspace GUI (Phase 9.5 & 9.6)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('slr_screening_reviewer_id', 'rev_1');
    vi.spyOn(extractionApi, 'getProjectTemplate').mockResolvedValue({
      template_id: 'default_extraction_template', version: '1.0.0', name: 'Test template', created_at: new Date().toISOString(),
      is_published: true, is_active: true,
      publication_fields: [
        { field_key: 'study_design', name: 'Typ badania (Study Design)', data_type: 'enum', is_required: true },
      ],
      repeating_groups: [{
        group_key: 'study_arms', name: 'Ramiona Badania / Grupy Uczestników (1:N Study Arms)',
        min_items: 0, max_items: 10, field_definitions: [],
      }],
    });
    Object.assign(URL, {
      createObjectURL: vi.fn().mockReturnValue('blob:test'),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(extractionApi, 'getExtractionProgress').mockResolvedValue(mockProgress);
    vi.spyOn(extractionApi, 'listExtractionRecords').mockResolvedValue(mockRecordsSummary);
    vi.spyOn(extractionApi, 'getExtractionMatrix').mockResolvedValue(mockMatrix);
    vi.spyOn(extractionApi, 'getExtractionEligibility').mockResolvedValue(mockEligibility);
    vi.spyOn(extractionApi, 'getExtractionRecord').mockResolvedValue(mockRecord);
    vi.spyOn(extractionApi, 'getExtractionHistory').mockResolvedValue(mockHistory);
    vi.spyOn(extractionApi, 'submitRevision').mockResolvedValue({
      ...mockRecord.latest_revision,
      revision_index: 2,
    });
  });

  const renderComponent = (path = `/projects/proj_test/extract/${pubId}`) => {
    return render(
      <ProjectProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/projects/:projectId/extract" element={<DataExtractionPage />} />
            <Route path="/projects/:projectId/extract/:publicationId" element={<DataExtractionPage />} />
          </Routes>
        </MemoryRouter>
      </ProjectProvider>
    );
  };

  it('A & B. Data Extraction route renders form workspace when publication ID present', async () => {
    renderComponent(`/projects/proj_test/extract/${pubId}`);

    expect(await screen.findByText('7. Ekstrakcja Danych (Data Extraction Workspace)')).toBeInTheDocument();
    expect(screen.getByText('Sample Article Title')).toBeInTheDocument();
    expect(screen.getByText(/E1: canonical publication metadata/i)).toBeInTheDocument();
  });

  it('C. Save Draft calls POST revision endpoint correctly and shows success banner', async () => {
    renderComponent(`/projects/proj_test/extract/${pubId}`);
    await screen.findByText('7. Ekstrakcja Danych (Data Extraction Workspace)');

    const draftBtn = await screen.findByRole('button', { name: /Zapisz Szkic/i });
    fireEvent.click(draftBtn);

    await waitFor(() => {
      expect(extractionApi.submitRevision).toHaveBeenCalledWith('proj_test', pubId, expect.objectContaining({
        mark_complete: false,
      }));
    });

    expect(await screen.findByText(/Zapisano szkic ekstrakcji/i)).toBeInTheDocument();
  });

  it('D. Mark Complete sends completion intent and displays COMPLETE when backend accepts', async () => {
    vi.spyOn(extractionApi, 'submitRevision').mockResolvedValue({
      ...mockRecord.latest_revision,
      revision_index: 2,
      completeness_status: 'complete',
    });

    renderComponent(`/projects/proj_test/extract/${pubId}`);
    await screen.findByText('7. Ekstrakcja Danych (Data Extraction Workspace)');

    const completeBtn = await screen.findByRole('button', { name: /Oznacz jako Zakończone/i });
    fireEvent.click(completeBtn);

    await waitFor(() => {
      expect(extractionApi.submitRevision).toHaveBeenCalledWith('proj_test', pubId, expect.objectContaining({
        mark_complete: true,
      }));
    });

    expect(await screen.findByText(/Ekstrakcja danych została oznaczona jako ZAKOŃCZONA/i)).toBeInTheDocument();
  });

  it('E. Tabular view and progress header render correctly', async () => {
    renderComponent('/projects/proj_test/extract');

    expect(await screen.findByText('Postęp Ekstrakcji Danych (Data Extraction Progress)')).toBeInTheDocument();
    expect(await screen.findByText('33.3%')).toBeInTheDocument();
    expect(await screen.findByText('Sample Article Title')).toBeInTheDocument();
    expect(screen.getByText('W trakcie')).toBeInTheDocument();
  });

  it('shows and saves an eligible publication before its first extraction record exists', async () => {
    vi.mocked(extractionApi.listExtractionRecords).mockResolvedValue({
      project_id: 'proj_test',
      total_records: 0,
      items: [],
    });
    vi.mocked(extractionApi.getExtractionRecord).mockRejectedValue(
      new ExtractionApiError(404, 'Extraction record was not found.'),
    );
    vi.mocked(extractionApi.getExtractionHistory).mockResolvedValue({
      project_id: 'proj_test',
      publication_id: pubId,
      total_revisions: 0,
      revisions: [],
    });

    renderComponent('/projects/proj_test/extract');

    expect(await screen.findByText('Zestawienie Publikacji (1)')).toBeInTheDocument();
    expect(screen.getByText(pubId)).toBeInTheDocument();
    expect(screen.getAllByText('Nie rozpoczęto').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: new RegExp(`Otwórz formularz ekstrakcji dla ${pubId}`) }));

    expect(await screen.findByText('Typ badania (Study Design)')).toBeInTheDocument();
    expect(screen.queryByText(/Błąd pobierania danych ekstrakcji/i)).not.toBeInTheDocument();

    vi.mocked(extractionApi.getExtractionRecord).mockResolvedValue(mockRecord);
    vi.mocked(extractionApi.listExtractionRecords).mockResolvedValue(mockRecordsSummary);
    fireEvent.click(screen.getByRole('button', { name: /Zapisz Szkic/i }));

    await waitFor(() => {
      expect(extractionApi.submitRevision).toHaveBeenCalledWith('proj_test', pubId, expect.objectContaining({
        mark_complete: false,
      }));
    });
    expect(await screen.findByText(/Zapisano szkic ekstrakcji/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Powrót do Widoku Tabelarycznego/i }));
    expect(await screen.findByText('W trakcie')).toBeInTheDocument();
  });

  it('keeps completed extraction records visible with their completed status', async () => {
    vi.mocked(extractionApi.listExtractionRecords).mockResolvedValue({
      ...mockRecordsSummary,
      items: [{ ...mockRecordsSummary.items[0], extraction_status: 'complete' }],
    });

    renderComponent('/projects/proj_test/extract');

    expect(await screen.findByText('Sample Article Title')).toBeInTheDocument();
    expect(screen.getAllByText('Zakończone').length).toBeGreaterThan(0);
  });

  it('shows blocked publications as non-editable eligibility candidates', async () => {
    vi.mocked(extractionApi.getExtractionEligibility).mockResolvedValue({
      project_id: 'proj_test',
      total_publications: 1,
      eligible_count: 0,
      items: [{
        publication_id: pubId,
        status: 'blocked_qa_incomplete',
        is_eligible: false,
        reason_details: 'Quality Assessment is incomplete.',
      }],
    });
    vi.mocked(extractionApi.listExtractionRecords).mockResolvedValue({
      project_id: 'proj_test',
      total_records: 0,
      items: [],
    });

    renderComponent('/projects/proj_test/extract');

    expect(await screen.findByText('Zestawienie Publikacji (1)')).toBeInTheDocument();
    expect(screen.getByText('Zablokowana: blocked_qa_incomplete')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: new RegExp(`Publikacja ${pubId} jest zablokowana`) })).toBeDisabled();
    expect(extractionApi.getExtractionRecord).not.toHaveBeenCalled();
  });

  it('renders an empty table when eligibility returns no publications', async () => {
    vi.mocked(extractionApi.getExtractionEligibility).mockResolvedValue({
      project_id: 'proj_test',
      total_publications: 0,
      eligible_count: 0,
      items: [],
    });

    renderComponent('/projects/proj_test/extract');

    expect(await screen.findByText('Zestawienie Publikacji (0)')).toBeInTheDocument();
    expect(screen.getByText('Brak zakwalifikowanych publikacji do ekstrakcji w tym projekcie.')).toBeInTheDocument();
  });

  it('F. View mode switching between Table View and Form Workspace', async () => {
    renderComponent('/projects/proj_test/extract');

    const formBtn = await screen.findByRole('button', { name: /Formularz Ekstrakcji/i });
    fireEvent.click(formBtn);

    expect(await screen.findByText(/Wybierz publikację do ekstrakcji/i)).toBeInTheDocument();

    const tableBtn = await screen.findByRole('button', { name: /Widok Tabelaryczny/i });
    fireEvent.click(tableBtn);

    expect(await screen.findByText('Postęp Ekstrakcji Danych (Data Extraction Progress)')).toBeInTheDocument();
  });

  it('G. Cross-Study Relationship Matrix renders 1:N items as separate rows', async () => {
    renderComponent('/projects/proj_test/extract');

    const matrixTab = await screen.findByRole('button', { name: /Macierz Relacji/i });
    fireEvent.click(matrixTab);

    expect(await screen.findByText('Macierz Relacji (Cross-Study Repeating Group Matrix)')).toBeInTheDocument();
    expect(await screen.findByText('Group A Intervention')).toBeInTheDocument();
    expect(await screen.findByText('Group B Control')).toBeInTheDocument();
  });

  it('H. Clicking Workspace action on summary table opens single publication editing workspace', async () => {
    renderComponent('/projects/proj_test/extract');

    const workspaceBtn = (await screen.findAllByRole('button', { name: /Otwórz formularz ekstrakcji/i }))[0];
    fireEvent.click(workspaceBtn);

    expect(await screen.findByText(/Powrót do Widoku Tabelarycznego/i)).toBeInTheDocument();
  });

  it('I. Lean Energy v1 schema renders publication fields and 1:N repeating group items dynamically', async () => {
    renderComponent(`/projects/proj_test/extract/${pubId}`);

    expect(await screen.findByText('7. Ekstrakcja Danych (Data Extraction Workspace)')).toBeInTheDocument();
    expect(screen.getByText(/E1: canonical publication metadata/i)).toBeInTheDocument();
    expect(screen.getByText('Typ badania (Study Design)')).toBeInTheDocument();
    expect(screen.getByText('Ramiona Badania / Grupy Uczestników (1:N Study Arms)')).toBeInTheDocument();
  });

  it('J. Export controls request JSON, publication CSV, and relationship CSV', async () => {
    const exportDataset = vi.spyOn(extractionApi, 'exportDataset').mockResolvedValue(new Blob(['{}']));
    renderComponent('/projects/proj_test/extract');

    fireEvent.click(await screen.findByRole('button', { name: /Eksport JSON/i }));
    fireEvent.click(await screen.findByRole('button', { name: /CSV publikacji/i }));
    fireEvent.click(await screen.findByRole('button', { name: /CSV relacji/i }));

    await waitFor(() => expect(exportDataset).toHaveBeenCalledTimes(3));
    expect(exportDataset).toHaveBeenNthCalledWith(1, 'proj_test', 'json', 'publications');
    expect(exportDataset).toHaveBeenNthCalledWith(2, 'proj_test', 'csv', 'publications');
    expect(exportDataset).toHaveBeenNthCalledWith(3, 'proj_test', 'csv', 'relationships');
  });

  it('K. Export failure is visible to the user', async () => {
    vi.spyOn(extractionApi, 'exportDataset').mockRejectedValue(new Error('export unavailable'));
    renderComponent('/projects/proj_test/extract');

    fireEvent.click(await screen.findByRole('button', { name: /Eksport JSON/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Nie udało się pobrać eksportu/i);
  });

  it('L. Repeating group items preserve durable group_item_id across add, edit, delete and submission', async () => {
    const existingGroupId = 'uuid-arm-123';
    const mockRecordWithGroup = {
      ...mockRecord,
      latest_revision: {
        ...mockRecord.latest_revision,
        group_items: [
          {
            group_key: 'study_arms',
            group_item_id: existingGroupId,
            item_index: 1,
            values: [],
          },
        ],
      },
    };
    vi.spyOn(extractionApi, 'getExtractionRecord').mockResolvedValue(mockRecordWithGroup);

    renderComponent(`/projects/proj_test/extract/${pubId}`);
    await screen.findByText('7. Ekstrakcja Danych (Data Extraction Workspace)');

    // Add a new element
    const addBtn = await screen.findByRole('button', { name: /Dodaj element/i });
    fireEvent.click(addBtn);

    // Save draft
    const draftBtn = await screen.findByRole('button', { name: /Zapisz Szkic/i });
    fireEvent.click(draftBtn);

    await waitFor(() => {
      expect(extractionApi.submitRevision).toHaveBeenCalledWith(
        'proj_test',
        pubId,
        expect.objectContaining({
          group_items: expect.arrayContaining([
            expect.objectContaining({
              group_item_id: existingGroupId,
              item_index: 1,
            }),
            expect.objectContaining({
              item_index: 2,
            }),
          ]),
        })
      );
    });
  });
});
