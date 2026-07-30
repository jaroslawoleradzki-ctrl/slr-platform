from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class NormalizationResponse(BaseModel):
    run_id: UUID
    project_id: str
    status: Literal["completed", "warning", "error"]
    processed_records: int
    clean_records: int
    warnings_count: int
    errors_count: int
    rules_applied: list[str]
    audit_trail: list[str]
    started_at: datetime
    completed_at: datetime
    executed_at: datetime
    error_message: str | None = None
