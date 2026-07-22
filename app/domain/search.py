from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BooleanOperator(StrEnum):
    """Boolean operators supported by the provider-independent query tree."""

    AND = "and"
    OR = "or"
    NOT = "not"


class SearchField(StrEnum):
    """Portable bibliographic fields used by structured search terms."""

    ANY = "any"
    TITLE = "title"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    AUTHOR = "author"
    VENUE = "venue"


class SearchTerm(BaseModel):
    """Leaf node in a structured Boolean search query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["term"] = "term"
    value: str = Field(min_length=1)
    field: SearchField = SearchField.ANY
    exact_phrase: bool = False

    @field_validator("value")
    @classmethod
    def strip_value(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    def to_boolean_query(self) -> str:
        value = self.value
        if self.exact_phrase or " " in value:
            value = f'"{value}"'
        if self.field is SearchField.ANY:
            return value
        return f"{self.field.value}:{value}"


class SearchGroup(BaseModel):
    """Nested Boolean group containing terms or other groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["group"] = "group"
    operator: BooleanOperator
    children: list[SearchExpression]

    @model_validator(mode="after")
    def validate_children(self) -> SearchGroup:
        child_count = len(self.children)
        if self.operator is BooleanOperator.NOT and child_count != 1:
            raise ValueError("NOT groups must contain exactly one child")
        if self.operator in {BooleanOperator.AND, BooleanOperator.OR} and child_count < 2:
            raise ValueError("AND and OR groups must contain at least two children")
        return self

    def to_boolean_query(self) -> str:
        if self.operator is BooleanOperator.NOT:
            return f"NOT ({self.children[0].to_boolean_query()})"
        separator = f" {self.operator.value.upper()} "
        rendered = separator.join(child.to_boolean_query() for child in self.children)
        return f"({rendered})"


SearchExpression = Annotated[SearchTerm | SearchGroup, Field(discriminator="node_type")]
SearchGroup.model_rebuild()


class SearchQuery(BaseModel):
    """Versioned, provider-independent Boolean search query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    expression: SearchExpression
    version: int = Field(default=1, ge=1)
    description: str | None = None
    created_by: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("name", "description", "created_by", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    def to_boolean_query(self) -> str:
        """Render a stable generic Boolean representation of the query tree."""

        return self.expression.to_boolean_query()


class SearchStrategy(BaseModel):
    """Named collection of versioned queries used in one review strategy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: UUID = Field(default_factory=uuid4)
    project_id: UUID | None = None
    name: str = Field(min_length=1)
    description: str | None = None
    queries: list[SearchQuery] = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_unique_query_ids(self) -> SearchStrategy:
        query_ids = [query.query_id for query in self.queries]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("queries must have unique query_id values")
        return self


class SearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchRun(BaseModel):
    """Auditable execution of a structured query against one provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID = Field(default_factory=uuid4)
    project_id: UUID | None = None
    strategy_id: UUID | None = None
    query_id: UUID
    query_version: int = Field(ge=1)
    provider: str = Field(min_length=1)
    provider_version: str | None = None
    rendered_query: str = Field(min_length=1)
    date_from: date | None = None
    date_to: date | None = None
    status: SearchRunStatus = SearchRunStatus.PENDING
    records_retrieved: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    config_hash: str | None = None
    git_commit: str | None = None

    @field_validator(
        "provider",
        "provider_version",
        "rendered_query",
        "config_hash",
        "git_commit",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("errors")
    @classmethod
    def validate_errors(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            stripped = value.strip()
            if not stripped:
                raise ValueError("errors must not contain blank values")
            normalized.append(stripped)
        return normalized

    @field_validator("started_at", "finished_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("run timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_run(self) -> SearchRun:
        if self.date_from is not None and self.date_to is not None:
            if self.date_from > self.date_to:
                raise ValueError("date_from must not be later than date_to")
        if self.started_at is not None and self.finished_at is not None:
            if self.started_at > self.finished_at:
                raise ValueError("started_at must not be later than finished_at")
        if self.status is SearchRunStatus.RUNNING and self.started_at is None:
            raise ValueError("running searches require started_at")
        if self.status in {
            SearchRunStatus.COMPLETED,
            SearchRunStatus.FAILED,
            SearchRunStatus.CANCELLED,
        } and self.finished_at is None:
            raise ValueError("finished searches require finished_at")
        if self.finished_at is not None and self.started_at is None:
            raise ValueError("finished_at requires started_at")
        if self.error_count != len(self.errors):
            raise ValueError("error_count must match the number of errors")
        return self
