from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.domain.author import Author
from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionConfigurationNotFoundError,
    FieldDataType,
    ValueOrigin,
    ValueStatus,
)
from app.domain.publication import Publication
from app.services.extraction_dataset_service import ExtractionDatasetService

PROJECT_ID = "project"
PUB_COMPLETE = UUID("00000000-0000-0000-0000-000000000001")
PUB_IN_PROGRESS = UUID("00000000-0000-0000-0000-000000000002")
PUB_NEEDS_REVIEW = UUID("00000000-0000-0000-0000-000000000003")
STAMP = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _value(
    key: str,
    *,
    text: str | None = None,
    status: ValueStatus = ValueStatus.PRESENT,
    origin: ValueOrigin | None = ValueOrigin.REPORTED,
    json_value: list[str] | None = None,
    float_value: float | None = None,
    unit_value: str | None = None,
) -> ExtractedValueState:
    missingness = status in (ValueStatus.UNASSESSED, ValueStatus.NOT_REPORTED, ValueStatus.NOT_APPLICABLE)
    return ExtractedValueState(
        field_key=key,
        status=status,
        origin=None if missingness else origin,
        text_value=None if missingness else text,
        json_value=None if missingness else json_value,
        float_value=None if missingness else float_value,
        unit_value=None if missingness else unit_value,
        source_page=None if missingness else "14",
        source_section=None if missingness else "Results",
        source_locator=None if missingness else "Table 2, row 3",
        source_quote=None if missingness else "short quote",
        reviewer_note=None if missingness else "coded note",
    )


class FakeDataset:
    def __init__(self) -> None:
        self.config = SimpleNamespace(template_id="template", template_version="1.0.0")
        self.publications = [
            Publication(
                record_id=PUB_COMPLETE,
                title="Canonical title",
                authors=[Author(display_name="A. Author")],
                publication_year=2024,
            ),
            Publication(record_id=PUB_IN_PROGRESS, title="Draft", publication_year=2023),
            Publication(record_id=PUB_NEEDS_REVIEW, title="Review", publication_year=2022),
        ]
        self.revisions = {
            PUB_COMPLETE: SimpleNamespace(
                revision_id=uuid4(),
                revision_index=2,
                reviewer_id="reviewer",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                created_at=STAMP,
                publication_values=[
                    _value("multi", json_value=["z", "a"], origin=ValueOrigin.REVIEWER_CODED),
                    _value("missing", status=ValueStatus.NOT_APPLICABLE),
                ],
                group_items=[
                    ExtractedGroupItemState(
                        group_key="relationships",
                        item_index=2,
                        values=[_value("effect", float_value=2.5, unit_value="kWh")],
                    ),
                    ExtractedGroupItemState(
                        group_key="relationships",
                        item_index=1,
                        values=[_value("effect", float_value=1.5, unit_value="kWh")],
                    ),
                ],
            ),
            PUB_IN_PROGRESS: SimpleNamespace(
                revision_id=uuid4(),
                revision_index=3,
                reviewer_id="reviewer",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
                created_at=STAMP,
                publication_values=[],
                group_items=[],
            ),
            PUB_NEEDS_REVIEW: SimpleNamespace(
                revision_id=uuid4(),
                revision_index=1,
                reviewer_id="reviewer",
                completeness_status=ExtractionCompletenessStatus.NEEDS_REVIEW,
                created_at=STAMP,
                publication_values=[],
                group_items=[],
            ),
        }
        self.publication_calls = 0
        self.revision_calls = 0

    def config_service(self):
        return SimpleNamespace(get_configuration=lambda project_id: self.config if project_id == PROJECT_ID else None)

    def eligibility_service(self):
        return SimpleNamespace(
            get_eligible_publications=lambda project_id, reviewer_id="": (
                [SimpleNamespace(publication_id=pub.record_id, is_eligible=True) for pub in self.publications]
                if project_id == PROJECT_ID
                else []
            )
        )

    def publication_repo(self):
        def get_publications(project_id: str):
            self.publication_calls += 1
            return self.publications

        return SimpleNamespace(get_publications=get_publications)

    def extraction_repo(self):
        def get_latest_revision_batch(project_id: str, publication_ids: list[UUID], reviewer_id: str = ""):
            self.revision_calls += 1
            return {publication_id: self.revisions.get(publication_id) for publication_id in publication_ids}

        return SimpleNamespace(get_latest_revision_batch=get_latest_revision_batch)

    def template_repo(self):
        fields = [
            SimpleNamespace(field_key="multi", data_type=FieldDataType.MULTI_ENUM),
            SimpleNamespace(field_key="missing", data_type=FieldDataType.TEXT),
        ]
        relation_fields = [SimpleNamespace(field_key="effect", data_type=FieldDataType.NUMBER_WITH_UNIT)]
        return SimpleNamespace(
            get_version=lambda template_id, version: SimpleNamespace(
                publication_fields=fields,
                repeating_groups=[SimpleNamespace(group_key="relationships", field_definitions=relation_fields)],
            )
        )


