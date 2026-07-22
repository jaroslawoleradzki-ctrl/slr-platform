from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.identifiers import Identifier


class Affiliation(BaseModel):
    """Institutional affiliation reported for an author."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    identifiers: list[Identifier] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class Author(BaseModel):
    """Canonical representation of a publication author."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1)
    given_name: str | None = None
    family_name: str | None = None
    identifiers: list[Identifier] = Field(default_factory=list)
    affiliations: list[Affiliation] = Field(default_factory=list)

    @field_validator("display_name", "given_name", "family_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped
