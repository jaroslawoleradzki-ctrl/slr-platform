import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LivePrismaFlowChart } from '../src/components/workflow/LivePrismaFlowChart';
import type { PrismaFunnelMetrics } from '../src/types';

const metrics: PrismaFunnelMetrics = {
  recordsIdentifiedProviders: 40,
  recordsIdentifiedImports: 6,
  totalIdentified: 46,
  recordsAfterNormalization: 44,
  recordsBeforeDedup: 44,
  recordsAfterTechnicalMerger: 42,
  duplicateGroupsPendingReview: 1,
  recordsScreenedTitleAbstract: 3,
  recordsScreenedFullText: 2,
  studiesIncludedSynthesis: 1,
  manualSourceBreakdown: { google_scholar_pop: 6 },
  providerBreakdown: { crossref: 40 },
  sourceRecordsIdentified: 7,
  exactDuplicatesLinked: 2,
  repeatedSourceOccurrences: 1,
  mergedDuplicateRecords: 2,
  recoveredRecords: 1,
  canonicalPublications: 42,
};

describe('PRISMA source accounting', () => {
  it('renders persisted source-aware counts instead of only canonical totals', () => {
    render(<LivePrismaFlowChart metrics={metrics} />);
    const panel = screen.getByTestId('prisma-source-accounting');
    expect(panel).toHaveTextContent('Rekordy źródłowe: 7');
    expect(panel).toHaveTextContent('Duplikaty DOI: 2');
    expect(panel).toHaveTextContent('Powtórzenia: 1');
    expect(panel).toHaveTextContent('Scalone duplikaty: 2');
    expect(panel).toHaveTextContent('Odzyskane: 1');
    expect(panel).toHaveTextContent('Kanoniczne: 42');
  });
});
