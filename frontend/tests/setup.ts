import '@testing-library/jest-dom';
import { vi, beforeEach } from 'vitest';
import { projectApiService } from '../src/services/api/projectApi';
import { SLRProject } from '../src/types';

const DEFAULT_TEST_PROJECTS: SLRProject[] = [
  {
    id: 'lean_energy',
    title: 'Lean Management and Energy Efficiency in Industrial Manufacturing',
    description: 'Test project description',
    protocolVersion: '0.6',
    status: 'active',
    createdAt: '2026-07-01T10:00:00Z',
    updatedAt: '2026-07-28T16:45:00Z',
    nextAction: { title: 'Next Action', description: 'Desc', targetStageId: 'search', actionLabel: 'Label', severity: 'normal' },
    conceptGroups: [],
    searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
    providers: [
      { id: 'openalex', name: 'OpenAlex Works API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
      { id: 'crossref', name: 'Crossref REST API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
      { id: 'semantic_scholar', name: 'Semantic Scholar Graph API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
    ],
    imports: [],
    normalization: [],
    deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
    duplicateGroups: [],
    screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
    qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
  },
  {
    id: 'ai_architecture',
    title: 'Architectural Tactics for LLM Integration in Enterprise Systems',
    description: 'Test project description',
    protocolVersion: '0.2',
    status: 'active',
    createdAt: '2026-07-15T09:00:00Z',
    updatedAt: '2026-07-27T11:20:00Z',
    nextAction: { title: 'Next Action', description: 'Desc', targetStageId: 'search', actionLabel: 'Label', severity: 'normal' },
    conceptGroups: [],
    searchFilters: { publicationYearFrom: null, publicationYearTo: null, languages: [], publicationTypes: [], fullTextOnly: false },
    providers: [
      { id: 'openalex', name: 'OpenAlex Works API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
      { id: 'crossref', name: 'Crossref REST API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
      { id: 'semantic_scholar', name: 'Semantic Scholar Graph API', type: 'live_api', connected: true, status: 'idle', resultsCount: 0, lastRunTimestamp: null },
    ],
    imports: [],
    normalization: [],
    deduplication: { recordsBeforeDedup: 0, identifierLinkedGroupsCount: 0, recordsAfterResultMerger: 0, candidateGroupsPendingUserReview: 0, status: 'pending' },
    duplicateGroups: [],
    screening: { titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 }, status: 'pending' },
    qualityAssessment: { totalToAssess: 0, completedAssessments: 0, reviewerConflictsCount: 0, status: 'pending' },
    prismaMetrics: { recordsIdentifiedProviders: 0, recordsIdentifiedImports: 0, totalIdentified: 0, recordsAfterNormalization: 0, recordsBeforeDedup: 0, recordsAfterTechnicalMerger: 0, duplicateGroupsPendingReview: 0, recordsScreenedTitleAbstract: 0, recordsScreenedFullText: 0, studiesIncludedSynthesis: 0 },
  },
];

beforeEach(() => {
  vi.spyOn(projectApiService, 'getProjects').mockResolvedValue(DEFAULT_TEST_PROJECTS);
});
