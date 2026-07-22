from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IdentifierType(StrEnum):
    DOI = "doi"
    ISSN = "issn"
    ISBN = "isbn"
    PMID = "pmid"
    OPENALEX = "openalex"
    ORCID = "orcid"
    OTHER = "other"


class Identifier(BaseModel):
    """External identifier assigned to a publication or related entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: IdentifierType
    value: str = Field(min_length=1)
    source: str | None = None

    @field_validator("value", "source")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped
