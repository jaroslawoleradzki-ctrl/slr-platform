import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProvenanceDrawer } from '../src/components/extraction/ProvenanceDrawer';

const valueState = {
  field_key: 'field',
  status: 'not_reported' as const,
  origin: null,
  source_page: 'old page',
  reviewer_note: 'existing note',
};

describe('ProvenanceDrawer status constraints', () => {
  it('allows a reviewer note but clears and disables source provenance when source provenance is forbidden', () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDrawer
        isOpen
        fieldKey="field"
        fieldName="Field"
        valueState={valueState}
        allowSourceProvenance={false}
        allowReviewerNote
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/Strona w publikacji/)).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Notatka recenzenta/), { target: { value: 'reviewed absence' } });
    fireEvent.click(screen.getByRole('button', { name: /Zapisz proweniencję/ }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      source_page: null,
      source_section: null,
      source_locator: null,
      source_quote: null,
      reviewer_note: 'reviewed absence',
    }));
  });

  it('keeps source provenance available for a reported present value', () => {
    render(
      <ProvenanceDrawer
        isOpen
        fieldKey="field"
        fieldName="Field"
        valueState={{ ...valueState, status: 'present', origin: 'reported' }}
        allowSourceProvenance
        allowReviewerNote
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByLabelText(/Strona w publikacji/)).not.toBeDisabled();
  });
});
