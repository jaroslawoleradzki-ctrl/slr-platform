"""v0.7.3 R5.2 candidate-generation equivalence and reuse regressions.

These tests are deterministic and functional.  Wall-clock measurements live in
the R5 remediation report; the comparison-count assertion here catches an
accidental return to unbounded all-pairs comparisons without depending on
shared-runner timing.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.normalization.title import titles_are_similar
from app.repositories.conflict_resolution_repository import (
    SqliteConflictResolutionRepository,
)
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.pre_screening_archive_repository import (
    SqlitePreScreeningArchiveRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services import duplicate_group_builder as builder_module
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_workflow_status_service import ProjectWorkflowStatusService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService

_CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)

_TOPICS = (
    "artificial intelligence",
    "higher education",
    "student engagement",
    "learning analytics",
    "teacher training",
    "digital literacy",
    "assessment design",
    "online learning",
    "research methods",
    "curriculum development",
)
_QUALIFIERS = (
    "systematic review",
    "meta analysis",
    "longitudinal study",
    "case study",
    "mixed methods investigation",
    "empirical evaluation",
    "comparative analysis",
    "qualitative inquiry",
)
_COMMON = (
    "the effects of artificial intelligence on student learning outcomes in "
    "higher education institutions"
)


def _publication(
    index: int,
    title: str,
    *,
    doi: str | None = None,
    year: int = 2020,
    namespace: str = "r5-candidates",
) -> Publication:
    identifiers = [Identifier(type=IdentifierType.DOI, value=doi)] if doi else []
    return Publication(
        record_id=uuid5(NAMESPACE_URL, f"{namespace}:{index}"),
        title=title,
        authors=[Author(display_name=f"Author {index % 37}")],
        publication_year=year,
        identifiers=identifiers,
        provenance=[
            ProvenanceEntry(
                source="google_scholar_pop",
                source_record_id=f"src-{index}",
                transformation="ris_to_publication",
            )
        ],
    )


def _dataset(count: int, namespace: str = "r5-candidates") -> list[Publication]:
    """Fixture exercising categories A-E with comparable title families."""
    publications: list[Publication] = []
    seed = 0

    def make(index: int, title: str, **kwargs) -> None:
        publications.append(_publication(index, title, namespace=namespace, **kwargs))

    while len(publications) < count:
        # A: mostly unrelated titles.
        for _ in range(6):
            if len(publications) >= count:
                break
            make(
                seed,
                f"unique {_QUALIFIERS[seed % len(_QUALIFIERS)]} of "
                f"{_TOPICS[seed % len(_TOPICS)]} for cohort {seed} in "
                f"region {seed % 17}",
            )
            seed += 1
        # B: exact duplicate-title group.
        if len(publications) + 3 <= count:
            title = (
                f"exact duplicate group {seed // 3}: "
                f"{_TOPICS[seed % len(_TOPICS)]} and "
                f"{_TOPICS[(seed + 3) % len(_TOPICS)]} in {seed % 11} institutions"
            )
            for member in range(3):
                make(seed + member, title, year=2018 + member)
            seed += 3
        # C: conservative similar-title pair.
        if len(publications) + 2 <= count:
            title = (
                f"similar candidate {seed // 2}: "
                f"{_QUALIFIERS[seed % len(_QUALIFIERS)]} of "
                f"{_TOPICS[seed % len(_TOPICS)]} in higher education"
            )
            make(seed, title)
            make(
                seed + 1,
                title.replace("higher education", "higher education systems"),
            )
            seed += 2
        # D: DOI-bearing and no-DOI records with the same title.
        if len(publications) + 2 <= count:
            title = (
                f"doi mixed evidence {seed // 2}: "
                f"{_TOPICS[seed % len(_TOPICS)]} for student outcomes in "
                f"{seed % 9} countries"
            )
            make(seed, title, doi=f"10.5555/r5.{seed}")
            make(seed + 1, title)
            seed += 2
        # E: adversarial high-collision title family.
        if len(publications) < count:
            make(
                seed,
                f"{_COMMON} {_TOPICS[seed % len(_TOPICS)]} "
                f"cohort {seed} variant {seed % 13}",
            )
            seed += 1
    return publications[:count]


def _reference_groups(publications: list[Publication]) -> list[tuple[UUID, ...]]:
    """Literal all-pairs reference implementation of title candidate logic."""
    parent = {publication.record_id: publication.record_id for publication in publications}

    def find(record_id: UUID) -> UUID:
        while parent[record_id] != record_id:
            parent[record_id] = parent[parent[record_id]]
            record_id = parent[record_id]
        return record_id

    def union(first: UUID, second: UUID) -> None:
        first_root, second_root = sorted((find(first), find(second)))
        if first_root != second_root:
            parent[second_root] = first_root

    titles = {publication.record_id: publication.title for publication in publications}
    file_ids = {
        publication.record_id
        for publication in publications
        if publication.provenance
        and publication.provenance[0].transformation == "ris_to_publication"
    }

    buckets: dict[str, list[UUID]] = {}
    for publication in publications:
        buckets.setdefault(titles[publication.record_id], []).append(publication.record_id)
    for bucket in buckets.values():
        if len(bucket) < 2 or not any(record_id in file_ids for record_id in bucket):
            continue
        for record_id in bucket[1:]:
            union(bucket[0], record_id)

    file_origin = sorted(record_id for record_id in file_ids if titles.get(record_id))
    for first in file_origin:
        first_title = titles[first]
        for second in publications:
            if second.record_id == first:
                continue
            second_title = titles[second.record_id]
            if second_title == first_title:
                continue
            if abs(len(first_title) - len(second_title)) > 25:
                continue
            if titles_are_similar(first_title, second_title):
                union(first, second.record_id)

    members: dict[UUID, list[UUID]] = {}
    for record_id in parent:
        members.setdefault(find(record_id), []).append(record_id)
    return sorted(
        tuple(sorted(member_ids))
        for member_ids in members.values()
        if len(member_ids) >= 2
    )


def _builder_members(publications: list[Publication]) -> list[tuple[UUID, ...]]:
    groups = DuplicateGroupBuilder().build(
        publications, created_at=_CREATED_AT, include_title_candidates=True
    )
    return [group.publication_ids for group in groups]


def test_optimized_candidates_match_all_pairs_reference() -> None:
    for count in (120, 300, 600):
        publications = _dataset(count)
        assert _builder_members(publications) == _reference_groups(publications)


def test_similar_title_candidate_is_preserved() -> None:
    first = _publication(1, "systematic review of learning analytics in higher education")
    second = _publication(
        2, "systematic review of learning analytics in higher education systems"
    )

    groups = DuplicateGroupBuilder().build(
        [first, second], created_at=_CREATED_AT, include_title_candidates=True
    )

    assert len(groups) == 1
    assert groups[0].publication_ids == (first.record_id, second.record_id)
    assert groups[0].match_type == "similar_title"
    assert groups[0].publication_ids == tuple(sorted(groups[0].publication_ids))


def test_numeric_only_title_variants_remain_rejected() -> None:
    first = _publication(1, "study 201")
    second = _publication(2, "study 202")

    assert (
        DuplicateGroupBuilder().build(
            [first, second], created_at=_CREATED_AT, include_title_candidates=True
        )
        == []
    )


def test_short_title_typo_candidates_use_short_bucket() -> None:
    exact = _publication(1, "deep learning")
    typo = _publication(2, "deep learnin")
    duplicate = _publication(3, "deep learning")

    groups = DuplicateGroupBuilder().build(
        [exact, typo, duplicate], created_at=_CREATED_AT, include_title_candidates=True
    )

    assert len(groups) == 1
    assert set(groups[0].publication_ids) == {
        exact.record_id,
        duplicate.record_id,
        typo.record_id,
    }


def test_exact_title_with_conflicting_doi_evidence_is_preserved() -> None:
    with_doi = _publication(1, "shared title", doi="10.5555/conflict")
    without_doi = _publication(2, "shared title")

    groups = DuplicateGroupBuilder().build(
        [with_doi, without_doi], created_at=_CREATED_AT, include_title_candidates=True
    )

    assert len(groups) == 1
    assert groups[0].match_type == "conflicting_identifiers"


def test_candidate_generation_is_deterministic_and_project_isolated() -> None:
    first_project = _dataset(200, namespace="r5-project-a")
    second_project = _dataset(200, namespace="r5-project-b")

    first_groups = _builder_members(first_project)
    assert first_groups == _builder_members(first_project)
    second_groups = _builder_members(second_project)

    first_ids = {record_id for group in first_groups for record_id in group}
    second_ids = {record_id for group in second_groups for record_id in group}
    assert not first_ids & second_ids


def test_comparison_count_is_bounded_for_large_normal_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publications = _dataset(1000)
    calls = 0
    original = builder_module.prepared_titles_are_similar

    def counted(*args, **kwargs) -> bool:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(builder_module, "prepared_titles_are_similar", counted)

    groups = DuplicateGroupBuilder().build(
        publications, created_at=_CREATED_AT, include_title_candidates=True
    )

    assert groups
    # The pre-remediation implementation compared every file-import record with
    # the whole collection (~500k comparisons at this size and far more at 2000).
    assert calls < 100_000


@pytest.fixture
def prisma_environment(tmp_path: Path):
    database = tmp_path / "r5-prisma.db"
    project_id = "r5_project"
    project_repo = SqliteProjectRepository(database)
    project_repo.create(Project(project_id=project_id, title="R5 Project"))
    publications = SqliteProjectPublicationRepository(database)
    publications.add_publications(project_id, _dataset(120))
    history = SqliteImportHistoryRepository(database)
    duplicate_decisions = SqliteDuplicateReviewDecisionRepository(database)
    screening_decisions = SqliteScreeningDecisionRepository(database)
    assignments = SqliteScreeningReviewerAssignmentRepository(database)
    resolutions = SqliteConflictResolutionRepository(database)
    reporting = ScreeningReportingRepository(database)

    input_service = ScreeningInputService(publications, duplicate_decisions)
    multi_service = MultiReviewerScreeningService(
        assignments=assignments,
        reporting=reporting,
        input_service=input_service,
        resolutions=resolutions,
    )
    adapter = ScreeningEligibilityAdapter(
        input_service=input_service,
        assignments_repo=assignments,
        decisions_repo=screening_decisions,
        multi_reviewer_service=multi_service,
    )
    workflow_status = ProjectWorkflowStatusService(
        publication_repository=publications,
        decision_repository=screening_decisions,
        assignment_repository=assignments,
        resolution_repository=resolutions,
        reporting_repository=reporting,
        input_service=input_service,
        multi_reviewer_service=multi_service,
        eligibility_adapter=adapter,
    )
    builder = DuplicateGroupBuilder()
    service = PrismaMetricsService(
        publication_repository=publications,
        import_history_repository=history,
        decision_repository=duplicate_decisions,
        workflow_status_service=workflow_status,
        builder=builder,
        archive_repository=SqlitePreScreeningArchiveRepository(database),
        merge_repository=SqliteDuplicateMergeRepository(database),
        source_record_repository=SqliteImportSourceRecordRepository(database),
    )
    duplicate_service = ProjectDuplicateService(
        repository=publications,
        decision_repository=duplicate_decisions,
        builder=builder,
        merge_repository=SqliteDuplicateMergeRepository(database),
        source_record_repository=SqliteImportSourceRecordRepository(database),
    )
    return service, duplicate_service, builder, project_id


def _count_builds(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    calls: Counter[str] = Counter()
    original = DuplicateGroupBuilder.build

    def counted(self, *args, **kwargs):
        calls["build"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DuplicateGroupBuilder, "build", counted)
    return calls


def test_prisma_builds_duplicate_groups_once_per_population(
    prisma_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, project_id = prisma_environment
    calls = _count_builds(monkeypatch)

    metrics = service.get_metrics(project_id)

    assert metrics.duplicate_groups_pending_review > 0
    # One build for the active population and one reused screening input set for
    # workflow status plus excluded counts (the pre-remediation path used three).
    assert calls["build"] == 2


def test_duplicate_group_service_builds_once_per_request(
    prisma_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, duplicate_service, _, project_id = prisma_environment
    calls = _count_builds(monkeypatch)

    response = duplicate_service.get_candidate_duplicate_groups(project_id)

    assert response.groups
    assert calls["build"] == 1
