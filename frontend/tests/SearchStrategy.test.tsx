import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SearchStrategyPage } from '../src/pages/SearchStrategyPage';
import { projectApiService } from '../src/services/api/projectApi';
import { SearchExecutionResult, SearchResultsImportResponse, SearchStrategy } from '../src/types';

const mockExecuteSearchStrategy = vi.fn();
const mockImportSelectedSearchResults = vi.fn();
const mockSetSelectedSearchResultIds = vi.fn();

let mockSearchExecutionResult: SearchExecutionResult | null = null;
let mockSelectedSearchResultIds: string[] = [];
let mockLastSearchImportResult: SearchResultsImportResponse | null = null;

vi.mock('../src/context/ProjectContext', () => ({
  useProject: () => ({
    activeProject: {
      id: 'lean_energy',
      title: 'Lean Energy',
      providers: [
        { id: 'openalex', name: 'OpenAlex', type: 'live_api', connected: true },
        { id: 'crossref', name: 'Crossref', type: 'live_api', connected: true },
      ],
    },
    executeSearchStrategy: mockExecuteSearchStrategy,
    searchExecutionResult: mockSearchExecutionResult,
    selectedSearchResultIds: mockSelectedSearchResultIds,
    setSelectedSearchResultIds: mockSetSelectedSearchResultIds,
    importSelectedSearchResults: mockImportSelectedSearchResults,
    lastSearchImportResult: mockLastSearchImportResult,
  }),
}));

