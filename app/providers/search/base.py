from __future__ import annotations

from dataclasses import dataclass

from app.domain.publication import Publication

JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)
JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ProviderSearchOutput:
    """Canonical results and ordered raw pages from one provider request."""

    publications: list[Publication]
    raw_responses: list[JsonObject]
    total_count: int | None = None
    next_cursor: str | None = None
    has_more: bool = False
