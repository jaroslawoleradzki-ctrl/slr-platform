import React from 'react';

/** Shared, token-based controls for the dark scientific theme. */
export const screeningControlStyle: React.CSSProperties = {
  width: '100%',
  backgroundColor: 'var(--bg-primary)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-strong)',
  borderRadius: 'var(--radius-md)',
  padding: '10px 12px',
  fontFamily: 'inherit',
  fontSize: '0.9rem',
};

export const screeningLabelStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  color: 'var(--text-secondary)',
  fontSize: '0.85rem',
  fontWeight: 600,
};
