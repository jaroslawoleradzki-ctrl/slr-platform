from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntegrityCheckLevel(StrEnum):
    """Level assigned to an individual audit check."""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class IntegrityAuditStatus(StrEnum):
    """Overall status of the project data integrity audit."""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class IntegrityCheckResult(BaseModel):
    """Result of an individual data integrity audit check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    level: IntegrityCheckLevel
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class IntegrityAuditReport(BaseModel):
    """Complete, deterministic result report for a project data integrity audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    status: IntegrityAuditStatus
    checks: tuple[IntegrityCheckResult, ...] = ()

    @property
    def is_ok(self) -> bool:
        return self.status is IntegrityAuditStatus.OK
