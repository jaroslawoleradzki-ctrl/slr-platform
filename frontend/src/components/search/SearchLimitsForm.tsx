import React from 'react';
import { Filter } from 'lucide-react';
import { SearchStrategyConstraints } from '../../types';
import { Card } from '../common/Card';

interface SearchLimitsFormProps {
  constraints: SearchStrategyConstraints;
  onChange: (constraints: SearchStrategyConstraints) => void;
  disabled?: boolean;
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  borderRadius: 'var(--radius-md)',
  backgroundColor: 'var(--bg-primary)',
  border: '1px solid var(--border-strong)',
  fontSize: '0.85rem',
  color: 'var(--text-primary)',
};

export const SearchLimitsForm: React.FC<SearchLimitsFormProps> = ({
  constraints,
  onChange,
  disabled = false,
}) => {
  const update = <K extends keyof SearchStrategyConstraints>(
    key: K,
    value: SearchStrategyConstraints[K],
  ) => {
    onChange({ ...constraints, [key]: value });
  };

  const fullTextChecked = Boolean(constraints.additional_limits?.open_access);

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={18} style={{ color: 'var(--accent-primary)' }} />
          <span>Ograniczenia i Filtry Wyszukiwania (Search Scope & Limits)</span>
        </div>
      }
      subtitle="Kryteria kwalifikujące wpisy na poziomie pobierania metadanych"
    >
      <fieldset disabled={disabled} style={{ border: 0, padding: 0, margin: 0 }}>
        <div
          data-testid="search-limits-grid"
          style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}
        >
          {/* Years Range */}
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              Zakres Lat Publikacji (Publication Years)
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="number"
                placeholder="Od (np. 2015)"
                value={constraints.publication_year_from ?? ''}
                aria-label="Rok początkowy"
                onChange={(e) =>
                  update(
                    'publication_year_from',
                    e.target.value ? parseInt(e.target.value, 10) : null,
                  )
                }
                style={inputStyle}
              />
              <span style={{ color: 'var(--text-muted)' }}>—</span>
              <input
                type="number"
                placeholder="Do (np. 2026)"
                value={constraints.publication_year_to ?? ''}
                aria-label="Rok końcowy"
                onChange={(e) =>
                  update(
                    'publication_year_to',
                    e.target.value ? parseInt(e.target.value, 10) : null,
                  )
                }
                style={inputStyle}
              />
            </div>
          </div>

          {/* Languages */}
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              Dozwolone Języki Publikacji (Languages)
            </label>
            <input
              type="text"
              aria-label="Języki"
              placeholder="np. en, pl, de"
              value={constraints.languages.join(', ')}
              onChange={(e) =>
                update(
                  'languages',
                  e.target.value
                    .split(',')
                    .map((item) => item.trim())
                    .filter(Boolean),
                )
              }
              style={{ ...inputStyle, marginBottom: 8 }}
            />
            <div style={{ display: 'flex', gap: '12px', paddingTop: '4px' }}>
              {['en', 'pl', 'de', 'fr', 'es'].map((lang) => {
                const checked = constraints.languages.includes(lang);
                return (
                  <label
                    key={lang}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => {
                        const updated = e.target.checked
                          ? [...constraints.languages, lang]
                          : constraints.languages.filter((l) => l !== lang);
                        update('languages', updated);
                      }}
                    />
                    <span style={{ textTransform: 'uppercase' }}>{lang}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Publication Types */}
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              Typy Dokumentów (Publication Types)
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', paddingTop: '4px' }}>
              {[
                { id: 'article', label: 'Journal Article' },
                { id: 'review', label: 'Review' },
                { id: 'conference_paper', label: 'Conference Paper' },
                { id: 'book_chapter', label: 'Book Chapter' },
              ].map((type) => {
                const checked = constraints.publication_types.includes(type.id);
                return (
                  <label
                    key={type.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => {
                        const updated = e.target.checked
                          ? [...constraints.publication_types, type.id]
                          : constraints.publication_types.filter((t) => t !== type.id);
                        update('publication_types', updated);
                      }}
                    />
                    <span>{type.label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Full Text Only */}
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}
            >
              Dostępność Pełnego Tekstu
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                paddingTop: '6px',
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                aria-label="Tylko z pełnym tekstem"
                checked={fullTextChecked}
                onChange={(e) => {
                  const currentLimits = { ...(constraints.additional_limits || {}) };
                  if (e.target.checked) {
                    currentLimits.open_access = true;
                  } else {
                    delete currentLimits.open_access;
                  }
                  onChange({ ...constraints, additional_limits: currentLimits });
                }}
              />
              <span>Wymagaj bezpośredniej dostępności Open Access / PDF</span>
            </label>
          </div>
        </div>
      </fieldset>
    </Card>
  );
};
