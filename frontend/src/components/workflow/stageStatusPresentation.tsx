import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Clock,
} from 'lucide-react';
import { WorkflowStageState } from '../../types';

export interface StageStatusPresentation {
  icon: React.ReactNode;
  color: string;
  backgroundColor?: string;
  borderColor?: string;
  /** Short human-readable state name for tooltips and aria labels */
  label: string;
}

const presentation = (
  icon: React.ReactNode,
  color: string,
  label: string,
  backgroundColor?: string,
  borderColor?: string
): StageStatusPresentation => ({ icon, color, label, backgroundColor, borderColor });

/**
 * Shared visual model for workflow stage states.
 * Every state has a distinct glyph so the meaning never relies on colour alone.
 */
export const getStageStatusPresentation = (
  state: WorkflowStageState,
  size = 14
): StageStatusPresentation => {
  switch (state) {
    case 'completed':
      return presentation(
        <CheckCircle2 size={size} aria-hidden="true" />,
        'var(--status-success-text)',
        'Zakończony'
      );
    case 'in_progress':
      return presentation(
        <CircleDot size={size} aria-hidden="true" />,
        'var(--status-info-text)',
        'W trakcie'
      );
    case 'pending_action':
      return presentation(
        <AlertCircle size={size} aria-hidden="true" />,
        'var(--status-warning-text)',
        'Wymaga działania',
        'var(--status-warning-bg)',
        'var(--status-warning-border)'
      );
    case 'warning':
      return presentation(
        <AlertTriangle size={size} aria-hidden="true" />,
        'var(--status-warning-text)',
        'Ostrzeżenia',
        'var(--status-warning-bg)',
        'var(--status-warning-border)'
      );
    case 'error':
      return presentation(
        <AlertCircle size={size} aria-hidden="true" />,
        'var(--status-error-text)',
        'Błąd'
      );
    case 'not_available':
      return presentation(
        <Clock size={size} style={{ opacity: 0.5 }} aria-hidden="true" />,
        'var(--text-muted)',
        'Niedostępny'
      );
    case 'not_started':
    default:
      return presentation(<Clock size={size} aria-hidden="true" />, 'var(--text-muted)', 'Oczekuje');
  }
};

/** Tooltip text combining stage identity, detailed status label and state name. */
export const getStageStatusTitle = (
  stageNumber: number,
  fullLabel: string,
  detailLabel: string | null | undefined,
  presentation: StageStatusPresentation
): string => {
  const detail = detailLabel ? ` — ${detailLabel}` : '';
  return `${stageNumber}. ${fullLabel}${detail} (${presentation.label})`;
};
