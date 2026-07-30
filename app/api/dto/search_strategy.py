from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.search import (
    BooleanOperator,
    SearchConceptGroup,
    SearchConstraints,
    SearchQuery,
)


class ConceptGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    terms: list[str] = Field(min_length=1)

    @field_validator("id", "name")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("terms")
    @classmethod
    def require_non_blank_terms(cls, terms: list[str]) -> list[str]:
        stripped = [term.strip() for term in terms]
        if any(not term for term in stripped):
            raise ValueError("terms must not contain blank values")
        return stripped


class SearchStrategyExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_year_from: int = Field(ge=1000, le=9999)
    publication_year_to: int = Field(ge=1000, le=9999)
    providers: list[Literal["openalex", "crossref"]] = Field(min_length=1)
    concept_groups: list[ConceptGroupRequest] = Field(min_length=1)
    languages: list[str] = Field(default_factory=list)
    publication_types: list[
        Literal["article", "review", "conference_paper", "book_chapter"]
    ] = Field(default_factory=list)
    open_access: bool = False
    cursor: str | None = None

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, languages: list[str]) -> list[str]:
        normalized = [language.strip().lower() for language in languages]
        if any(not language for language in normalized):
            raise ValueError("languages must not contain blank values")
        if len(set(normalized)) != len(normalized):
            raise ValueError("languages must be unique")
        return normalized

    @field_validator("cursor")
    @classmethod
    def normalize_cursor(cls, cursor: str | None) -> str | None:
        if cursor is None:
            return None
        normalized = cursor.strip()
        if not normalized:
            raise ValueError("cursor must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_year_range(self) -> "SearchStrategyExecutionRequest":
        if self.publication_year_from > self.publication_year_to:
            raise ValueError(
                "publication_year_from must not be later than publication_year_to"
            )
        return self


class SearchStrategyPutRequest(BaseModel):
    """Complete write contract for one project's persisted search strategy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: UUID | None = None
    name: str = Field(min_length=1)
    description: str | None = None
    research_questions: list[str] = Field(min_length=1)
    concept_groups: list[SearchConceptGroup] = Field(min_length=1)
    group_operator: Literal[BooleanOperator.AND, BooleanOperator.OR] = (
        BooleanOperator.AND
    )
    constraints: SearchConstraints
    providers: list[
        Literal["openalex", "crossref", "semantic_scholar"]
    ] = Field(min_length=1)
    queries: list[SearchQuery] = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    created_at: datetime | None = None

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("research_questions")
    @classmethod
    def normalize_research_questions(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values]
        if any(not value for value in stripped):
            raise ValueError("research_questions must not contain blank values")
        if len(set(stripped)) != len(stripped):
            raise ValueError("research_questions must be unique")
        return stripped

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("created_at must be timezone-aware")
        return value

    def creation_time(self) -> datetime:
        return self.created_at or datetime.now(timezone.utc)


class SearchStrategyExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    status: Literal["validated"] = "validated"
    rendered_query: str
    providers: list[str]
    publication_year_from: int
    publication_year_to: int
    executed_at: datetime
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    next_cursor: str | None = None
    has_more: bool
    results: list["SearchResultRecordResponse"]
    provider_errors: list["SearchProviderErrorResponse"] = Field(default_factory=list)


class SearchResultRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    authors: list[str]
    year: int
    provider: Literal["openalex", "crossref"]
    source_id: str
    doi: str | None = None


class SearchProviderErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["openalex", "crossref"]
    message: str


class SearchResultsImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    records: list[SearchResultRecordResponse]


class SearchResultsImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    imported_count: int
    skipped_count: int
    total_requested: int
    working_collection_count: int


class BibliographicImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    import_id: UUID
    records_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    status: Literal["success", "warning"]


class BibliographicImportHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    import_id: UUID
    project_id: str
    filename: str
    format: Literal["RIS", "BibTeX"]
    records_count: int = Field(ge=0)
    status: Literal["success", "warning"]
    created_at: datetime
    warnings: list[str] = Field(default_factory=list)


SearchStrategyExecutionResponse.model_rebuild()