def _service(fake: FakeDataset) -> ExtractionDatasetService:
    return ExtractionDatasetService(
        config_service=fake.config_service(),
        eligibility_service=fake.eligibility_service(),
        template_repo=fake.template_repo(),
        extraction_repo=fake.extraction_repo(),
        publication_repo=fake.publication_repo(),
    )


def test_default_read_contract_uses_latest_complete_revision_and_preserves_one_to_many() -> None:
    fake = FakeDataset()
    service = _service(fake)

    publications = service.get_publication_read_models(PROJECT_ID)
    relationships = service.get_relationship_read_models(PROJECT_ID)

    assert [model.publication_id for model in publications] == [PUB_COMPLETE]
    assert publications[0].latest_revision_index == 2
    assert publications[0].canonical_title == "Canonical title"
    assert [item.item_index for item in relationships] == [1, 2]
    assert len(relationships) == 2
    assert fake.publication_calls == 2
    assert fake.revision_calls == 2


def test_all_statuses_are_available_only_when_explicitly_requested() -> None:
    fake = FakeDataset()
    models = _service(fake).get_publication_read_models(PROJECT_ID, status_filter=None)
    assert [model.completeness_status for model in models] == [
        ExtractionCompletenessStatus.COMPLETE,
        ExtractionCompletenessStatus.IN_PROGRESS,
        ExtractionCompletenessStatus.NEEDS_REVIEW,
    ]


def test_json_is_typed_provenance_preserving_and_deterministic() -> None:
    fake = FakeDataset()
    payload = _service(fake).export_json(PROJECT_ID)
    values = {value["field_key"]: value for value in payload[0]["publication_values"]}
    assert values["multi"]["json_value"] == ["a", "z"]
    assert values["multi"]["origin"] == "reviewer_coded"
    assert values["multi"]["source_page"] == "14"
    assert payload[0]["group_items"][0]["item_index"] == 1


def test_csv_separates_datasets_and_serializes_status_origin_units_and_provenance() -> None:
    fake = FakeDataset()
    service = _service(fake)
    publications_csv = service.export_csv(PROJECT_ID)
    relationships_csv = service.export_csv(PROJECT_ID, dataset="relationships")

    assert "multi__status" in publications_csv
    assert "multi__origin" in publications_csv
    assert "missing__status" in publications_csv
    assert "multi__source_page" in publications_csv
    assert "a; z" in publications_csv
    assert "relationships" in relationships_csv
    assert "effect__unit" in relationships_csv
    assert "kWh" in relationships_csv
    assert relationships_csv.count("\n") == 3


def test_empty_dataset_is_a_valid_empty_export() -> None:
    fake = FakeDataset()
    fake.eligibility_service = lambda: SimpleNamespace(get_eligible_publications=lambda *args: [])
    service = _service(fake)
    assert service.export_json(PROJECT_ID) == []
    assert "project_id" in service.export_csv(PROJECT_ID)


def test_missing_configuration_is_an_explicit_error() -> None:
    fake = FakeDataset()
    service = _service(fake)
    try:
        service.get_publication_read_models("missing")
    except ExtractionConfigurationNotFoundError:
        pass
    else:
        raise AssertionError("missing configuration must not produce a dataset")


def test_relationship_read_model_and_exports_preserve_group_item_id() -> None:
    fake = FakeDataset()
    service = _service(fake)
    relationships = service.get_relationship_read_models(PROJECT_ID)
    assert len(relationships) == 2
    # Verify group_item_id is a UUID and matches fake revision data sorted by item_index
    sorted_items = sorted(fake.revisions[PUB_COMPLETE].group_items, key=lambda item: item.item_index)
    expected_ids = [item.group_item_id for item in sorted_items]
    assert [rel.group_item_id for rel in relationships] == expected_ids

    # Verify JSON export includes group_item_id
    json_data = service.export_json(PROJECT_ID)
    exported_group_items = json_data[0]["group_items"]
    assert len(exported_group_items) == 2
    assert [item["group_item_id"] for item in exported_group_items] == [str(uid) for uid in expected_ids]

    # Verify CSV export includes group_item_id column and values
    csv_data = service.export_csv(PROJECT_ID, dataset="relationships")
    assert "group_item_id" in csv_data
    for uid in expected_ids:
        assert str(uid) in csv_data
