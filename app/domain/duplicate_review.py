from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator

MAX_RATIONALE_LENGTH = 1000


class DuplicateDecision(str, Enum):
    """Human review decision for a candidate duplicate group."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"


class DuplicateGroupReviewDecision(BaseModel):
    """Domain model representing a human reviewer decision and optional rationale."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: DuplicateDecision
    rationale: str | None = None

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if len(stripped) > MAX_RATIONALE_LENGTH:
            raise ValueError(f"Rationale text exceeds maximum length of {MAX_RATIONALE_LENGTH} characters.")
        return stripped
