import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { DataExtractionPage } from '../src/pages/DataExtractionPage';
import { extractionApi } from '../src/api/extractionApi';
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
    expect(screen.getByDisplayValue('Sample Article Title')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2024')).toBeInTheDocument();
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
    expect(screen.getByText('Tytuł badania / publikacji')).toBeInTheDocument();
    expect(screen.getByText('Typ badania (Study Design)')).toBeInTheDocument();
    expect(screen.getByText('Ramiona Badania / Grupy Uczestników (1:N Study Arms)')).toBeInTheDocument();
  });
});
