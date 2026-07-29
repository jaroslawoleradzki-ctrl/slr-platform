export type StageStatus = 'completed' | 'in_progress' | 'pending_action' | 'pending' | 'error';

export interface ConceptGroup {
  id: string;
  name: string;
  terms: string[];
}

export interface SearchFilters {
  publicationYearFrom: number | null;
  publicationYearTo: number | null;
  languages: string[];
  publicationTypes: string[];
  fullTextOnly: boolean;
}

export interface SearchProviderStatus {
  id: string;
  name: string;
  type: 'live_api' | 'manual_import';
  connected: boolean;
  status: 'completed' | 'running' | 'failed' | 'idle';
  resultsCount: number;
  lastRunTimestamp: string | null;
  errorMessage?: string;
}

export interface ImportFileRecord {
  id: string;
  filename: string;
  format: 'BibTeX' | 'RIS';
  recordsCount: number;
  importedAt: string;
  status: 'success' | 'warning' | 'error';
  warnings?: string[];
}

export interface NormalizationStatus {
  completed: boolean;
  totalRecordsProcessed: number;
  cleanRecordsCount: number;
  warningsCount: number;
  errorsCount: number;
  warningsLog: string[];
}

export interface DeduplicationSummary {
  recordsBeforeDedup: number;
  identifierLinkedGroupsCount: number;
  recordsAfterResultMerger: number;
  candidateGroupsPendingUserReview: number;
  status: 'completed' | 'pending_action' | 'in_progress' | 'pending';
}

export interface DuplicateGroupPreview {
  groupId: string;
  similarityScore: number;
  reason: string;
  records: {
    id: string;
    title: string;
    authors: string;
    year: number;
    source: string;
    doi?: string;
  }[];
}

export interface ScreeningStatus {
  titleAbstract: {
    pending: number;
    included: number;
    excluded: number;
    unresolved: number;
    total: number;
  };
  fullText: {
    pending: number;
    included: number;
    excluded: number;
    unresolved: number;
    total: number;
  };
  status: 'in_progress' | 'pending' | 'completed';
}

export interface QualityAssessmentStatus {
  totalToAssess: number;
  completedAssessments: number;
  reviewerConflictsCount: number;
  status: 'in_progress' | 'pending' | 'completed';
}

export interface PrismaFunnelMetrics {
  recordsIdentifiedProviders: number;
  recordsIdentifiedImports: number;
  totalIdentified: number;
  recordsAfterNormalization: number;
  recordsBeforeDedup: number;
  recordsAfterTechnicalMerger: number;
  duplicateGroupsPendingReview: number;
  recordsScreenedTitleAbstract: number;
  recordsScreenedFullText: number;
  studiesIncludedSynthesis: number;
}

export interface SLRProject {
  id: string;
  title: string;
  description: string;
  protocolVersion: string;
  createdAt: string;
  updatedAt: string;
  nextAction: {
    title: string;
    description: string;
    targetStageId: string;
    actionLabel: string;
    severity: 'urgent' | 'normal';
  };
  conceptGroups: ConceptGroup[];
  searchFilters: SearchFilters;
  providers: SearchProviderStatus[];
  imports: ImportFileRecord[];
  normalization: NormalizationStatus[];
  deduplication: DeduplicationSummary;
  duplicateGroups: DuplicateGroupPreview[];
  screening: ScreeningStatus;
  qualityAssessment: QualityAssessmentStatus;
  prismaMetrics: PrismaFunnelMetrics;
}
