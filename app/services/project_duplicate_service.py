from app.api.dto.deduplication import (
    DuplicateDecisionStatus,
    DuplicateDecisionType,
    DuplicateGroupDecisionResponse,
    DuplicateGroupListResponse,
    DuplicateGroupResponse,
    DuplicateRecordPreviewResponse,
    ProvenanceEntryResponse,
    SharedIdentifierResponse,
)
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    GroupNotFoundError,
    in_memory_duplicate_review_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
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
    venue_str = pub.venue.name if pub.venue else None

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

    provenance_responses = [
        ProvenanceEntryResponse(
            source=p.source,
            source_record_id=p.source_record_id,
            retrieved_at=p.retrieved_at.isoformat() if p.retrieved_at else None,
        )
        for p in pub.provenance
    ]

    return DuplicateRecordPreviewResponse(
        id=str(pub.record_id),
        title=pub.title,
        authors=author_names,
        year=pub.publication_year,
        source=source,
        venue=venue_str,
        doi=doi,
        pmid=pmid,
        openalex_id=openalex_id,
        provenance=provenance_responses,
    )


class ProjectDuplicateService:
    """Application service for building candidate duplicate groups and managing reviewer decisions.

    Service responsibilities:
    - Retrieve project publications from the injected ProjectPublicationRepository.
    - Invoke DuplicateGroupBuilder domain service.
    - Map domain duplicate groups and member publications to DTO responses.
    - Record and retrieve duplicate review decisions via DuplicateReviewDecisionRepository (keyed by project_id and group_id).
    - Does not modify Publication objects or execute merges.
    """

    def __init__(
        self,
        repository: ProjectPublicationRepository | None = None,
        decision_repository: DuplicateReviewDecisionRepository = in_memory_duplicate_review_decision_repository,
        builder: DuplicateGroupBuilder = duplicate_group_builder,
    ) -> None:
        self._repository = repository or default_project_publication_repository()
        self._decision_repository = decision_repository
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

            group_id_str = str(domain_group.group_id)
            record_previews = [_map_publication_to_preview(pub) for pub in member_pubs]
            shared_idents = _extract_shared_identifiers(member_pubs)

            formatted_idents = ", ".join(f"{s.identifier_type.upper()}: {s.value}" for s in shared_idents)
            reason_str = (
                f"Zgodność identyfikatorów ({formatted_idents})"
                if shared_idents
                else "Identical strong identifier match"
            )

            domain_decision = self._decision_repository.get_decision(project_id, group_id_str)
            status_enum = (
                DuplicateDecisionStatus(domain_decision.decision.value)
                if domain_decision
                else DuplicateDecisionStatus.PENDING
            )

            group_responses.append(
                DuplicateGroupResponse(
                    group_id=group_id_str,
                    reason=reason_str,
                    records_count=len(record_previews),
                    status=status_enum,
                    shared_identifiers=shared_idents,
                    records=record_previews,
                )
            )

        return DuplicateGroupListResponse(
            project_id=project_id,
            total_groups_count=len(group_responses),
            groups=group_responses,
        )

    def _ensure_group_exists(self, project_id: str, group_id: str) -> None:
        publications = self._repository.get_publications(project_id)
        domain_groups = self._builder.build(publications)
        group_ids = {str(dg.group_id) for dg in domain_groups}
        if group_id not in group_ids:
            raise GroupNotFoundError(group_id, project_id)

    def record_decision(
        self,
        project_id: str,
        group_id: str,
        decision: DuplicateDecisionType | str,
        rationale: str | None = None,
    ) -> DuplicateGroupDecisionResponse:
        self._ensure_group_exists(project_id, group_id)
        domain_decision_enum = (
            decision
            if isinstance(decision, DuplicateDecision)
            else DuplicateDecision(decision if isinstance(decision, str) else decision.value)
        )
        domain_record = DuplicateGroupReviewDecision(
            decision=domain_decision_enum,
            rationale=rationale,
        )
        self._decision_repository.save_decision(project_id, group_id, domain_record)
        return DuplicateGroupDecisionResponse(
            project_id=project_id,
            group_id=group_id,
            decision=DuplicateDecisionStatus(domain_record.decision.value),
            rationale=domain_record.rationale,
        )

    def get_decision(self, project_id: str, group_id: str) -> DuplicateGroupDecisionResponse:
        self._ensure_group_exists(project_id, group_id)
        domain_record = self._decision_repository.get_decision(project_id, group_id)
        if domain_record is None:
            return DuplicateGroupDecisionResponse(
                project_id=project_id,
                group_id=group_id,
                decision=DuplicateDecisionStatus.PENDING,
                rationale=None,
            )
        return DuplicateGroupDecisionResponse(
            project_id=project_id,
            group_id=group_id,
            decision=DuplicateDecisionStatus(domain_record.decision.value),
            rationale=domain_record.rationale,
        )


project_duplicate_service = ProjectDuplicateService()
