from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.dto.screening import (
    AutomaticCriterionAssessmentResponse,
    CriterionAssessmentRequest,
    ScreeningCriterionResponse,
    ScreeningDecisionResponse,
    ScreeningPublicationIdentifierResponse,
    ScreeningPublicationVenueResponse,
)
from app.domain.full_text_screening import FullTextAvailabilityStatus
from app.domain.identifiers import IdentifierType
from app.domain.publication import DocumentType
from app.domain.screening import ScreeningOutcome
from app.services.full_text_screening_service import (
    FullTextOverview,
    FullTextProgress,
    FullTextReadinessStatus,
    FullTextRecord,
    FullTextRecordPage,
    FullTextScreeningStatus,
)


class FullTextAvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(min_length=1)
    status: FullTextAvailabilityStatus
    external_url: str | None = None
    notes: str | None = None


class FullTextAvailabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FullTextAvailabilityStatus
    external_url: str | None
    notes: str | None

    @classmethod
    def from_domain(cls, value) -> "FullTextAvailabilityResponse":
        return cls(status=value.status, external_url=value.external_url, notes=value.notes)


class FullTextScreeningRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    title: str
    abstract: str | None
    authors: list[str]
    publication_year: int | None
    publication_date: str | None
    identifiers: list[ScreeningPublicationIdentifierResponse]
    doi: str | None
    venue: ScreeningPublicationVenueResponse | None
    publisher: str | None
    document_type: DocumentType | None
    language: str | None
    keywords: list[str]
    urls: list[str]
    open_access: bool | None
    status: FullTextScreeningStatus
    latest_decision: ScreeningDecisionResponse | None
    availability: FullTextAvailabilityResponse
    automatic_assessments: list[AutomaticCriterionAssessmentResponse]

    @classmethod
    def from_read_model(cls, record: FullTextRecord) -> "FullTextScreeningRecordResponse":
        publication = record.publication
        doi = next((item.value for item in publication.identifiers if item.type is IdentifierType.DOI), None)
        return cls(
            publication_id=publication.record_id,
            title=publication.title,
            abstract=publication.abstract,
            authors=[author.display_name for author in publication.authors],
            publication_year=publication.publication_year,
            publication_date=publication.publication_date.isoformat() if publication.publication_date else None,
            identifiers=[ScreeningPublicationIdentifierResponse(type=item.type, value=item.value, source=item.source) for item in publication.identifiers],
            doi=doi,
            venue=ScreeningPublicationVenueResponse(name=publication.venue.name, type=publication.venue.type, publisher=publication.venue.publisher) if publication.venue else None,
            publisher=publication.publisher,
            document_type=publication.document_type,
            language=publication.language,
            keywords=publication.keywords,
            urls=publication.urls,
            open_access=publication.open_access,
            status=record.status,
            latest_decision=ScreeningDecisionResponse.from_domain(record.latest_decision) if record.latest_decision else None,
            availability=FullTextAvailabilityResponse.from_domain(record.availability),
            automatic_assessments=[AutomaticCriterionAssessmentResponse(criterion_id=item.criterion_id, assessment_value=item.assessment_value, evaluated_metadata_value=item.evaluated_metadata_value) for item in record.automatic_assessments],
        )


class FullTextProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    unscreened: int
    included: int
    excluded: int
    uncertain: int
    completed: int

    @classmethod
    def from_read_model(cls, progress: FullTextProgress) -> "FullTextProgressResponse":
        return cls(total=progress.total, unscreened=progress.unscreened, included=progress.included,
                   excluded=progress.excluded, uncertain=progress.uncertain, completed=progress.completed)


class FullTextOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    reviewer_id: str
    ready: bool
    readiness_status: FullTextReadinessStatus
    eligible_records_count: int
    working_collection_count: int
    canonical_records_count: int
    unresolved_duplicate_groups: int
    criteria: list[ScreeningCriterionResponse]
    progress: FullTextProgressResponse | None

    @classmethod
    def from_read_model(cls, overview: FullTextOverview) -> "FullTextOverviewResponse":
        input_set = overview.screening_input
        return cls(
            project_id=overview.project_id, reviewer_id=overview.reviewer_id,
            ready=overview.readiness.ready, readiness_status=overview.readiness.status,
            eligible_records_count=overview.readiness.eligible_count,
            working_collection_count=input_set.working_collection_count,
            canonical_records_count=input_set.canonical_records_count,
            unresolved_duplicate_groups=input_set.unresolved_groups_count,
            criteria=[ScreeningCriterionResponse.from_domain(item) for item in overview.criteria],
            progress=FullTextProgressResponse.from_read_model(overview.progress) if overview.progress else None,
        )


class FullTextScreeningListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    reviewer_id: str
    ready: bool = True
    status_filter: FullTextScreeningStatus | None
    total: int
    offset: int
    limit: int
    items: list[FullTextScreeningRecordResponse]

    @classmethod
    def from_read_model(cls, page: FullTextRecordPage) -> "FullTextScreeningListResponse":
        return cls(project_id=page.project_id, reviewer_id=page.reviewer_id, status_filter=page.status_filter,
                   total=page.total, offset=page.offset, limit=page.limit,
                   items=[FullTextScreeningRecordResponse.from_read_model(item) for item in page.items])


class FullTextDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publication_id: UUID
    reviewer_id: str = Field(min_length=1)
    outcome: ScreeningOutcome
    rationale: str | None = None
    criterion_assessments: list[CriterionAssessmentRequest] = Field(default_factory=list)
    exclusion_reason_criterion_ids: list[UUID] = Field(default_factory=list)
