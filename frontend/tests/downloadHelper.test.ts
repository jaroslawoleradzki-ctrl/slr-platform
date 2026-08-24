import { describe, it, expect, vi, beforeEach } from 'vitest';
import { triggerBlobDownload } from '../src/utils/downloadHelper';

describe('downloadHelper — triggerBlobDownload', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
    Object.assign(URL, {
      createObjectURL: vi.fn().mockReturnValue('blob:test-download-url'),
      revokeObjectURL: vi.fn(),
    });
  });

  it('creates an anchor, triggers click with proper filename, and cleans up', () => {
    const appendChildSpy = vi.spyOn(document.body, 'appendChild');

    const clickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      const el = originalCreateElement(tagName);
      if (tagName === 'a') {
        el.click = clickSpy;
      }
      return el;
    });

    const blob = new Blob(['sample-data'], { type: 'text/plain' });
    triggerBlobDownload(blob, 'project_export.bib');

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(appendChildSpy).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();

    // Fast-forward setTimeout(..., 0) for URL.revokeObjectURL
    vi.runAllTimers();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-download-url');
  });
});
