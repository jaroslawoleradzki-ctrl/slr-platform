"""Domain models and value objects for the Data Extraction framework (Phase 9.1).

This module is completely domain-agnostic. It contains zero hardcoded domain or SLR topic logic.
"""

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+$")


class ExtractionDomainError(Exception):
    """Base exception for all data extraction domain errors."""


class InvalidTemplateError(ExtractionDomainError):
    """Raised when an extraction template or version is structurally invalid."""


class TemplateImmutableError(ExtractionDomainError):
    """Raised when attempting to mutate a published immutable template version."""


class InvalidValueError(ExtractionDomainError):
    """Raised when an extracted field value violates type or missingness rules."""


class InvalidRevisionError(ExtractionDomainError):
    """Raised when an extraction revision is structurally invalid."""


class FieldDataType(StrEnum):
    """Supported field data types for extraction template definitions."""

    TEXT = "text"
    LONG_TEXT = "long_text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    ENUM = "enum"
    MULTI_ENUM = "multi_enum"
    IDENTIFIER = "identifier"
    URL = "url"
    NUMBER_WITH_UNIT = "number_with_unit"
    REPEATING_GROUP = "repeating_group"


class ValueStatus(StrEnum):
    """Explicit status explaining why a value is present or absent."""

    PRESENT = "present"
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"
    UNCLEAR = "unclear"


class ValueOrigin(StrEnum):
    """Origin/attribution of an extracted value."""

    REPORTED = "reported"
    REVIEWER_CODED = "reviewer_coded"


class ExtractionCompletenessStatus(StrEnum):
    """Overall completeness status of an extraction record or revision."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"


class QuantitativeValue(BaseModel):
    """Value object representing a numeric value with associated unit and measurement type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numeric_value: float | None = None
    unit: str | None = None
    measurement_type: str | None = None