const storedStrategy: SearchStrategy = {
  strategy_id: '10000000-0000-0000-0000-000000000001',
  project_id: 'lean_energy',
  name: 'Lean energy',
  description: 'Protocol strategy',
  research_questions: ['How does lean affect energy use?'],
  concept_groups: [
    {
      group_id: 'lean',
      name: 'Lean',
      terms: ['lean manufacturing', 'lean production'],
      operator: 'or',
    },
  ],
  group_operator: 'and',
  constraints: {
    publication_year_from: 2015,
    publication_year_to: 2026,
    languages: ['en'],
    publication_types: ['article'],
    additional_limits: { open_access: true },
  },
  providers: ['openalex'],
  queries: [
    {
      query_id: '20000000-0000-0000-0000-000000000001',
      name: 'Core query',
      expression: { node_type: 'term', value: 'lean' },
      version: 1,
      description: null,
      created_by: null,
      notes: null,
      created_at: '2026-07-30T10:00:00Z',
    },
  ],
  version: 1,
  created_at: '2026-07-30T10:00:00Z',
  updated_at: '2026-07-30T10:00:00Z',
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/projects/lean_energy/search']}>
      <Routes>
        <Route path="/projects/:projectId/search" element={<SearchStrategyPage />} />
        <Route path="/projects/:projectId/sources" element={<div>Sources Ingestion page</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe('persistent Search Strategy GUI & Execution', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(projectApiService, 'getProjects').mockResolvedValue([
      {
        id: 'lean_energy',
        title: 'Lean Energy Project',
        description: '',
        protocolVersion: '1.0',
        status: 'active',
        createdAt: '', updatedAt: '',
        nextAction: { title: '', description: '', targetStageId: 'search', actionLabel: '', severity: 'normal' },
        conceptGroups: [], searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
        providers: [], imports: [], normalization: [], deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
        duplicateGroups: [], screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
        qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
        prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0, manualSourceBreakdown: {} },
      },
    ]);
    mockSearchExecutionResult = null;
    mockSelectedSearchResultIds = [];
    mockLastSearchImportResult = null;
    mockExecuteSearchStrategy.mockResolvedValue({
      execution_id: 'exec-1',
      strategy_id: storedStrategy.strategy_id,
      rendered_query: '"lean manufacturing" OR "lean production"',
      total_count: 1,
      returned_count: 1,
      next_cursor: null,
      has_more: false,
      results: [
        {
          id: 'rec-1',
          title: 'Real OpenAlex Paper on Lean Energy',
          authors: ['J. Smith'],
          year: 2024,
          provider: 'openalex',
          source_id: 'W123456',
          doi: '10.1000/182',
        },
      ],
      provider_errors: [],
    });

    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(
      structuredClone(storedStrategy),
    );
    vi.spyOn(projectApiService, 'saveSearchStrategy').mockImplementation(
      async (_projectId, payload) => ({
        ...structuredClone(storedStrategy),
        ...payload,
        strategy_id: payload.strategy_id ?? storedStrategy.strategy_id,
        project_id: 'lean_energy',
        queries: payload.queries.map((query, index) => ({
          ...query,
          query_id: `20000000-0000-0000-0000-00000000000${index + 1}`,
          version: query.version ?? 1,
          description: query.description ?? null,
          created_by: null,
          notes: null,
          created_at: storedStrategy.created_at,
        })),
        created_at: payload.created_at ?? storedStrategy.created_at,
        updated_at: '2026-07-30T11:00:00Z',
      }),
    );
  });

  it('1. GET strategii przy wejściu na stronę', async () => {
    renderPage();
    expect(screen.getByText('Ładowanie strategii wyszukiwania…')).toBeInTheDocument();
    await waitFor(() => {
      expect(projectApiService.getSearchStrategy).toHaveBeenCalledWith('lean_energy');
    });
    expect(await screen.findByDisplayValue('Lean')).toBeInTheDocument();
  });

  it('2. 404 otwiera pusty formularz z informacją o braku strategii', async () => {
    vi.mocked(projectApiService.getSearchStrategy).mockResolvedValue(null);
    renderPage();

    expect(await screen.findByText(/nie ma jeszcze zapisanej strategii/i)).toBeInTheDocument();
    expect(screen.getByTestId('boolean-query-preview')).toHaveTextContent('Dodaj grupy i terminy');
  });

  it('3. Zapisz wykonuje PUT i pozostaje na stronie bez nawigacji', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));

    await waitFor(() => {
      expect(projectApiService.saveSearchStrategy).toHaveBeenCalledWith(
        'lean_energy',
        expect.objectContaining({
          concept_groups: expect.arrayContaining([
            expect.objectContaining({ name: 'Lean' }),
          ]),
        }),
      );
    });
    expect(await screen.findByText('Strategia została zapisana.')).toBeInTheDocument();
    expect(screen.queryByText('Sources Ingestion page')).not.toBeInTheDocument();
  });

  it('4. Szukaj wykonuje PUT', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    fireEvent.click(screen.getByRole('button', { name: 'Szukaj' }));

    await waitFor(() => {
      expect(projectApiService.saveSearchStrategy).toHaveBeenCalledTimes(1);
    });
  });

  it('5. Po udanym PUT Szukaj wywołuje executeSearchStrategy', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    fireEvent.click(screen.getByRole('button', { name: 'Szukaj' }));

    await waitFor(() => {
      expect(mockExecuteSearchStrategy).toHaveBeenCalledTimes(1);
    });
  });

  it('6. Wyniki pojawiają się w SearchResultsSection na tej samej stronie', async () => {
    mockSearchExecutionResult = {
      project_id: 'lean_energy',
      status: 'validated',
      rendered_query: '"lean"',
      providers: ['openalex'],
      publication_year_from: 2015,
      publication_year_to: 2026,
      executed_at: '2026-07-30T10:00:00Z',
      total_count: 1,
      returned_count: 1,
      next_cursor: null,
      has_more: false,
      results: [
        {
          id: 'rec-100',
          title: 'Rzeczywisty wynik wyszukiwania OpenAlex',
          authors: ['A. Kowalski'],
          year: 2025,
          provider: 'openalex',
          source_id: 'W999999',
          doi: '10.1000/999',
        },
      ],
      provider_errors: [],
    };

    renderPage();
    await screen.findByDisplayValue('Lean');
    expect(screen.getByText('Rzeczywisty wynik wyszukiwania OpenAlex')).toBeInTheDocument();
  });

  it('7. Szukaj nie wywołuje navigate do /sources', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    fireEvent.click(screen.getByRole('button', { name: 'Szukaj' }));

    await waitFor(() => {
      expect(mockExecuteSearchStrategy).toHaveBeenCalled();
    });
    expect(screen.queryByText('Sources Ingestion page')).not.toBeInTheDocument();
  });

  it('8. Błąd PUT blokuje wyszukiwanie', async () => {
    vi.mocked(projectApiService.saveSearchStrategy).mockRejectedValue(
      new Error('Błąd zapisu w bazie data base'),
    );
    renderPage();
    await screen.findByDisplayValue('Lean');

    fireEvent.click(screen.getByRole('button', { name: 'Szukaj' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Błąd zapisu w bazie data base');
    expect(mockExecuteSearchStrategy).not.toHaveBeenCalled();
    expect(screen.queryByText('Sources Ingestion page')).not.toBeInTheDocument();
  });

  it('9. Błąd search execution wyświetla alert', async () => {
    mockExecuteSearchStrategy.mockRejectedValue(
      new Error('Awarie API providera OpenAlex'),
    );
    renderPage();
    await screen.findByDisplayValue('Lean');

    fireEvent.click(screen.getByRole('button', { name: 'Szukaj' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Awarie API providera OpenAlex');
  });

  it('10. Brak sekcji Podstawowe dane strategii oraz Pytania badawcze na ekranie', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    expect(screen.queryByText('Podstawowe dane strategii')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Nazwa strategii')).not.toBeInTheDocument();
    expect(screen.queryByText('Pytania badawcze')).not.toBeInTheDocument();
    expect(screen.queryByText('Dodaj pytanie badawcze')).not.toBeInTheDocument();
  });

  it('11. Brak pól Klucz, Wartość i przycisku + w formularzu ograniczeń', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    expect(screen.queryByLabelText('Nazwa dodatkowego ograniczenia')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Wartość dodatkowego ograniczenia')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Dodaj dodatkowe ograniczenie')).not.toBeInTheDocument();
  });

  it('12. Brak wyników demo lub mocków — SearchResultsSection pod formularzem jest zasilana z wyniku backendu', async () => {
    renderPage();
    await screen.findByDisplayValue('Lean');

    expect(screen.getByText('Brak wykonanych wyszukiwań.')).toBeInTheDocument();
    expect(screen.queryByText('Mock Result Record')).not.toBeInTheDocument();
  });

  it('13. 404 -> pusty formularz z pustą listą providerów -> blokada zapisu bez wyboru -> OpenAlex zaznaczalny -> zapis pierwszej strategii', async () => {
    vi.mocked(projectApiService.getSearchStrategy).mockResolvedValue(null);
    renderPage();

    // 1. 404 -> infobar o braku strategii
    expect(await screen.findByText(/nie ma jeszcze zapisanej strategii/i)).toBeInTheDocument();

    // 2. OpenAlex, Crossref i Semantic Scholar nie są domyślnie zaznaczone, ale są możliwe do zaznaczenia
    const openAlexCb = screen.getByRole('checkbox', { name: /OpenAlex/i });
    const crossrefCb = screen.getByRole('checkbox', { name: /Crossref/i });
    const semanticCb = screen.getByRole('checkbox', { name: /Semantic Scholar/i });

    expect(openAlexCb).not.toBeChecked();
    expect(crossrefCb).not.toBeChecked();
    expect(semanticCb).not.toBeChecked();
    expect(openAlexCb).not.toBeDisabled();
    expect(crossrefCb).not.toBeDisabled();
    expect(semanticCb).not.toBeDisabled();

    // Dodajmy grupę pojęć
    const groupInput = screen.getByRole('textbox', { name: 'Nazwa nowej grupy' });
    fireEvent.change(groupInput, { target: { value: 'Energy' } });
    fireEvent.click(screen.getByRole('button', { name: 'Dodaj grupę' }));

    const termInput = screen.getByRole('textbox', { name: 'Nowy termin grupy 1' });
    fireEvent.change(termInput, { target: { value: 'solar' } });
    fireEvent.keyDown(termInput, { key: 'Enter', code: 'Enter' });

    // 3. Próba zapisu bez zaznaczonego providera -> błąd walidacji
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wybierz co najmniej jednego providera.');
    expect(projectApiService.saveSearchStrategy).not.toHaveBeenCalled();

    // 4. Zaznaczenie OpenAlex i ponowny zapis -> pomyślna walidacja i PUT
    fireEvent.click(openAlexCb);
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));

    await waitFor(() => {
      expect(projectApiService.saveSearchStrategy).toHaveBeenCalledWith('lean_energy', expect.objectContaining({
        concept_groups: expect.arrayContaining([
          expect.objectContaining({ name: 'Energy', terms: ['solar'] }),
        ]),
        providers: ['openalex'],
      }));
    });

    expect(await screen.findByText(/Strategia została zapisana/i)).toBeInTheDocument();
    expect(screen.queryByText(/nie ma jeszcze zapisanej strategii/i)).not.toBeInTheDocument();
  });

  it('14. Błąd importu wyników wyświetla dedykowany komunikat błędów importu', async () => {
    mockSearchExecutionResult = {
      project_id: 'lean_energy',
      status: 'validated',
      rendered_query: '"lean"',
      providers: ['openalex'],
      publication_year_from: 2015,
      publication_year_to: 2026,
      executed_at: '2026-07-30T10:00:00Z',
      total_count: 1,
      returned_count: 1,
      next_cursor: null,
      has_more: false,
      results: [
        {
          id: 'rec-100',
          title: 'Wynik do importu',
          authors: ['A. Kowalski'],
          year: 2025,
          provider: 'openalex',
          source_id: 'W999999',
          doi: '10.1000/999',
        },
      ],
      provider_errors: [],
    };
    mockSelectedSearchResultIds = ['rec-100'];
    mockImportSelectedSearchResults.mockRejectedValue(
      new Error('Niepoprawne dane strategii: providers: Extra inputs are not permitted (HTTP 422).')
    );

    renderPage();
    await screen.findByDisplayValue('Lean');

    const importButton = screen.getByRole('button', { name: /Importuj zaznaczone/i });
    fireEvent.click(importButton);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Wyszukiwanie zakończone, ale nie udało się zaimportować wyników');
    expect(alert).toHaveTextContent('providers: Extra inputs are not permitted');
    expect(screen.queryByText('Nie udało się wykonać wyszukiwania')).not.toBeInTheDocument();
  });
});
