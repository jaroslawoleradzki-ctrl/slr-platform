import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { ProjectDashboardPage } from '../src/pages/ProjectDashboardPage';
import { Sidebar } from '../src/components/layout/Sidebar';
import { WorkflowStepper } from '../src/components/workflow/WorkflowStepper';
import { projectApiService } from '../src/services/api/projectApi';
import { deriveNextAction } from '../src/selectors/workflowNextAction';
import {
  ApiDuplicateGroupListResponse,
  BibliographicImportHistoryRecord,
  NormalizationResponse,
  SearchStrategy,
  WorkflowNavigationStatus,
} from '../src/types';

// ─── Shared fixtures ───────────────────────────────────────────────────────────

const STRATEGY_2_GROUPS: SearchStrategy = {
  strategy_id: 'st-1',
  project_id: 'lean_energy',
  name: 'Strategy',
  description: null,
  research_questions: [],
  concept_groups: [
    { group_id: 'cg1', name: 'Domain A', terms: ['term'], operator: 'or' },
    { group_id: 'cg2', name: 'Domain B', terms: ['term2'], operator: 'or' },
  ],
  group_operator: 'and',
  constraints: { publication_year_from: null, publication_year_to: null, languages: [], publication_types: [], additional_limits: {} },
  providers: ['openalex'],
  queries: [],
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const TWO_IMPORTS: BibliographicImportHistoryRecord[] = [
  { import_id: 'i1', project_id: 'lean_energy', source_type: 'file', filename: 'file.bib', format: 'BibTeX', provider: null, query: null, records_count: 50, total_available: null, status: 'success', created_at: '2026-01-02T10:00:00Z', warnings: [] },
  { import_id: 'i2', project_id: 'lean_energy', source_type: 'file', filename: 'file2.ris', format: 'RIS',    provider: null, query: null, records_count: 30, total_available: null, status: 'success', created_at: '2026-01-03T10:00:00Z', warnings: [] },
];

const OK_NORM: NormalizationResponse = {
  run_id: 'r1', project_id: 'lean_energy', status: 'completed',
  processed_records: 80, clean_records: 80, warnings_count: 0, errors_count: 0,
  rules_applied: [], audit_trail: [],
  started_at: '', completed_at: '', executed_at: '',
};

const DEDUP_5_PENDING: ApiDuplicateGroupListResponse = {
  project_id: 'lean_energy',
  total_groups_count: 5,
  groups: Array.from({ length: 5 }, (_, i) => ({
    group_id: `g-${i}`, reason: 'DOI', records_count: 2, status: 'PENDING' as const, shared_identifiers: [], records: [],
  })),
};

const DEDUP_REVIEWED: ApiDuplicateGroupListResponse = {
  project_id: 'lean_energy',
  total_groups_count: 3,
  groups: [
    { group_id: 'g-0', reason: 'DOI', records_count: 2, status: 'APPROVE', shared_identifiers: [], records: [] },
    { group_id: 'g-1', reason: 'DOI', records_count: 2, status: 'APPROVE', shared_identifiers: [], records: [] },
    { group_id: 'g-2', reason: 'DOI', records_count: 2, status: 'REJECT',  shared_identifiers: [], records: [] },
  ],
};

const EMPTY_DEDUP: ApiDuplicateGroupListResponse = { project_id: 'lean_energy', total_groups_count: 0, groups: [] };

// ─── Render helpers ────────────────────────────────────────────────────────────

const renderDashboard = (path = '/projects/lean_energy/dashboard') =>
  render(
    <ProjectProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/projects/:projectId/dashboard" element={<ProjectDashboardPage />} />
          <Route path="/projects/:projectId/search"    element={<div>Search page</div>} />
        </Routes>
      </MemoryRouter>
    </ProjectProvider>
  );

const renderWithNav = () =>
  render(
    <ProjectProvider>
      <MemoryRouter initialEntries={['/projects/lean_energy/dashboard']}>
        <Routes>
          <Route path="/projects/:projectId/dashboard" element={<><WorkflowStepper /><Sidebar /><ProjectDashboardPage /></>} />
        </Routes>
      </MemoryRouter>
    </ProjectProvider>
  );

// ─── Suite A: unit tests for deriveNextAction (shared selector) ───────────────

describe('deriveNextAction — shared selector, single source of truth', () => {
  const allComplete: WorkflowNavigationStatus = {
    search:            { state: 'completed',    count: 2,    label: '2 grup' },
    sources:           { state: 'completed',    count: 2,    label: '2 importów' },
    normalization:     { state: 'completed',    count: 0,    label: 'OK' },
    deduplication:     { state: 'completed',    totalGroups: 3, pendingGroups: 0, approvedGroups: 2, rejectedGroups: 1, label: 'Oceniono' },
    screening:         { state: 'not_available', label: 'Niedostępne' },
    qualityAssessment: { state: 'not_available', label: 'Niedostępne' },
    dataExtraction:    { state: 'not_available', label: 'Niedostępne' },
    exports:           { state: 'not_available', label: 'Niedostępne' },
  };

  it('no search strategy → targetStageId = "search", severity = "normal"', () => {
    const a = deriveNextAction({ ...allComplete, search: { state: 'not_started', count: null, label: null } });
    expect(a?.targetStageId).toBe('search');
    expect(a?.severity).toBe('normal');
  });

  it('search error → targetStageId = "search"', () => {
    expect(deriveNextAction({ ...allComplete, search: { state: 'error', count: null, label: 'Błąd' } })?.targetStageId).toBe('search');
  });

  it('no imports → targetStageId = "sources", severity = "normal"', () => {
    const a = deriveNextAction({ ...allComplete, sources: { state: 'not_started', count: null, label: null } });
    expect(a?.targetStageId).toBe('sources');
    expect(a?.severity).toBe('normal');
  });

  it('normalization not started → targetStageId = "normalize", severity = "normal"', () => {
    const a = deriveNextAction({ ...allComplete, normalization: { state: 'not_started', count: null, label: 'Pending' } });
    expect(a?.targetStageId).toBe('normalize');
    expect(a?.severity).toBe('normal');
  });

  it('normalization error → targetStageId = "normalize", severity = "urgent"', () => {
    const a = deriveNextAction({ ...allComplete, normalization: { state: 'error', count: 2, label: '2 błędów' } });
    expect(a?.targetStageId).toBe('normalize');
    expect(a?.severity).toBe('urgent');
  });

  it('dedup pending → targetStageId = "dedup", severity = "urgent", description contains group count', () => {
    const a = deriveNextAction({
      ...allComplete,
      deduplication: { state: 'pending_action', totalGroups: 5, pendingGroups: 5, approvedGroups: 0, rejectedGroups: 0, label: '5 do oceny' },
    });
    expect(a?.targetStageId).toBe('dedup');
    expect(a?.severity).toBe('urgent');
    expect(a?.description).toContain('5 grup');
  });

  it('dedup error → targetStageId = "dedup", severity = "urgent"', () => {
    const a = deriveNextAction({
      ...allComplete,
      deduplication: { state: 'error', totalGroups: 0, pendingGroups: 0, approvedGroups: 0, rejectedGroups: 0, label: 'Błąd' },
    });
    expect(a?.targetStageId).toBe('dedup');
    expect(a?.severity).toBe('urgent');
  });

  it('all stages complete → summary action pointing to dedup', () => {
    const a = deriveNextAction(allComplete);
    expect(a?.targetStageId).toBe('dedup');
    expect(a?.severity).toBe('normal');
    expect(a?.title).toContain('ukończone');
  });

  it('normalization warning does not block dedup as next action', () => {
    const a = deriveNextAction({
      ...allComplete,
      normalization: { state: 'warning', count: 5, label: '5 ostrzeżeń' },
      deduplication: { state: 'pending_action', totalGroups: 3, pendingGroups: 3, approvedGroups: 0, rejectedGroups: 0, label: '3 do oceny' },
    });
    expect(a?.targetStageId).toBe('dedup');
  });
});

// ─── Suite B: ProjectDashboardPage integration ────────────────────────────────

describe('ProjectDashboardPage — real data, no mock values', () => {
  beforeEach(() => vi.restoreAllMocks());

  // ── Loading ──────────────────────────────────────────────────────────────────
  it('shows loading indicator while status is fetched', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockReturnValue(new Promise(() => {}));
    vi.spyOn(projectApiService, 'getBibliographicImports').mockReturnValue(new Promise(() => {}));
    vi.spyOn(projectApiService, 'getNormalization').mockReturnValue(new Promise(() => {}));
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockReturnValue(new Promise(() => {}));
    renderDashboard();
    expect(screen.getByText(/Ładowanie statusu projektu/i)).toBeInTheDocument();
  });

  // ── No mock values leak ──────────────────────────────────────────────────────
  it('does not render static mock numbers (45, 425, 2105, "Triage", "Finalna Synteza")', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(EMPTY_DEDUP);
    renderDashboard();
    await waitFor(() => expect(screen.queryByText(/Ładowanie statusu projektu/i)).not.toBeInTheDocument());
    expect(screen.queryByText(/\b45\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\b425\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Triage Tytułów/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Finalna Synteza/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Live Providers/i)).not.toBeInTheDocument();
  });

  // ── Empty state ──────────────────────────────────────────────────────────────
  it('shows "Brak danych" for stages with no backend data', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(EMPTY_DEDUP);
    renderDashboard();
    await waitFor(() => expect(screen.queryByText(/Ładowanie statusu projektu/i)).not.toBeInTheDocument());
    expect(screen.getAllByText('Brak danych').length).toBeGreaterThanOrEqual(1);
  });

  // ── Real data for each stage ─────────────────────────────────────────────────
  it('renders real data for all four stages: group count, import count, normalization, dedup', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(OK_NORM);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(DEDUP_5_PENDING);
    renderDashboard();
    await waitFor(() => expect(screen.getByText('5 grup')).toBeInTheDocument());
    expect(screen.getAllByText(/2 grup/i).length).toBeGreaterThanOrEqual(1);   // search: "2 grup"
    expect(screen.getByText('2 importy')).toBeInTheDocument();
    expect(screen.getByText('Wykonano')).toBeInTheDocument();                  // normalization completed
    expect(screen.getByText('OK')).toBeInTheDocument();                        // normalization secondary
    expect(screen.getByText(/5 oczekuje/i)).toBeInTheDocument();               // dedup secondary
  });

  // ── Normalization: error/warning primary is the label, not a bare number ─────
  it('normalization warning — primary value is label "X ostrzeżeń", not a bare number', async () => {
    const warnNorm: NormalizationResponse = { ...OK_NORM, status: 'warning', warnings_count: 13 };
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(warnNorm);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(EMPTY_DEDUP);
    renderDashboard();
    await waitFor(() => expect(screen.getByText('13 ostrzeżeń')).toBeInTheDocument());
    // Bare "13" must not appear as standalone text
    expect(screen.queryByText('13', { exact: true })).not.toBeInTheDocument();
  });

  // ── Dedup APPROVE/REJECT counts ──────────────────────────────────────────────
  it('renders APPROVE/REJECT breakdown when all dedup groups reviewed', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(OK_NORM);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(DEDUP_REVIEWED);
    renderDashboard();
    await waitFor(() => expect(screen.getByText('3 grup')).toBeInTheDocument());
    expect(screen.getByText(/2 APPROVE · 1 REJECT/i)).toBeInTheDocument();
  });

  // ── Stages 5–8 always Niedostępne, no navigation ────────────────────────────
  it('stages 5–8 are always Niedostępne and have aria-disabled, not clickable', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue([]);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(null);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(EMPTY_DEDUP);
    renderDashboard();
    await waitFor(() => expect(screen.queryByText(/Ładowanie statusu projektu/i)).not.toBeInTheDocument());
    expect(screen.getAllByText('Niedostępne').length).toBeGreaterThanOrEqual(4);
    expect(screen.getByText('5. Screening')).toBeInTheDocument();
    expect(screen.getByText('8. Exports & PRISMA')).toBeInTheDocument();
    // All Niedostępne rows must have aria-disabled
    document.querySelectorAll('[aria-disabled="true"]').forEach((el) => {
      expect(el).toBeInTheDocument();
    });
  });

  // ── Partial failure: dedup error does not blank other stages ─────────────────
  it('dedup endpoint failure does not erase search/sources/normalization data', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(OK_NORM);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockRejectedValue(new Error('500'));
    renderDashboard();
    await waitFor(() => expect(screen.getAllByText(/2 grup/i).length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText('2 importy')).toBeInTheDocument();
    expect(screen.getByText('Wykonano')).toBeInTheDocument();
  });

  // ── Stage card navigation ────────────────────────────────────────────────────
  it('clicking search stage card navigates to /search with correct projectId', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(OK_NORM);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(EMPTY_DEDUP);
    renderDashboard('/projects/lean_energy/dashboard');
    await waitFor(() => expect(screen.getAllByText(/2 grup/i).length).toBeGreaterThanOrEqual(1));
    fireEvent.click(document.getElementById('stage-card-search')!);
    await waitFor(() => expect(screen.getByText('Search page')).toBeInTheDocument());
  });

  // ── Dashboard ↔ Sidebar ↔ WorkflowStepper consistency ──────────────────────
  it('Dashboard, Sidebar, and WorkflowStepper show consistent dedup pending count', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(OK_NORM);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(DEDUP_5_PENDING);
    renderWithNav();
    await waitFor(() => expect(screen.getByText('5 grup')).toBeInTheDocument());
    expect(screen.getByText('5 do oceny')).toBeInTheDocument(); // Sidebar badge
    expect(screen.getByText('5')).toBeInTheDocument();          // WorkflowStepper alertCount
  });

  it('Sidebar shows "Oceniono" when all dedup groups reviewed', async () => {
    vi.spyOn(projectApiService, 'getSearchStrategy').mockResolvedValue(STRATEGY_2_GROUPS);
    vi.spyOn(projectApiService, 'getBibliographicImports').mockResolvedValue(TWO_IMPORTS);
    vi.spyOn(projectApiService, 'getNormalization').mockResolvedValue(OK_NORM);
    vi.spyOn(projectApiService, 'getDuplicateGroups').mockResolvedValue(DEDUP_REVIEWED);
    renderWithNav();
    await waitFor(() => expect(screen.getByText('3 grup')).toBeInTheDocument());
    expect(screen.getByText('Oceniono')).toBeInTheDocument();
    expect(screen.getByText(/2 APPROVE · 1 REJECT/i)).toBeInTheDocument();
  });
});
