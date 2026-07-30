from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid5

from app.api.dto.search_strategy import (
    SearchResultRecordResponse,
    SearchStrategyExecutionRequest,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)

_RESULT_NAMESPACE = UUID("b7470f55-69ad-57c8-908d-797a83dc696b")


@dataclass(frozen=True, slots=True)
class _ControlledRecord:
    key: str
    project_id: str
    title: str
    authors: tuple[str, ...]
    year: int
    provider: Literal["openalex", "crossref"]
    doi: str | None


_CONTROLLED_RECORDS = (
    _ControlledRecord(
        key="lean-openalex-1",
        project_id="lean_energy",
        title="Lean manufacturing practices and industrial energy efficiency",
        authors=("Anna Kowalska", "Michael Smith"),
        year=2021,
        provider="openalex",
        doi="10.1000/lean-energy.2021.001",
    ),
    _ControlledRecord(
        key="lean-crossref-1",
        project_id="lean_energy",
        title="Kaizen interventions for sustainable production systems",
        authors=("Laura Chen",),
        year=2023,
        provider="crossref",
        doi="10.1000/kaizen.2023.014",
    ),
    _ControlledRecord(
        key="lean-openalex-2",
        project_id="lean_energy",
        title="Energy management in discrete manufacturing",
        authors=("Jan Nowak", "Elena Rossi"),
        year=2024,
        provider="openalex",
        doi=None,
    ),
)


class SearchResultSource(Protocol):
    def search(
        self,
        project_id: str,
        strategy: SearchStrategyExecutionRequest,
    ) -> list[SearchResultRecordResponse]: ...


class ControlledSearchResultSource:
    """Offline deterministic Phase 6.7.2a adapter, replaceable in 6.7.2b."""

    def __init__(
        self,
        project_repository: ProjectPublicationRepository | None = None,
    ) -> None:
        self._project_repository = project_repository or default_project_publication_repository()

    def search(
        self,
        project_id: str,
        strategy: SearchStrategyExecutionRequest,
    ) -> list[SearchResultRecordResponse]:
        self._project_repository.get_publications(project_id)
        selected_providers = set(strategy.providers)
        records = [
            record
            for record in _CONTROLLED_RECORDS
            if record.project_id == project_id
            and record.provider in selected_providers
            and strategy.publication_year_from
            <= record.year
            <= strategy.publication_year_to
        ]
        return [
            SearchResultRecordResponse(
                id=str(uuid5(_RESULT_NAMESPACE, f"{project_id}:{record.key}")),
                title=record.title,
                authors=list(record.authors),
                year=record.year,
                provider=record.provider,
                source_id=record.key,
                doi=record.doi,
            )
            for record in records
        ]


controlled_search_result_source = ControlledSearchResultSource()
