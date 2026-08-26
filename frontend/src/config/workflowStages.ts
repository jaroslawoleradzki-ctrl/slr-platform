import { WorkflowNavigationStatus, WorkflowStageState } from '../types';

export interface WorkflowStageDefinition {
  id: string;
  number: number;
  /** Full label used by the sidebar navigation */
  fullLabel: string;
  /** Compact label used by the top workflow overview bar */
  shortLabel: string;
  /** Path segment appended to /projects/:projectId/ */
  pathSuffix: string;
  /** Key inside WorkflowNavigationStatus; null when the stage has no backend status yet */
  statusKey: keyof WorkflowNavigationStatus | null;
}

export const WORKFLOW_STAGES: readonly WorkflowStageDefinition[] = [
  { id: 'search', number: 1, fullLabel: 'Search Strategy', shortLabel: 'Search', pathSuffix: 'search', statusKey: 'search' },
  { id: 'sources', number: 2, fullLabel: 'Sources & Imports', shortLabel: 'Sources', pathSuffix: 'sources', statusKey: 'sources' },
  { id: 'normalize', number: 3, fullLabel: 'Normalization', shortLabel: 'Normalize', pathSuffix: 'normalize', statusKey: 'normalization' },
  { id: 'dedup', number: 4, fullLabel: 'Deduplication', shortLabel: 'Dedupe', pathSuffix: 'dedup', statusKey: 'deduplication' },
  { id: 'screening', number: 5, fullLabel: 'Screening', shortLabel: 'Screening', pathSuffix: 'screen/title-abstract', statusKey: 'screening' },
  { id: 'quality-assessment', number: 6, fullLabel: 'Quality Assessment', shortLabel: 'QA', pathSuffix: 'quality-assessment', statusKey: 'qualityAssessment' },
  { id: 'extract', number: 7, fullLabel: 'Data Extraction', shortLabel: 'Extraction', pathSuffix: 'extract', statusKey: 'dataExtraction' },
  { id: 'synthesis', number: 8, fullLabel: 'Evidence Synthesis', shortLabel: 'Synthesis', pathSuffix: 'synthesis', statusKey: null },
  { id: 'exports', number: 9, fullLabel: 'Exports & PRISMA', shortLabel: 'Export', pathSuffix: 'exports', statusKey: 'exports' },
];

export const buildStagePath = (projectId: string | undefined, pathSuffix: string): string =>
  projectId ? `/projects/${projectId}/${pathSuffix}` : '/projects';

/**
 * Single source of per-stage display state for both the sidebar and the top bar.
 * Evidence Synthesis has no backend status yet; it is derived from upstream stages
 * instead of being hardcoded.
 */
export const getWorkflowStageState = (
  workflowStatus: WorkflowNavigationStatus | null,
  stage: WorkflowStageDefinition
): WorkflowStageState => {
  if (!stage.statusKey) {
    if (!workflowStatus) return 'not_started';
    const extractionDone = workflowStatus.dataExtraction.state === 'completed';
    const exportReady = workflowStatus.exports.state === 'pending_action';
    return extractionDone || exportReady ? 'in_progress' : 'not_started';
  }
  return workflowStatus?.[stage.statusKey]?.state ?? 'not_started';
};
