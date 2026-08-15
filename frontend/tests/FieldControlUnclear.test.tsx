import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FieldControl } from '../src/components/extraction/FieldControl';
import type { ExtractedValueStateDTO, ExtractionFieldDefinition } from '../src/services/api/extractionApi';

const base: ExtractedValueStateDTO = { field_key: 'field', status: 'unclear', origin: null };
const field = (
  data_type: 'text' | 'integer' | 'boolean' | 'multi_enum' | 'number_with_unit' = 'text',
  allowed_statuses?: ExtractedValueStateDTO['status'][],
) => ({ field_key: 'field', name: 'Field', data_type, allowed_statuses });
const originSelect = () => screen.getByText('Źródło:').parentElement!.querySelector('select')!;
const statusSelect = () => screen.getByText('Status:').parentElement!.querySelector('select')!;
afterEach(cleanup);
const renderField = (valueState: ExtractedValueStateDTO = base, definition: ExtractionFieldDefinition = field()) => {
  const onChange = vi.fn();
  render(<FieldControl fieldDef={definition} valueState={valueState} onChange={onChange} onOpenProvenance={vi.fn()} />);
  return onChange;
};

describe('FieldControl UNCLEAR', () => {
  it('keeps explicit-null and omitted values unassessed for origin purposes', () => {
    const change = renderField({ ...base, text_value: null, int_value: null, float_value: null, bool_value: null, json_value: null });
    expect(originSelect()).toBeDisabled(); expect(change).not.toHaveBeenCalled();
    cleanup();
    const omitted = renderField(base); expect(originSelect()).toBeDisabled(); expect(omitted).not.toHaveBeenCalled();
  });

  it.each([
    ['text', { ...base, text_value: 'tentative' }, field('text')],
    ['numeric', { ...base, int_value: 1 }, field('integer')],
    ['boolean', { ...base, bool_value: false }, field('boolean')],
    ['multi', { ...base, json_value: ['x'] }, field('multi_enum')],
  ])('enables origin for tentative %s value', (_kind: string, value: ExtractedValueStateDTO, definition: ExtractionFieldDefinition) => {
    renderField(value, definition); expect(originSelect()).not.toBeDisabled();
  });

  it('requires numeric evidence, not a unit alone, for number-with-unit', () => {
    renderField({ ...base, unit_value: 'kWh' }, field('number_with_unit')); expect(originSelect()).toBeDisabled(); cleanup();
    renderField({ ...base, float_value: 1, unit_value: 'kWh' }, field('number_with_unit')); expect(originSelect()).not.toBeDisabled();
  });

  it('treats an empty multi-value list as no value', () => {
    renderField({ ...base, json_value: [] }, field('multi_enum')); expect(originSelect()).toBeDisabled();
  });

  it('clears origin and source fields when a tentative value disappears, retaining the note', async () => {
    const onChange = renderField({ ...base, origin: 'reported', source_page: '1', source_section: 'Results', source_locator: 'T1', source_quote: 'q', reviewer_note: 'why' });
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ origin: null, source_page: null, source_section: null, source_locator: null, source_quote: null, reviewer_note: 'why' })));
    expect(originSelect()).toBeDisabled();
  });

  it('does not clean a valid reviewer-coded tentative state or loop', async () => {
    const onChange = renderField({ ...base, text_value: 'tentative', origin: 'reviewer_coded', reviewer_note: 'reason' });
    expect(originSelect()).not.toBeDisabled();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('limits selectable statuses to the template contract while retaining UNASSESSED', () => {
    renderField({ ...base, status: 'unassessed' }, field('text', ['present']));
    expect(Array.from(statusSelect().options).map((option) => option.value)).toEqual(['unassessed', 'present']);
    cleanup();
    renderField({ ...base, status: 'unassessed' }, field('text', ['present', 'not_reported', 'not_applicable', 'unclear']));
    expect(Array.from(statusSelect().options).map((option) => option.value)).toEqual([
      'unassessed', 'present', 'not_reported', 'not_applicable', 'unclear',
    ]);
  });

  it('maps an empty origin selection to null', () => {
    const onChange = renderField({ ...base, status: 'present', text_value: 'evidence', origin: 'reported' });
    fireEvent.change(originSelect(), { target: { value: '' } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ origin: null }));
  });

  it('does not open any provenance editor for an unassessed field', () => {
    renderField({ ...base, status: 'unassessed' });
    expect(screen.getByRole('button', { name: /Proweniencja/ })).toBeDisabled();
  });

  it('allows notes but not source provenance for missingness statuses', () => {
    const onOpenProvenance = vi.fn();
    render(
      <FieldControl
        fieldDef={field('text', ['present', 'not_reported'])}
        valueState={{ ...base, status: 'not_reported' }}
        onChange={vi.fn()}
        onOpenProvenance={onOpenProvenance}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Proweniencja/ }));
    expect(onOpenProvenance).toHaveBeenCalledWith(
      expect.anything(), expect.any(Function),
      { allowSourceProvenance: false, allowReviewerNote: true },
    );
  });

  it('keeps UNCLEAR without a tentative value note-only, then enables source provenance with evidence', () => {
    const onOpenProvenance = vi.fn();
    const { rerender } = render(
      <FieldControl
        fieldDef={field('text', ['present', 'unclear'])}
        valueState={base}
        onChange={vi.fn()}
        onOpenProvenance={onOpenProvenance}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Proweniencja/ }));
    expect(onOpenProvenance).toHaveBeenLastCalledWith(
      expect.anything(), expect.any(Function),
      { allowSourceProvenance: false, allowReviewerNote: true },
    );

    rerender(
      <FieldControl
        fieldDef={field('text', ['present', 'unclear'])}
        valueState={{ ...base, text_value: 'tentative' }}
        onChange={vi.fn()}
        onOpenProvenance={onOpenProvenance}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Proweniencja/ }));
    expect(onOpenProvenance).toHaveBeenLastCalledWith(
      expect.anything(), expect.any(Function),
      { allowSourceProvenance: true, allowReviewerNote: true },
    );
  });
});
