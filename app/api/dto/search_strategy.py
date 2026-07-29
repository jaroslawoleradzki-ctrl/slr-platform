from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    @model_validator(mode="after")
    def validate_year_range(self) -> "SearchStrategyExecutionRequest":
        if self.publication_year_from > self.publication_year_to:
            raise ValueError(
                "publication_year_from must not be later than publication_year_to"
            )
        return self


class SearchStrategyExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    status: Literal["validated"] = "validated"
    rendered_query: str
    providers: list[str]
    publication_year_from: int
    publication_year_to: int
    executed_at: datetime
    result_count: int
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


SearchStrategyExecutionResponse.model_rebuild()
