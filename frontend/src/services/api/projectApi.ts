import { SLRProject } from '../../types';
import { MOCK_PROJECTS } from '../../mocks/projectData';

export interface ProjectApiService {
  getProjects(): Promise<SLRProject[]>;
  getProjectById(id: string): Promise<SLRProject | null>;
  createProject(title: string, description: string, protocolVersion: string): Promise<SLRProject>;
}

class MockProjectApiService implements ProjectApiService {
  private projects: SLRProject[] = [...MOCK_PROJECTS];

  async getProjects(): Promise<SLRProject[]> {
    return [...this.projects];
  }

  async getProjectById(id: string): Promise<SLRProject | null> {
    const project = this.projects.find((p) => p.id === id);
    return project ? { ...project } : null;
  }

  async createProject(title: string, description: string, protocolVersion: string): Promise<SLRProject> {
    await new Promise((resolve) => setTimeout(resolve, 200));
    const newId = title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || `proj_${Date.now()}`;
    const newProject: SLRProject = {
      id: newId,
      title,
      description,
      protocolVersion: protocolVersion || '0.1',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nextAction: {
        title: 'Zdefiniuj Zapytanie i Grupy Pojęć',
        description: 'Nowy projekt został utworzony. Przejdź do edytora zapytań i zdefiniuj grupy pojęć dla przeglądu.',
        targetStageId: 'search',
        actionLabel: 'Konfiguruj Strategię Wyszukiwania',
        severity: 'normal'
      },
      conceptGroups: [
        {
          id: `cg-${Date.now()}-1`,
          name: 'Main Domain Terms',
          terms: ['Systematic Review', 'Literature Analysis']
        }
      ],
      searchFilters: {
        publicationYearFrom: 2018,
        publicationYearTo: 2026,
        languages: ['en'],
        publicationTypes: ['article', 'review'],
        fullTextOnly: false,
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
    };

    this.projects.unshift(newProject);
    return newProject;
  }
}

export const projectApiService: ProjectApiService = new MockProjectApiService();
