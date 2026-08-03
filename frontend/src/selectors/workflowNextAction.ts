import { WorkflowNavigationStatus } from '../types';

/**
 * Describes a single recommended next action derived purely from WorkflowNavigationStatus.
 *
 * This is the single source of truth for next-action derivation logic.
 * Both ProjectDashboardPage and NextActionCard import from here.
 * No mock data, no static project fields.
 */
export interface NextAction {
  title: string;
  description: string;
  /** Route segment appended to /projects/:projectId/ */
  targetStageId: string;
  actionLabel: string;
  severity: 'urgent' | 'normal';
}

/**
 * Derives the next recommended workflow action from real backend WorkflowNavigationStatus.
 *
 * Priority order:
 *   1. Search Strategy missing / error
 *   2. Sources missing / error
 *   3. Normalization not started
 *   4. Normalization error
 *   5. Deduplication pending review
 *   6. Deduplication error
 *   7. All stages 1–4 complete
 *
 * Returns null when the status object is not yet available (loading state).
 */
export function deriveNextAction(status: WorkflowNavigationStatus): NextAction | null {
  // Stage 1: Search Strategy
  if (status.search.state === 'not_started' || status.search.state === 'error') {
    return {
      title: 'Zdefiniuj Strategię Wyszukiwania',
      description:
        'Projekt nie ma jeszcze skonfigurowanej strategii wyszukiwania. Utwórz grupy pojęć i wybierz dostawców wyszukiwania.',
      targetStageId: 'search',
      actionLabel: 'Konfiguruj Strategię',
      severity: 'normal',
    };
  }

  // Stage 2: Sources / Imports
  if (status.sources.state === 'not_started' || status.sources.state === 'error') {
    return {
      title: 'Importuj Źródła Bibliograficzne',
      description:
        'Strategia wyszukiwania jest gotowa. Wykonaj wyszukiwanie lub zaimportuj pliki bibliograficzne (BibTeX, RIS).',
      targetStageId: 'sources',
      actionLabel: 'Przejdź do Importu',
      severity: 'normal',
    };
  }

  // Stage 3: Normalization — not started
  if (status.normalization.state === 'not_started') {
    const importCount = status.sources.count ?? 0;
    return {
      title: 'Uruchom Normalizację',
      description: `Zaimportowano ${importCount} ${importCount === 1 ? 'import' : 'importów'}. Uruchom normalizację, aby ujednolicić dane bibliograficzne przed deduplikacją.`,
      targetStageId: 'normalize',
      actionLabel: 'Uruchom Normalizację',
      severity: 'normal',
    };
  }

  // Stage 3: Normalization — error
  if (status.normalization.state === 'error') {
    return {
      title: 'Napraw Błędy Normalizacji',
      description:
        'Ostatnie wykonanie normalizacji zakończyło się błędami. Sprawdź dziennik i uruchom ponownie.',
      targetStageId: 'normalize',
      actionLabel: 'Sprawdź Normalizację',
      severity: 'urgent',
    };
  }

  // Stage 4: Deduplication — pending review
  if (status.deduplication.state === 'pending_action' && status.deduplication.pendingGroups > 0) {
    return {
      title: 'Oceń Grupy Duplikatów',
      description: `Wykryto ${status.deduplication.pendingGroups} grup kandydatów na duplikaty oczekujących na decyzję badacza.`,
      targetStageId: 'dedup',
      actionLabel: 'Przejdź do Deduplikacji',
      severity: 'urgent',
    };
  }

  // Stage 4: Deduplication — error
  if (status.deduplication.state === 'error') {
    return {
      title: 'Błąd Deduplikacji',
      description:
        'Nie udało się pobrać danych o grupach duplikatów. Sprawdź połączenie z backendem.',
      targetStageId: 'dedup',
      actionLabel: 'Przejdź do Deduplikacji',
      severity: 'urgent',
    };
  }

  // All four implemented stages completed
  if (
    status.search.state === 'completed' &&
    (status.sources.state === 'completed' || status.sources.state === 'warning') &&
    (status.normalization.state === 'completed' || status.normalization.state === 'warning') &&
    status.deduplication.state === 'completed'
  ) {
    return {
      title: 'Etapy 1–4 ukończone',
      description:
        'Strategia, importy, normalizacja i deduplikacja są ukończone. Etapy screeningu i oceny jakości będą dostępne w kolejnych wersjach.',
      targetStageId: 'dedup',
      actionLabel: 'Podsumowanie Deduplikacji',
      severity: 'normal',
    };
  }

  return null;
}
