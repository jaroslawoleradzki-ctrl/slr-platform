import { useCallback, useState } from 'react';

export const REVIEWER_IDENTITY_STORAGE_KEY = 'slr_screening_reviewer_id';

/** Compatibility wrapper over the established browser-only reviewer identifier. */
export function useReviewerIdentity() {
  const [reviewerId, setReviewerIdState] = useState(() => localStorage.getItem(REVIEWER_IDENTITY_STORAGE_KEY) || '');
  const setReviewerId = useCallback((value: string) => {
    const normalized = value.trim();
    if (normalized) localStorage.setItem(REVIEWER_IDENTITY_STORAGE_KEY, normalized);
    else localStorage.removeItem(REVIEWER_IDENTITY_STORAGE_KEY);
    setReviewerIdState(normalized);
  }, []);
  return { reviewerId, setReviewerId };
}
