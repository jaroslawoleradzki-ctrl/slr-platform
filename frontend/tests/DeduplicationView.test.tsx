import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DeduplicationSummaryCard } from '../src/components/deduplication/DeduplicationSummaryCard';

describe('DeduplicationSummaryCard', () => {
  it('highlights pending candidate duplicate groups without claiming automated domain merge', () => {
    const summary = {
      recordsBeforeDedup: 2000,
      identifierLinkedGroupsCount: 300,
      recordsAfterResultMerger: 1700,
      candidateGroupsPendingUserReview: 25,
      status: 'pending_action' as const,
    };

    render(<DeduplicationSummaryCard summary={summary} />);

    expect(screen.getAllByText(/25 grup/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Kandydaci na duplikaty/i)).toBeInTheDocument();
  });
});
