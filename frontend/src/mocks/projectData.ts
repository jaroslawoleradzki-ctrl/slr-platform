import { SLRProject } from '../types';

export const MOCK_PROJECTS: SLRProject[] = [
  {
    id: 'lean_energy',
    title: 'Lean Management and Energy Efficiency in Industrial Manufacturing',
    description: 'Systematic review investigating operational lean principles (TPS, Kaizen, JIT) and their quantitative impact on industrial energy performance and consumption reduction.',
    protocolVersion: '0.6',
    status: 'active',
    createdAt: '2026-07-01T10:00:00Z',
    updatedAt: '2026-07-28T16:45:00Z',
    nextAction: {
      title: 'Ocena Grup Duplikatów (Deduplikacja)',
      description: 'Techniczny ResultMerger wykonał wstępne scalenie identyfikatorów. Wykryto grupy kandydatów na duplikaty oczekujące na przegląd badacza.',
      targetStageId: 'dedup',
      actionLabel: 'Przejdź do Oceny Duplikatów',
      severity: 'urgent',
    },
    conceptGroups: [
      {
        id: 'cg-1',
        name: 'Lean Management Terms',
        terms: [
          'Lean Management',
          'Lean Manufacturing',
          'Lean Production',
          'Toyota Production System',
          'Kaizen',
          'Continuous Improvement',
          'Just-in-Time'
        ]
      },
      {
        id: 'cg-2',
        name: 'Energy Efficiency Terms',
        terms: [
          'Energy Efficiency',
          'Energy Consumption',
          'Energy Performance',
          'Energy Saving',
          'Energy Management',
          'Energy Use'
        ]
      },
      {
        id: 'cg-3',
        name: 'Manufacturing Terms',
        terms: [
          'Manufacturing',
          'Production',
          'Industrial',
          'Factory'
        ]
      }
    ],
    searchFilters: {
      publicationYearFrom: 2015,
      publicationYearTo: 2026,
      languages: ['en', 'pl'],
      publicationTypes: ['article', 'review', 'conference_paper'],
      fullTextOnly: false,
    },
    providers: [
      {
        id: 'openalex',
        name: 'OpenAlex Works API',
        type: 'live_api',
        connected: true,
        status: 'completed',
        resultsCount: 840,
        lastRunTimestamp: '2026-07-28T14:20:00Z'
      },
      {
        id: 'crossref',
        name: 'Crossref REST API',
        type: 'live_api',
        connected: true,
        status: 'completed',
        resultsCount: 620,
        lastRunTimestamp: '2026-07-28T14:22:00Z'
      },
      {
        id: 'semantic_scholar',
        name: 'Semantic Scholar Graph API',
        type: 'live_api',
        connected: true,
        status: 'completed',
        resultsCount: 410,
        lastRunTimestamp: '2026-07-28T14:25:00Z'
      }
    ],
    imports: [],
    normalization: [],
    deduplication: {
      recordsBeforeDedup: 0,
      identifierLinkedGroupsCount: 0,
      recordsAfterResultMerger: 0,
      candidateGroupsPendingUserReview: 0,
      status: 'pending'
    },
    duplicateGroups: [],
    screening: {
      titleAbstract: {
        pending: 0,
        included: 0,
        excluded: 0,
        unresolved: 0,
        total: 0
      },
      fullText: {
        pending: 0,
        included: 0,
        excluded: 0,
        unresolved: 0,
        total: 0
      },
      status: 'pending'
    },
    qualityAssessment: {
      totalToAssess: 0,
      completedAssessments: 0,
      reviewerConflictsCount: 0,
      status: 'pending'
    },
    prismaMetrics: {
      recordsIdentifiedProviders: 0,
      recordsIdentifiedImports: 0,
      totalIdentified: 0,
      recordsAfterNormalization: 0,
      recordsBeforeDedup: 0,
      recordsAfterTechnicalMerger: 0,
      duplicateGroupsPendingReview: 0,
      recordsScreenedTitleAbstract: 0,
      recordsScreenedFullText: 0,
      studiesIncludedSynthesis: 0
    }
  },
  {
    id: 'ai_architecture',
    title: 'Architectural Tactics for LLM Integration in Enterprise Systems',
    description: 'Systematic literature review on software architecture patterns, latency mitigation, and cost-optimization tactics when embedding LLMs into critical backend services.',
    protocolVersion: '0.2',
    status: 'active',
    createdAt: '2026-07-15T09:00:00Z',
    updatedAt: '2026-07-27T11:20:00Z',
    nextAction: {
      title: 'Uruchomienie Wyszukiwania w Providerach',
      description: 'Zdefiniowano grupy pojęć i zapytania search strategy. Następnym krokiem jest uruchomienie zapytań w API OpenAlex i Crossref.',
      targetStageId: 'sources',
      actionLabel: 'Uruchom Live Search',
      severity: 'normal'
    },
    conceptGroups: [
      {
        id: 'cg-10',
        name: 'LLM & Generative AI',
        terms: ['Large Language Models', 'LLM', 'Generative AI', 'Foundation Models']
      },
      {
        id: 'cg-11',
        name: 'Software Architecture',
        terms: ['Software Architecture', 'Architectural Tactics', 'Design Patterns', 'Microservices']
      }
    ],
    searchFilters: {
      publicationYearFrom: 2022,
      publicationYearTo: 2026,
      languages: ['en'],
      publicationTypes: ['article', 'conference_paper'],
      fullTextOnly: true,
    },
    providers: [
      {
        id: 'openalex',
        name: 'OpenAlex Works API',
        type: 'live_api',
        connected: true,
        status: 'idle',
        resultsCount: 0,
        lastRunTimestamp: null
      },
      {
        id: 'crossref',
        name: 'Crossref REST API',
        type: 'live_api',
        connected: true,
        status: 'idle',
        resultsCount: 0,
        lastRunTimestamp: null
      }
    ],
    imports: [],
    normalization: [],
    deduplication: {
      recordsBeforeDedup: 0,
      identifierLinkedGroupsCount: 0,
      recordsAfterResultMerger: 0,
      candidateGroupsPendingUserReview: 0,
      status: 'pending'
    },
    duplicateGroups: [],
    screening: {
      titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 },
      fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 },
      status: 'pending'
    },
    qualityAssessment: {
      totalToAssess: 0,
      completedAssessments: 0,
      reviewerConflictsCount: 0,
      status: 'pending'
    },
    prismaMetrics: {
      recordsIdentifiedProviders: 0,
      recordsIdentifiedImports: 0,
      totalIdentified: 0,
      recordsAfterNormalization: 0,
      recordsBeforeDedup: 0,
      recordsAfterTechnicalMerger: 0,
      duplicateGroupsPendingReview: 0,
      recordsScreenedTitleAbstract: 0,
      recordsScreenedFullText: 0,
      studiesIncludedSynthesis: 0
    }
  }
];
