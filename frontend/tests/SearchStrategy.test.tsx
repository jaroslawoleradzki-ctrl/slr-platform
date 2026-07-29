import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConceptGroupQueryBuilder } from '../src/components/search/ConceptGroupQueryBuilder';

describe('ConceptGroupQueryBuilder', () => {
  it('renders concept groups and generated boolean query string', () => {
    const mockGroups = [
      { id: 'g1', name: 'Lean Terms', terms: ['Kaizen', 'Toyota Production System'] },
      { id: 'g2', name: 'Energy Terms', terms: ['Energy Efficiency'] },
    ];

    render(<ConceptGroupQueryBuilder initialGroups={mockGroups} />);

    expect(screen.getByText(/Lean Terms/i)).toBeInTheDocument();
    expect(screen.getAllByText(/"Kaizen"/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/"Energy Efficiency"/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Wyrenderowane Zapytanie Boolean/i)).toBeInTheDocument();
  });
});
