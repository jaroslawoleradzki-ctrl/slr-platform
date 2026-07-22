import pytest
from pydantic import ValidationError

from app.domain.identifiers import Identifier, IdentifierType


def test_identifier_strips_value() -> None:
    identifier = Identifier(type=IdentifierType.DOI, value=" 10.1000/test ")

    assert identifier.value == "10.1000/test"


def test_identifier_rejects_blank_value() -> None:
    with pytest.raises(ValidationError):
        Identifier(type=IdentifierType.DOI, value="   ")
