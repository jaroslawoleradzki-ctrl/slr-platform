import React from 'react';
import {
  ExtractionTemplateVersion,
  ExtractedValueStateDTO,
  ExtractedGroupItemStateDTO,
  ValueStatus,
} from '../../api/extractionApi';
import { FieldControl } from './FieldControl';
import { RelationshipManager } from './RelationshipManager';

interface ExtractionFormViewProps {
  templateVersion: ExtractionTemplateVersion;
  publicationValues: ExtractedValueStateDTO[];
  groupItems: ExtractedGroupItemStateDTO[];
  onChangePublicationValues: (updatedValues: ExtractedValueStateDTO[]) => void;
  onChangeGroupItems: (updatedGroups: ExtractedGroupItemStateDTO[]) => void;
  onOpenProvenance: (
    fieldKey: string,
    fieldName: string,
    valueState: ExtractedValueStateDTO,
    onSave: (p: Partial<ExtractedValueStateDTO>) => void,
    options: { allowSourceProvenance: boolean; allowReviewerNote: boolean },
  ) => void;
  validationErrors?: Record<string, string>;
}

export const ExtractionFormView: React.FC<ExtractionFormViewProps> = ({
  templateVersion,
  publicationValues,
  groupItems,
  onChangePublicationValues,
  onChangeGroupItems,
  onOpenProvenance,
  validationErrors = {},
}) => {
  const handlePublicationFieldChange = (updatedVal: ExtractedValueStateDTO) => {
    const updated = publicationValues.map((val) =>
      val.field_key === updatedVal.field_key ? updatedVal : val
    );
    if (!publicationValues.some((val) => val.field_key === updatedVal.field_key)) {
      updated.push(updatedVal);
    }
    onChangePublicationValues(updated);
  };

  const handleGroupItemsChange = (groupKey: string, updatedGroupItems: ExtractedGroupItemStateDTO[]) => {
    const remainingOtherGroups = groupItems.filter((g) => g.group_key !== groupKey);
    onChangeGroupItems([...remainingOtherGroups, ...updatedGroupItems]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Publication-Level Fields Section */}
      <div
        style={{
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          backgroundColor: 'var(--bg-surface)',
          padding: '20px',
        }}
      >
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: 0, marginBottom: '16px' }}>
          Pola na poziomie publikacji
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {templateVersion.publication_fields.map((fieldDef) => {
            const valueState =
              publicationValues.find((val) => val.field_key === fieldDef.field_key) || {
                field_key: fieldDef.field_key,
                status: 'unassessed' as ValueStatus,
                origin: null,
              };
            const errorMsg = validationErrors[fieldDef.field_key];

            return (
              <FieldControl
                key={fieldDef.field_key}
                fieldDef={fieldDef}
                valueState={valueState}
                onChange={handlePublicationFieldChange}
                onOpenProvenance={(val, onSave, options) => onOpenProvenance(fieldDef.field_key, fieldDef.name, val, onSave, options)}
                errorMessage={errorMsg}
              />
            );
          })}
        </div>
      </div>

      {/* Repeating Group Sections */}
      {templateVersion.repeating_groups.length > 0 && (
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
            Grupy powtarzalne (1:N)
          </h3>

          {templateVersion.repeating_groups.map((groupDef) => {
            const currentGroupItems = groupItems.filter((g) => g.group_key === groupDef.group_key);
            return (
              <RelationshipManager
                key={groupDef.group_key}
                groupDef={groupDef}
                groupItems={currentGroupItems}
                onChange={(updated) => handleGroupItemsChange(groupDef.group_key, updated)}
                onOpenProvenance={onOpenProvenance}
                validationErrors={validationErrors}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};
