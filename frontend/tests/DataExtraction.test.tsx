import { fireEvent, render, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { DataExtractionPage } from '../src/pages/DataExtractionPage';
import { extractionApi, ExtractionApiError } from '../src/api/extractionApi';
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

describe('Data Extraction Workspace GUI (Phase 9.5)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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

  it('A & B. Data Extraction route renders and loads latest extraction record', async () => {
    renderComponent();
    await waitForElementToBeRemoved(() => screen.queryByText(/Ładowanie formularza ekstrakcji/i));
    expect(screen.getByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Sample Article Title')).toBeInTheDocument();
  });

  it('C. Loading state is displayed during fetch', () => {
    vi.spyOn(extractionApi, 'getExtractionEligibility').mockImplementation(() => new Promise(() => {}));
    renderComponent();
    expect(screen.getByText(/Ładowanie formularza ekstrakcji/i)).toBeInTheDocument();
  });

  it('E. Publication selector renders eligible publication ID', async () => {
    renderComponent();
    await waitForElementToBeRemoved(() => screen.queryByText(/Ładowanie formularza ekstrakcji/i));
    expect(screen.getByLabelText('Wybierz publikację do ekstrakcji:')).toBeInTheDocument();
  });

  it('F. Publication-level fields render from template definition', async () => {
    renderComponent();
    await waitForElementToBeRemoved(() => screen.queryByText(/Ładowanie formularza ekstrakcji/i));
    expect(screen.getByText('Tytuł badania / publikacji')).toBeInTheDocument();
    expect(screen.getByText('Rok publikacji')).toBeInTheDocument();
    expect(screen.getByText('Typ badania (Study Design)')).toBeInTheDocument();
  });

  it('G & H. Text and numeric field editing updates input values', async () => {
    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    const titleInput = await screen.findByLabelText('Tytuł badania / publikacji');
    fireEvent.change(titleInput, { target: { value: 'Updated Title Text' } });
    expect(titleInput).toHaveValue('Updated Title Text');

    const yearInput = await screen.findByLabelText('Rok publikacji');
    fireEvent.change(yearInput, { target: { value: '2025' } });
    expect(yearInput).toHaveValue(2025);
  });

  it('I. Enum selection dropdown updates selected value', async () => {
    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    const designSelect = await screen.findByLabelText('Typ badania (Study Design)');
    fireEvent.change(designSelect, { target: { value: 'Cohort Study' } });
    expect(designSelect).toHaveValue('Cohort Study');
  });

  it('K & L & M. ValueStatus change to NOT_REPORTED / NOT_APPLICABLE disables typed input control', async () => {
    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    const titleInput = await screen.findByLabelText('Tytuł badania / publikacji');
    expect(titleInput).not.toBeDisabled();

    // Change status to NOT_REPORTED
    const statusSelects = await screen.findAllByRole('combobox');
    const titleStatusSelect = statusSelects[1];
    fireEvent.change(titleStatusSelect, { target: { value: 'not_reported' } });

    await waitFor(() => {
      expect(titleInput).toBeDisabled();
    });
  });

  it('P & Q. Provenance drawer opens and allows editing metadata', async () => {
    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');
    await screen.findByLabelText('Tytuł badania / publikacji');

    const provButtons = await screen.findAllByRole('button', { name: /\+ Proweniencja|Proweniencja ✓/i });
    fireEvent.click(provButtons[0]);

    expect(await screen.findByText('Proweniencja pola')).toBeInTheDocument();
    const pageInput = screen.getByLabelText('Strona w publikacji (source_page)');
    fireEvent.change(pageInput, { target: { value: 'p. 15' } });
    expect(pageInput).toHaveValue('p. 15');

    fireEvent.click(screen.getByRole('button', { name: 'Zapisz proweniencję' }));
    await waitFor(() => {
      expect(screen.queryByText('Proweniencja pola')).not.toBeInTheDocument();
    });
  });

  it('R & S & T. Repeating group manager adds, edits and removes group items', async () => {
    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    expect(await screen.findByText('Ramiona badania / Grupy badane (Study Arms)')).toBeInTheDocument();

    const addBtn = screen.getByRole('button', { name: /Dodaj element/i });
    fireEvent.click(addBtn);

    expect(await screen.findByText('Element #1')).toBeInTheDocument();

    const armNameInput = await screen.findByLabelText('Nazwa grupy / ramienia');
    fireEvent.change(armNameInput, { target: { value: 'Control Arm A' } });
    expect(armNameInput).toHaveValue('Control Arm A');

    const removeBtn = screen.getByRole('button', { name: /Usuń element #1/i });
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(screen.queryByText('Element #1')).not.toBeInTheDocument();
    });
  });

  it('U & V. Save Draft calls POST revision endpoint correctly and shows success banner', async () => {
    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    const draftBtn = await screen.findByRole('button', { name: /Zapisz szkic/i });
    fireEvent.click(draftBtn);

    await waitFor(() => {
      expect(extractionApi.submitRevision).toHaveBeenCalledWith('proj_test', pubId, expect.objectContaining({
        mark_complete: false,
      }));
    });

    expect(await screen.findByText(/Zapisano szkic ekstrakcji/i)).toBeInTheDocument();
  });

  it('W & Z. Mark Complete sends completion intent and displays COMPLETE when backend accepts', async () => {
    vi.spyOn(extractionApi, 'submitRevision').mockResolvedValue({
      ...mockRecord.latest_revision,
      revision_index: 2,
      completeness_status: 'complete',
    });

    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    const completeBtn = await screen.findByRole('button', { name: /Oznacz jako zakończone/i });
    fireEvent.click(completeBtn);

    await waitFor(() => {
      expect(extractionApi.submitRevision).toHaveBeenCalledWith('proj_test', pubId, expect.objectContaining({
        mark_complete: true,
      }));
    });

    expect(await screen.findByText(/Ekstrakcja danych została oznaczona jako ZAKOŃCZONA/i)).toBeInTheDocument();
  });

  it('X. Backend 422 validation errors are displayed clearly', async () => {
    vi.spyOn(extractionApi, 'submitRevision').mockRejectedValue(
      new ExtractionApiError(422, ['Wymagane pole study_title nie może być puste.'])
    );

    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    const completeBtn = await screen.findByRole('button', { name: /Oznacz jako zakończone/i });
    fireEvent.click(completeBtn);

    expect(await screen.findByText('Walidacja nie powiodła się. Popraw błędy w formularzu.')).toBeInTheDocument();
  });

  it('Y. Backend blocked eligibility status renders warning card', async () => {
    vi.spyOn(extractionApi, 'getExtractionEligibility').mockResolvedValue({
      project_id: 'proj_test',
      total_publications: 1,
      eligible_count: 0,
      items: [
        {
          publication_id: pubId,
          status: 'blocked_screening_incomplete' as const,
          is_eligible: false,
          reason_details: 'Brak decyzji screeningowej',
        },
      ],
    });

    renderComponent();
    await screen.findByText('7. Formularz Ekstrakcji Danych (Data Extraction Workspace)');

    expect(await screen.findByText(/Publikacja nie kwalifikuje się obecnie do ekstrakcji danych/i)).toBeInTheDocument();
    expect(screen.getAllByText(/blocked_screening_incomplete/i).length).toBeGreaterThan(0);
  });
});
