from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.publication import Publication


class DuplicateGroupStatus(StrEnum):
    """Review and merge status of a potential duplicate group."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


class DuplicateDecisionType(StrEnum):
    """Decision types that can change a duplicate group's review status."""

    CONFIRM = "confirm"
    REJECT = "reject"


class InvalidDuplicateGroupTransition(ValueError):
    """Raised when a duplicate group cannot perform a requested transition."""


class DuplicateDecision(BaseModel):
    """Immutable record of one duplicate-group decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: DuplicateDecisionType
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewer_id: str | None = None
    rationale: str | None = None

    @field_validator("reviewer_id", "rationale")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("decided_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        return value


class DuplicateGroup(BaseModel):
    """Infrastructure-independent aggregate for potential duplicate publications."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: UUID = Field(default_factory=uuid4)
    publication_ids: tuple[UUID, ...]
    status: DuplicateGroupStatus = DuplicateGroupStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decision_history: tuple[DuplicateDecision, ...] = ()

    @field_validator("publication_ids")
    @classmethod
    def validate_publication_ids(cls, values: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(values) < 2:
            raise ValueError(
                "a duplicate group must contain at least two publications"
            )
        if len(set(values)) != len(values):
            raise ValueError(
                "a publication must not occur more than once in a duplicate group"
            )
        return values

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_history(self) -> "DuplicateGroup":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")

        expected_status = DuplicateGroupStatus.PENDING
        previous_time = self.created_at
        transitions = {
            (
                DuplicateGroupStatus.PENDING,
                DuplicateDecisionType.CONFIRM,
            ): DuplicateGroupStatus.APPROVED,
            (
                DuplicateGroupStatus.PENDING,
                DuplicateDecisionType.REJECT,
            ): DuplicateGroupStatus.REJECTED,
        }

        for decision in self.decision_history:
            if decision.decided_at < previous_time:
                raise ValueError("decision history must be chronological")
            next_status = transitions.get((expected_status, decision.decision))
            if next_status is None:
                raise ValueError("decision history contains an invalid transition")
            expected_status = next_status
            previous_time = decision.decided_at

        # Handle MERGED status: allowed if last decision was CONFIRM and group was CONFIRMED
        if self.status is DuplicateGroupStatus.MERGED:
            if expected_status is not DuplicateGroupStatus.APPROVED:
                raise ValueError("MERGED status requires previous APPROVED status")
            # For MERGED groups, updated_at can be the merge time (not necessarily the last decision time)
        elif self.status is not expected_status:
            raise ValueError("status must match decision history")

        # For non-MERGED groups, updated_at must equal the latest decision time
        if self.status is not DuplicateGroupStatus.MERGED and self.decision_history and self.updated_at != previous_time:
            raise ValueError("updated_at must equal the latest decision time")
        return self

    def confirm(
        self,
        *,
        decided_at: datetime | None = None,
        reviewer_id: str | None = None,
        rationale: str | None = None,
    ) -> "DuplicateGroup":
        return self._transition(
            DuplicateDecisionType.CONFIRM,
            DuplicateGroupStatus.APPROVED,
            decided_at=decided_at,
            reviewer_id=reviewer_id,
            rationale=rationale,
        )

    def reject(
        self,
        *,
        decided_at: datetime | None = None,
        reviewer_id: str | None = None,
        rationale: str | None = None,
    ) -> "DuplicateGroup":
        return self._transition(
            DuplicateDecisionType.REJECT,
            DuplicateGroupStatus.REJECTED,
            decided_at=decided_at,
            reviewer_id=reviewer_id,
            rationale=rationale,
        )



    def _transition(
        self,
        decision_type: DuplicateDecisionType,
        target_status: DuplicateGroupStatus,
        *,
        decided_at: datetime | None,
        reviewer_id: str | None,
        rationale: str | None,
    ) -> "DuplicateGroup":
        allowed_sources = {
            DuplicateDecisionType.CONFIRM: DuplicateGroupStatus.PENDING,
            DuplicateDecisionType.REJECT: DuplicateGroupStatus.PENDING,
        }
        required_status = allowed_sources[decision_type]
        if self.status is not required_status:
            raise InvalidDuplicateGroupTransition(
                f"cannot {decision_type.value} a duplicate group with "
                f"status {self.status.value}"
            )

        timestamp = decided_at or datetime.now(timezone.utc)
        decision = DuplicateDecision(
            decision=decision_type,
            decided_at=timestamp,
            reviewer_id=reviewer_id,
            rationale=rationale,
        )
        if decision.decided_at < self.updated_at:
            raise InvalidDuplicateGroupTransition(
                "decision time must not be earlier than updated_at"
            )
        values = self.model_dump()
        values.update(
            status=target_status,
            updated_at=timestamp,
            decision_history=(*self.decision_history, decision),
        )
        return DuplicateGroup.model_validate(values)

class DuplicateGroupMergeRecord(BaseModel):
    """Durable technical merge state, deliberately separate from reviewer decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    canonical_record_id: UUID
    merged_publication_ids: tuple[UUID, ...]
    merged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "merged"
    pre_merge_snapshots: tuple[Publication, ...] = ()

    @model_validator(mode="after")
    def validate_merge(self) -> "DuplicateGroupMergeRecord":
        if self.status not in {"merged", "reverted"}:
            raise ValueError("status must be merged or reverted")
        if len(self.merged_publication_ids) < 2 or len(set(self.merged_publication_ids)) != len(self.merged_publication_ids):
            raise ValueError("a merge requires unique publication IDs")
        if self.canonical_record_id not in self.merged_publication_ids:
            raise ValueError("canonical record must be a merge member")
        if {p.record_id for p in self.pre_merge_snapshots} != set(self.merged_publication_ids):
            raise ValueError("pre-merge snapshots must cover all merge members")
        return self
