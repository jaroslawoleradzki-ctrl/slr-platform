from typing import Protocol

from app.domain.duplicate_review import DuplicateDecision


class GroupNotFoundError(Exception):
    """Raised when a specified duplicate group_id is not found for a project."""

    def __init__(self, group_id: str, project_id: str | None = None) -> None:
        self.group_id = group_id
        self.project_id = project_id
        msg = (
            f"Duplicate group '{group_id}' not found in project '{project_id}'."
            if project_id
            else f"Duplicate group '{group_id}' not found."
        )
        super().__init__(msg)


class DuplicateReviewDecisionRepository(Protocol):
    """Interface for storing and retrieving duplicate review decisions keyed by (project_id, group_id)."""

    def save_decision(
        self, project_id: str, group_id: str, decision: DuplicateDecision
    ) -> None:
        """Store or update a decision for a duplicate group within a specific project."""
        ...

    def get_decision(
        self, project_id: str, group_id: str
    ) -> DuplicateDecision | None:
        """Retrieve the stored decision for a (project_id, group_id), or None if undecided."""
        ...


class InMemoryDuplicateReviewDecisionRepository:
    """In-memory repository for human duplicate review decisions, keyed by composite (project_id, group_id).

    Boundary Note:
    This in-memory implementation stores reviewer decisions in runtime memory using (project_id, group_id) composite keys.
    It guarantees decision isolation between different projects even if they happen to share a group_id.
    """

    def __init__(self) -> None:
        self._decisions: dict[tuple[str, str], DuplicateDecision] = {}

    def save_decision(
        self, project_id: str, group_id: str, decision: DuplicateDecision
    ) -> None:
        self._decisions[(project_id, group_id)] = decision

    def get_decision(
        self, project_id: str, group_id: str
    ) -> DuplicateDecision | None:
        return self._decisions.get((project_id, group_id))

    def clear(self) -> None:
        """Helper for resetting state between tests."""
        self._decisions.clear()


in_memory_duplicate_review_decision_repository = (
    InMemoryDuplicateReviewDecisionRepository()
)
