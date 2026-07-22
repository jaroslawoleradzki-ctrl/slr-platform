import pytest
from pydantic import ValidationError

from app.domain.venue import Venue, VenueType


def test_venue_normalizes_text() -> None:
    venue = Venue(name=" Journal of Cleaner Production ", type=VenueType.JOURNAL)

    assert venue.name == "Journal of Cleaner Production"
    assert venue.type is VenueType.JOURNAL


def test_venue_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        Venue(name="   ")
