from app.api.dto.deduplication import (
    DuplicateGroupListResponse,
    DuplicateGroupResponse,
    DuplicateRecordPreviewResponse,
    SharedIdentifierResponse,
)
from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    demo_project_publication_repository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder, duplicate_group_builder


def _extract_shared_identifiers(records: list[Publication]) -> list[SharedIdentifierResponse]:
    """Find shared strong canonical identifiers among members of a candidate group."""
    identifier_counts: dict[tuple[str, str], int] = {}
    for pub in records:
        for ident in pub.identifiers:
            norm_val = normalize_doi(ident.value) if ident.type is IdentifierType.DOI else ident.value.strip()
            if norm_val:
                key = (ident.type.value.lower(), norm_val)
                identifier_counts[key] = identifier_counts.get(key, 0) + 1

    shared = [
        SharedIdentifierResponse(identifier_type=type_name, value=val)
        for (type_name, val), count in identifier_counts.items()
        if count >= 2
    ]
    return sorted(shared, key=lambda s: (s.identifier_type, s.value))


def _map_publication_to_preview(pub: Publication) -> DuplicateRecordPreviewResponse:
    author_names = ", ".join(a.display_name for a in pub.authors) if pub.authors else "Unknown Authors"
    source = pub.provenance[0].source if pub.provenance else "Unknown Source"

    doi: str | None = None
    pmid: str | None = None
    openalex_id: str | None = None

    for ident in pub.identifiers:
        if ident.type is IdentifierType.DOI:
            doi = normalize_doi(ident.value) or ident.value
        elif ident.type is IdentifierType.PMID:
            pmid = ident.value
        elif ident.type is IdentifierType.OPENALEX or (
            ident.type is IdentifierType.OTHER and ident.source and ident.source.casefold() == "openalex"
        ):
            openalex_id = ident.value

    return DuplicateRecordPreviewResponse(
        id=str(pub.record_id),
        title=pub.title,
        authors=author_names,
        year=pub.publication_year,
        source=source,
        doi=doi,
        pmid=pmid,
        openalex_id=openalex_id,
    )


class ProjectDuplicateService:
    """Application service for building candidate duplicate groups for an SLR project.

    Service responsibility:
    - Retrieve project publications from the injected ProjectPublicationRepository.
    - Invoke DuplicateGroupBuilder domain service.
    - Map domain duplicate groups and member publications to DTO responses.
    - Does not contain hardcoded project_id conditionals or persistence logic.
    """

    def __init__(
        self,
        repository: ProjectPublicationRepository = demo_project_publication_repository,
        builder: DuplicateGroupBuilder = duplicate_group_builder,
    ) -> None:
        self._repository = repository
        self._builder = builder

    def get_candidate_duplicate_groups(self, project_id: str) -> DuplicateGroupListResponse:
        publications = self._repository.get_publications(project_id)
        pub_by_id = {pub.record_id: pub for pub in publications}

        domain_groups = self._builder.build(publications)
        group_responses: list[DuplicateGroupResponse] = []

        for domain_group in domain_groups:
            member_pubs = [pub_by_id[pid] for pid in domain_group.publication_ids if pid in pub_by_id]
            if len(member_pubs) < 2:
                continue

            record_previews = [_map_publication_to_preview(pub) for pub in member_pubs]
            shared_idents = _extract_shared_identifiers(member_pubs)

            formatted_idents = ", ".join(f"{s.identifier_type.upper()}: {s.value}" for s in shared_idents)
            reason_str = (
                f"Zgodność identyfikatorów ({formatted_idents})"
                if shared_idents
                else "Identical strong identifier match"
            )

            group_responses.append(
                DuplicateGroupResponse(
                    group_id=str(domain_group.group_id),
                    reason=reason_str,
                    records_count=len(record_previews),
                    shared_identifiers=shared_idents,
                    records=record_previews,
                )
            )

        return DuplicateGroupListResponse(
            project_id=project_id,
            total_groups_count=len(group_responses),
            groups=group_responses,
        )


project_duplicate_service = ProjectDuplicateService()
