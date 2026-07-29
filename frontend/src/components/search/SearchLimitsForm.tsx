import React from 'react';
import { Filter } from 'lucide-react';
import { SearchFilters } from '../../types';
import { Card } from '../common/Card';

interface SearchLimitsFormProps {
  filters: SearchFilters;
  onFiltersChange?: (filters: SearchFilters) => void;
}

export const SearchLimitsForm: React.FC<SearchLimitsFormProps> = ({ filters, onFiltersChange }) => {
  const handleChange = (key: keyof SearchFilters, value: any) => {
    if (onFiltersChange) {
      onFiltersChange({ ...filters, [key]: value });
    }
  };

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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Years Range */}
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Zakres Lat Publikacji (Publication Years)
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="number"
              placeholder="Od (np. 2015)"
              value={filters.publicationYearFrom || ''}
              onChange={(e) => handleChange('publicationYearFrom', e.target.value ? parseInt(e.target.value) : null)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-strong)',
                fontSize: '0.85rem',
              }}
            />
            <span style={{ color: 'var(--text-muted)' }}>—</span>
            <input
              type="number"
              placeholder="Do (np. 2026)"
              value={filters.publicationYearTo || ''}
              onChange={(e) => handleChange('publicationYearTo', e.target.value ? parseInt(e.target.value) : null)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-strong)',
                fontSize: '0.85rem',
              }}
            />
          </div>
        </div>

        {/* Languages */}
        <div>
          <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Dozwolone Języki Publikacji (Languages)
          </label>
          <div style={{ display: 'flex', gap: '12px', paddingTop: '4px' }}>
            {['en', 'pl', 'de', 'fr', 'es'].map((lang) => {
              const checked = filters.languages.includes(lang);
              return (
                <label key={lang} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const updated = e.target.checked
                        ? [...filters.languages, lang]
                        : filters.languages.filter((l) => l !== lang);
                      handleChange('languages', updated);
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
          <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Typy Dokumentów (Publication Types)
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', paddingTop: '4px' }}>
            {[
              { id: 'article', label: 'Journal Article' },
              { id: 'review', label: 'Review' },
              { id: 'conference_paper', label: 'Conference Paper' },
              { id: 'book_chapter', label: 'Book Chapter' },
            ].map((type) => {
              const checked = filters.publicationTypes.includes(type.id);
              return (
                <label key={type.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const updated = e.target.checked
                        ? [...filters.publicationTypes, type.id]
                        : filters.publicationTypes.filter((t) => t !== type.id);
                      handleChange('publicationTypes', updated);
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
          <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Dostępność Pełnego Tekstu
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={filters.fullTextOnly}
              onChange={(e) => handleChange('fullTextOnly', e.target.checked)}
            />
            <span>Wymagaj bezpośredniej dostępności Open Access / PDF</span>
          </label>
        </div>
      </div>
    </Card>
  );
};
