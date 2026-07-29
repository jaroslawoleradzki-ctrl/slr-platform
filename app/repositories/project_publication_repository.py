from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication

_TIME = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)


class ProjectNotFoundError(Exception):
    """Raised when a requested project_id does not exist in the repository."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project '{project_id}' not found.")


class ProjectPublicationRepository(Protocol):
    """Abstraction for retrieving publication collections for an SLR project."""

    def get_publications(self, project_id: str) -> list[Publication]:
        """Retrieve publications for a project or raise ProjectNotFoundError."""
        ...


class DemoProjectPublicationRepository:
    """Temporary in-memory demo repository providing sample SLR project publications.

    Boundary Note:
    This adapter is a temporary demo implementation for Phase 6.3.
    Full project storage and persistence will be introduced in future phases.
    """

    def __init__(self) -> None:
        self._projects_data: dict[str, list[Publication]] = {
            "lean_energy": [
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000101"),
                    title="Energy reduction through lean production in auto manufacturing: A systematic review",
                    authors=[Author(display_name="Smith, J."), Author(display_name="Kowalski, P.")],
                    publication_year=2021,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1016/j.jclepro.2021.102834"),
                        Identifier(type=IdentifierType.OPENALEX, value="W3128349201"),
                    ],
                    provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W3128349201")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000102"),
                    title="Energy reduction through lean production in automotive manufacturing: Systematic Review",
                    authors=[Author(display_name="Smith, John"), Author(display_name="Kowalski, Piotr")],
                    publication_year=2021,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1016/j.jclepro.2021.102834"),
                        Identifier(type=IdentifierType.OPENALEX, value="W3128349201"),
                    ],
                    provenance=[ProvenanceEntry(source="Crossref", source_record_id="10.1016/j.jclepro.2021.102834")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000201"),
                    title="Applying Kaizen principles to lower electricity consumption in foundry operations",
                    authors=[Author(display_name="Müller, H."), Author(display_name="Schmidt, A.")],
                    publication_year=2019,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1007/s00170-019-04122-z"),
                        Identifier(type=IdentifierType.PMID, value="31204912"),
                    ],
                    provenance=[ProvenanceEntry(source="Semantic Scholar", source_record_id="S2-31204912")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000202"),
                    title="Applying Kaizen principles to lower electricity consumption in foundry operations.",
                    authors=[Author(display_name="Muller, H."), Author(display_name="Schmidt, A.")],
                    publication_year=2019,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1007/s00170-019-04122-z"),
                        Identifier(type=IdentifierType.PMID, value="31204912"),
                    ],
                    provenance=[ProvenanceEntry(source="RIS file (Google Scholar export)", source_record_id="IMP-002")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000301"),
                    title="Unique publication on industrial heat recovery without duplicates",
                    authors=[Author(display_name="Taylor, R.")],
                    publication_year=2024,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1016/j.enercon.2024.109988"),
                    ],
                    provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W99887766")],
                    created_at=_TIME,
                ),
            ],
            "ai_architecture": [],
        }

    def get_publications(self, project_id: str) -> list[Publication]:
        if project_id not in self._projects_data:
            raise ProjectNotFoundError(project_id)
        return list(self._projects_data[project_id])


demo_project_publication_repository = DemoProjectPublicationRepository()
