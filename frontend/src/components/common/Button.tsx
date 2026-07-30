import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  isLoading?: boolean;
  loadingText?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  icon,
  isLoading = false,
  loadingText,
  disabled,
  children,
  style,
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'secondary':
        return {
          backgroundColor: 'var(--bg-surface-elevated)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-strong)',
        };
      case 'outline':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-strong)',
        };
      case 'danger':
        return {
          backgroundColor: 'var(--status-error-bg)',
          color: 'var(--status-error-text)',
          border: '1px solid var(--status-error-border)',
        };
      case 'primary':
      default:
        return {
          backgroundColor: 'var(--accent-primary)',
          color: '#ffffff',
          border: '1px solid transparent',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'sm':
        return {
          padding: '6px 12px',
          fontSize: '0.8rem',
        };
      case 'lg':
        return {
          padding: '12px 24px',
          fontSize: '1rem',
        };
      case 'md':
      default:
        return {
          padding: '10px 18px',
          fontSize: '0.875rem',
        };
    }
  };

  const isButtonDisabled = disabled || isLoading;

  return (
    <>
      <button
        disabled={isButtonDisabled}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          borderRadius: 'var(--radius-md)',
          fontWeight: 600,
          whiteSpace: 'nowrap',
          cursor: isButtonDisabled ? 'not-allowed' : 'pointer',
          opacity: isButtonDisabled ? 0.7 : 1,
          boxShadow: variant === 'primary' ? 'var(--shadow-sm)' : 'none',
          transition: 'all 0.15s ease',
          ...getVariantStyles(),
          ...getSizeStyles(),
          ...style,
        }}
        {...props}
      >
        {isLoading ? (
          <>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                animation: 'spin 1s linear infinite',
              }}
            >
              {icon || <Loader2 size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />}
            </span>
            {loadingText !== undefined ? loadingText : children}
          </>
        ) : (
          <>
            {icon && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {icon}
              </span>
            )}
            {children}
          </>
        )}
      </button>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
};
