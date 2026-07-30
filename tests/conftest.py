import pytest
from app.repositories.duplicate_review_decision_repository import (
    in_memory_duplicate_review_decision_repository,
)


@pytest.fixture(autouse=True)
def reset_in_memory_decision_repository() -> None:
    """Automatically clear in-memory decision repository state before each test."""
    in_memory_duplicate_review_decision_repository.clear()
