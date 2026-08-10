import React from 'react';
import { Card } from '../common/Card';
import { TitleAbstractRecord } from '../../services/api/screeningApi';

export const ScreeningPublicationCard: React.FC<{ record: TitleAbstractRecord }> = ({ record }) => (
  <Card title={record.title} subtitle={record.authors.length ? record.authors.join(', ') : 'Brak informacji o autorach'}>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
      {record.publication_year && <span>{record.publication_year}</span>}
      {record.venue && <span>{record.venue.name}</span>}
      {record.doi && <span>DOI: {record.doi}</span>}
      {record.language && <span>Język: {record.language}</span>}
      {record.open_access !== null && <span>{record.open_access ? 'Open access' : 'Brak open access'}</span>}
      {record.document_type && <span>{record.document_type}</span>}
    </div>
    {record.identifiers.filter((identifier) => identifier.type !== 'doi').length > 0 && (
      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Identyfikatory: {record.identifiers.filter((identifier) => identifier.type !== 'doi').map((identifier) => `${identifier.type}: ${identifier.value}`).join(' · ')}
      </p>
    )}
    {record.keywords.length > 0 && <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Keywords: {record.keywords.join(', ')}</p>}
    {record.urls.length > 0 && <p style={{ fontSize: '0.8rem' }}><a href={record.urls[0]} target="_blank" rel="noreferrer">Open publication link</a></p>}
    <section aria-label="Abstract" style={{ marginTop: '18px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
      <h3 style={{ fontSize: '1rem', margin: '0 0 8px' }}>Abstract</h3>
      <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, color: 'var(--text-primary)', margin: 0 }}>
        {record.abstract || 'Brak abstraktu w zapisanych metadanych publikacji.'}
      </p>
    </section>
  </Card>
);
