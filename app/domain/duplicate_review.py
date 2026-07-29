from enum import Enum


class DuplicateDecision(str, Enum):
    """Human review decision for a candidate duplicate group."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
