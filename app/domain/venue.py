from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.identifiers import Identifier


class VenueType(StrEnum):
    JOURNAL = "journal"
    CONFERENCE = "conference"
    BOOK = "book"
    REPOSITORY = "repository"
    OTHER = "other"


class Venue(BaseModel):
    """Canonical representation of a publication venue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    type: VenueType | None = None
    publisher: str | None = None
    identifiers: list[Identifier] = Field(default_factory=list)

    @field_validator("name", "publisher")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped
