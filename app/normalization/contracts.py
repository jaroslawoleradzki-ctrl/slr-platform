from typing import Protocol, TypeVar

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class Normalizer(Protocol[InputT, OutputT]):
    """Normalize one canonical value or object without provider coupling.

    Implementations must be deterministic, idempotent for their supported
    inputs, and non-mutating. They produce a stable representation for one
    value or object and must not compare, merge, rank, or remove records.
    """

    def normalize(self, value: InputT) -> OutputT: ...