class ExtractionProvenance(BaseModel):
    """Value object capturing source location and notes for an extracted value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_page: str | None = None
    source_section: str | None = None
    source_locator: str | None = None
    source_quote: str | None = None
    reviewer_note: str | None = None

    @field_validator("source_quote")
    @classmethod
    def validate_source_quote(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise InvalidValueError("source_quote must not exceed 500 characters")
        return v


class ExtractedValueState(BaseModel):
    """Domain object representing an extracted field value assessment and provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value_id: UUID = Field(default_factory=uuid4)
    field_key: str
    status: ValueStatus
    origin: ValueOrigin

    text_value: str | None = None
    int_value: int | None = None
    float_value: float | None = None
    bool_value: bool | None = None
    unit_value: str | None = None
    json_value: list[str] | None = None

    source_page: str | None = None
    source_section: str | None = None
    source_locator: str | None = None
    source_quote: str | None = None
    reviewer_note: str | None = None

    @field_validator("field_key")
    @classmethod
    def validate_field_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidValueError("field_key must not be empty")
        return v.strip()

    @field_validator("source_quote")
    @classmethod
    def validate_source_quote(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise InvalidValueError("source_quote must not exceed 500 characters")
        return v

    @model_validator(mode="after")
    def validate_value_status_consistency(self) -> Self:
        has_typed_val = (
            self.text_value is not None
            or self.int_value is not None
            or self.float_value is not None
            or self.bool_value is not None
            or self.unit_value is not None
            or self.json_value is not None
        )

        if self.status == ValueStatus.PRESENT:
            if not has_typed_val:
                raise InvalidValueError(
                    f"Extracted value for field '{self.field_key}' with status PRESENT must have at least one typed value."
                )
        elif self.status in (ValueStatus.NOT_REPORTED, ValueStatus.NOT_APPLICABLE):
            if has_typed_val:
                raise InvalidValueError(
                    f"Extracted value for field '{self.field_key}' with status {self.status.value} must have all typed values set to None."
                )
        return self

    @property
    def provenance(self) -> ExtractionProvenance:
        return ExtractionProvenance(
            source_page=self.source_page,
            source_section=self.source_section,
            source_locator=self.source_locator,
            source_quote=self.source_quote,
            reviewer_note=self.reviewer_note,
        )


class ExtractedGroupItemState(BaseModel):
    """Domain object representing a 1:N repeating group item instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_item_id: UUID = Field(default_factory=uuid4)
    group_key: str
    item_index: int
    values: list[ExtractedValueState] = Field(default_factory=list)

    @field_validator("group_key")
    @classmethod
    def validate_group_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidValueError("group_key must not be empty")
        return v.strip()

    @field_validator("item_index")
    @classmethod
    def validate_item_index(cls, v: int) -> int:
        if v < 1:
            raise InvalidValueError("item_index must be >= 1")
        return v

    @model_validator(mode="after")
    def validate_unique_field_keys(self) -> Self:
        keys = set()
        for val in self.values:
            if val.field_key in keys:
                raise InvalidValueError(
                    f"Duplicate field_key '{val.field_key}' in group item index {self.item_index}"
                )
            keys.add(val.field_key)
        return self


class ExtractionFieldDefinition(BaseModel):
    """Specification of a field within an extraction template or repeating group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_key: str
    name: str
    data_type: FieldDataType
    description: str | None = None
    is_required: bool = False
    allowed_values: list[str] | None = None
    allow_custom_text: bool = False
    allowed_units: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    regex_pattern: str | None = None
    group_key: str | None = None

    @field_validator("field_key")
    @classmethod
    def validate_field_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidTemplateError("field_key must not be empty")
        return v.strip()

    @model_validator(mode="after")
    def validate_field_definition(self) -> Self:
        if self.data_type in (FieldDataType.ENUM, FieldDataType.MULTI_ENUM):
            if not self.allow_custom_text and not self.allowed_values:
                raise InvalidTemplateError(
                    f"Field '{self.field_key}' of type {self.data_type.value} requires allowed_values unless allow_custom_text is True."
                )
        if self.data_type == FieldDataType.REPEATING_GROUP:
            if not self.group_key:
                raise InvalidTemplateError(
                    f"Field '{self.field_key}' of type REPEATING_GROUP must specify group_key."
                )
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise InvalidTemplateError(
                    f"Field '{self.field_key}' min_value ({self.min_value}) cannot exceed max_value ({self.max_value})."
                )
        if self.min_length is not None and self.max_length is not None:
            if self.min_length > self.max_length:
                raise InvalidTemplateError(
                    f"Field '{self.field_key}' min_length ({self.min_length}) cannot exceed max_length ({self.max_length})."
                )
        return self

    def validate_value(self, val_state: ExtractedValueState) -> list[str]:
        """Validate an ExtractedValueState against this field definition."""
        errors: list[str] = []
        if val_state.field_key != self.field_key:
            errors.append(
                f"Field key mismatch: expected '{self.field_key}', got '{val_state.field_key}'"
            )
            return errors

        if val_state.status in (ValueStatus.NOT_REPORTED, ValueStatus.NOT_APPLICABLE):
            return errors

        if val_state.status in (ValueStatus.PRESENT, ValueStatus.UNCLEAR):
            dt = self.data_type
            if dt in (
                FieldDataType.TEXT,
                FieldDataType.LONG_TEXT,
                FieldDataType.IDENTIFIER,
                FieldDataType.URL,
            ):
                if val_state.text_value is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires text_value.")
                elif val_state.text_value is not None:
                    txt = val_state.text_value
                    if self.min_length is not None and len(txt) < self.min_length:
                        errors.append(
                            f"Field '{self.field_key}' text length {len(txt)} is below min_length {self.min_length}."
                        )
                    if self.max_length is not None and len(txt) > self.max_length:
                        errors.append(
                            f"Field '{self.field_key}' text length {len(txt)} exceeds max_length {self.max_length}."
                        )
                    if self.regex_pattern and not re.search(self.regex_pattern, txt):
                        errors.append(
                            f"Field '{self.field_key}' value does not match pattern '{self.regex_pattern}'."
                        )
            elif dt == FieldDataType.INTEGER:
                if val_state.int_value is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires int_value.")
                elif val_state.int_value is not None:
                    iv = val_state.int_value
                    if self.min_value is not None and iv < self.min_value:
                        errors.append(
                            f"Field '{self.field_key}' value {iv} is below min_value {self.min_value}."
                        )
                    if self.max_value is not None and iv > self.max_value:
                        errors.append(
                            f"Field '{self.field_key}' value {iv} exceeds max_value {self.max_value}."
                        )
            elif dt == FieldDataType.DECIMAL:
                num_val = (
                    val_state.float_value
                    if val_state.float_value is not None
                    else (float(val_state.int_value) if val_state.int_value is not None else None)
                )
                if num_val is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires float_value or int_value.")
                elif num_val is not None:
                    if self.min_value is not None and num_val < self.min_value:
                        errors.append(
                            f"Field '{self.field_key}' value {num_val} is below min_value {self.min_value}."
                        )
                    if self.max_value is not None and num_val > self.max_value:
                        errors.append(
                            f"Field '{self.field_key}' value {num_val} exceeds max_value {self.max_value}."
                        )
            elif dt == FieldDataType.BOOLEAN:
                if val_state.bool_value is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires bool_value.")
            elif dt == FieldDataType.DATE:
                if val_state.text_value is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires text_value (ISO date).")
            elif dt == FieldDataType.ENUM:
                if val_state.text_value is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires text_value.")
                elif (
                    val_state.text_value is not None
                    and self.allowed_values
                    and not self.allow_custom_text
                ):
                    if val_state.text_value not in self.allowed_values:
                        errors.append(
                            f"Field '{self.field_key}' value '{val_state.text_value}' is not in allowed_values."
                        )
            elif dt == FieldDataType.MULTI_ENUM:
                if val_state.json_value is None and val_state.status == ValueStatus.PRESENT:
                    errors.append(f"Field '{self.field_key}' requires json_value list.")
                elif (
                    val_state.json_value is not None
                    and self.allowed_values
                    and not self.allow_custom_text
                ):
                    for item in val_state.json_value:
                        if item not in self.allowed_values:
                            errors.append(
                                f"Field '{self.field_key}' item '{item}' is not in allowed_values."
                            )
            elif dt == FieldDataType.NUMBER_WITH_UNIT:
                num_val = (
                    val_state.float_value
                    if val_state.float_value is not None
                    else (float(val_state.int_value) if val_state.int_value is not None else None)
                )
                if val_state.status == ValueStatus.PRESENT:
                    if num_val is None:
                        errors.append(f"Field '{self.field_key}' requires float_value/int_value.")
                    if val_state.unit_value is None:
                        errors.append(f"Field '{self.field_key}' requires unit_value.")
                if val_state.unit_value is not None and self.allowed_units:
                    if val_state.unit_value not in self.allowed_units:
                        errors.append(
                            f"Field '{self.field_key}' unit '{val_state.unit_value}' is not in allowed_units."
                        )
                if num_val is not None:
                    if self.min_value is not None and num_val < self.min_value:
                        errors.append(
                            f"Field '{self.field_key}' value {num_val} is below min_value {self.min_value}."
                        )
                    if self.max_value is not None and num_val > self.max_value:
                        errors.append(
                            f"Field '{self.field_key}' value {num_val} exceeds max_value {self.max_value}."
                        )

        return errors


class ExtractionRepeatingGroupDefinition(BaseModel):
    """Specification of a 1:N repeating group within an extraction template version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_key: str
    name: str
    description: str | None = None
    min_items: int = 0
    max_items: int | None = None
    field_definitions: list[ExtractionFieldDefinition] = Field(default_factory=list)

    @field_validator("group_key")
    @classmethod
    def validate_group_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidTemplateError("group_key must not be empty")
        return v.strip()

    @field_validator("min_items")
    @classmethod
    def validate_min_items(cls, v: int) -> int:
        if v < 0:
            raise InvalidTemplateError("min_items must be >= 0")
        return v

    @model_validator(mode="after")
    def validate_group(self) -> Self:
        if self.max_items is not None and self.max_items < self.min_items:
            raise InvalidTemplateError(
                f"Group '{self.group_key}' max_items ({self.max_items}) cannot be less than min_items ({self.min_items})."
            )
        keys = set()
        for fdef in self.field_definitions:
            if fdef.field_key in keys:
                raise InvalidTemplateError(
                    f"Duplicate field_key '{fdef.field_key}' in group '{self.group_key}'"
                )
            keys.add(fdef.field_key)
        return self


class ExtractionRevision(BaseModel):
    """Append-only point-in-time revision snapshot of extraction assessments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    revision_id: UUID = Field(default_factory=uuid4)
    record_id: UUID
    project_id: str
    publication_id: UUID
    revision_index: int
    reviewer_id: str
    completeness_status: ExtractionCompletenessStatus
    publication_values: list[ExtractedValueState] = Field(default_factory=list)
    group_items: list[ExtractedGroupItemState] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("reviewer_id")
    @classmethod
    def validate_reviewer_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidRevisionError("reviewer_id must be a non-empty string")
        return v.strip()

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidRevisionError("project_id must be a non-empty string")
        return v.strip()

    @field_validator("revision_index")
    @classmethod
    def validate_revision_index(cls, v: int) -> int:
        if v < 1:
            raise InvalidRevisionError("revision_index must be >= 1")
        return v

    @field_validator("completeness_status")
    @classmethod
    def validate_revision_completeness_status(
        cls, v: ExtractionCompletenessStatus
    ) -> ExtractionCompletenessStatus:
        if v is ExtractionCompletenessStatus.NOT_STARTED:
            raise InvalidRevisionError(
                "ExtractionRevision completeness_status cannot be not_started; "
                "not_started is reserved for records without revisions."
            )
        return v

    @model_validator(mode="after")
    def validate_publication_values_unique_keys(self) -> Self:
        seen = set()
        for v in self.publication_values:
            if v.field_key in seen:
                raise InvalidRevisionError(
                    f"Duplicate publication field_key '{v.field_key}' in revision"
                )
            seen.add(v.field_key)
        return self


class ExtractionTemplateVersion(BaseModel):
    """Immutable structural snapshot of an extraction template version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    version: str
    name: str
    description: str | None = None
    is_published: bool = False
    is_active: bool = True
    publication_fields: list[ExtractionFieldDefinition] = Field(default_factory=list)
    repeating_groups: list[ExtractionRepeatingGroupDefinition] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        if not SEMVER_REGEX.match(v):
            raise InvalidTemplateError(f"Version string '{v}' must be a valid semver (X.Y.Z).")
        return v

    @model_validator(mode="after")
    def validate_template_version_structure(self) -> Self:
        pub_keys = set()
        for fdef in self.publication_fields:
            if fdef.field_key in pub_keys:
                raise InvalidTemplateError(
                    f"Duplicate publication field_key '{fdef.field_key}' in template '{self.template_id}' v{self.version}"
                )
            pub_keys.add(fdef.field_key)

        group_keys = set()
        for gdef in self.repeating_groups:
            if gdef.group_key in group_keys:
                raise InvalidTemplateError(
                    f"Duplicate group_key '{gdef.group_key}' in template '{self.template_id}' v{self.version}"
                )
            group_keys.add(gdef.group_key)
        return self

    def publish(self) -> "ExtractionTemplateVersion":
        """Returns a copy of this version marked as published (immutable)."""
        return self.model_copy(update={"is_published": True})

    def validate_revision(self, revision: ExtractionRevision) -> list[str]:
        """Validate an ExtractionRevision against this template version."""
        errors: list[str] = []

        pub_val_map: dict[str, ExtractedValueState] = {
            v.field_key: v for v in revision.publication_values
        }

        for fdef in self.publication_fields:
            val_state = pub_val_map.get(fdef.field_key)
            if val_state is None:
                if fdef.is_required:
                    errors.append(f"Required publication field '{fdef.field_key}' is missing.")
            else:
                field_errs = fdef.validate_value(val_state)
                errors.extend(field_errs)

        group_items_by_key: dict[str, list[ExtractedGroupItemState]] = {}
        for item in revision.group_items:
            group_items_by_key.setdefault(item.group_key, []).append(item)

        for gdef in self.repeating_groups:
            items = group_items_by_key.get(gdef.group_key, [])
            count = len(items)

            if count < gdef.min_items:
                errors.append(
                    f"Repeating group '{gdef.group_key}' requires at least {gdef.min_items} item(s), found {count}."
                )
            if gdef.max_items is not None and count > gdef.max_items:
                errors.append(
                    f"Repeating group '{gdef.group_key}' allows at most {gdef.max_items} item(s), found {count}."
                )

            indexes_seen = set()
            for item in items:
                if item.item_index in indexes_seen:
                    errors.append(
                        f"Duplicate item_index {item.item_index} in group '{gdef.group_key}'."
                    )
                indexes_seen.add(item.item_index)

                item_val_map: dict[str, ExtractedValueState] = {
                    v.field_key: v for v in item.values
                }

                for child_fdef in gdef.field_definitions:
                    child_val = item_val_map.get(child_fdef.field_key)
                    if child_val is None:
                        if child_fdef.is_required:
                            errors.append(
                                f"Required field '{child_fdef.field_key}' missing in group '{gdef.group_key}' item index {item.item_index}."
                            )
                    else:
                        child_errs = child_fdef.validate_value(child_val)
                        errors.extend(child_errs)

        return errors

    def compute_completeness(self, revision: ExtractionRevision) -> ExtractionCompletenessStatus:
        """Compute completeness status for a revision against this template version."""
        errors = self.validate_revision(revision)
        if not errors:
            return ExtractionCompletenessStatus.COMPLETE
        return ExtractionCompletenessStatus.IN_PROGRESS


class ExtractionTemplate(BaseModel):
    """Extraction template header holding metadata and versions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    name: str
    description: str | None = None
    versions: list[ExtractionTemplateVersion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidTemplateError("template_id must not be empty")
        return v.strip()

    def get_version(self, version_str: str) -> ExtractionTemplateVersion:
        for ver in self.versions:
            if ver.version == version_str:
                return ver
        raise InvalidTemplateError(
            f"Version '{version_str}' not found in template '{self.template_id}'"
        )

    def add_version(self, version: ExtractionTemplateVersion) -> "ExtractionTemplate":
        if version.template_id != self.template_id:
            raise InvalidTemplateError(
                f"Version template_id '{version.template_id}' does not match '{self.template_id}'"
            )
        for existing in self.versions:
            if existing.version == version.version:
                raise InvalidTemplateError(
                    f"Version '{version.version}' already exists in template '{self.template_id}'"
                )
        new_versions = list(self.versions) + [version]
        return self.model_copy(update={"versions": new_versions})


class ExtractionRecord(BaseModel):
    """Header record representing the current extraction state for a publication in a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: UUID = Field(default_factory=uuid4)
    project_id: str
    publication_id: UUID
    template_id: str
    template_version: str
    current_status: ExtractionCompletenessStatus = ExtractionCompletenessStatus.NOT_STARTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidRevisionError("project_id must be a non-empty string")
        return v.strip()
