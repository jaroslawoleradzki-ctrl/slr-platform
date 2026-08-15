"""Unit tests for Data Extraction domain models and value system (Phase 9.1)."""

from uuid import uuid4

import pytest

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionFieldDefinition,
    ExtractionProvenance,
    ExtractionRecord,
    ExtractionRepeatingGroupDefinition,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    FieldDataType,
    InvalidRevisionError,
    InvalidTemplateError,
    InvalidValueError,
    QuantitativeValue,
    ValueOrigin,
    ValueStatus,
)


class TestFieldDataTypesAndEnums:
    def test_all_12_field_data_types_exist(self):
        expected_types = {
            "text",
            "long_text",
            "integer",
            "decimal",
            "boolean",
            "date",
            "enum",
            "multi_enum",
            "identifier",
            "url",
            "number_with_unit",
            "repeating_group",
        }
        actual_types = {dt.value for dt in FieldDataType}
        assert actual_types == expected_types

    def test_value_status_enum(self):
        statuses = {s.value for s in ValueStatus}
        assert statuses == {"unassessed", "present", "not_reported", "not_applicable", "unclear"}

    def test_value_origin_enum_has_no_derived(self):
        origins = {o.value for o in ValueOrigin}
        assert origins == {"reported", "reviewer_coded"}
        assert "derived" not in origins


class TestQuantitativeValueAndProvenance:
    def test_quantitative_value_creation(self):
        qv = QuantitativeValue(numeric_value=42.5, unit="kg", measurement_type="absolute")
        assert qv.numeric_value == 42.5
        assert qv.unit == "kg"
        assert qv.measurement_type == "absolute"

    def test_provenance_valid_source_quote(self):
        prov = ExtractionProvenance(
            source_page="p. 12",
            source_section="Results",
            source_locator="Table 1",
            source_quote="Verbatim quote",
            reviewer_note="Extracted carefully",
        )
        assert prov.source_quote == "Verbatim quote"

    def test_provenance_source_quote_exceeding_500_chars_raises(self):
        long_quote = "a" * 501
        with pytest.raises(InvalidValueError, match="source_quote must not exceed 500 characters"):
            ExtractionProvenance(source_quote=long_quote)


class TestExtractedValueState:
    def test_valid_present_text_value(self):
        val = ExtractedValueState(
            field_key="sample_size",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="100 participants",
            source_locator="Table 1",
        )
        assert val.field_key == "sample_size"
        assert val.status == ValueStatus.PRESENT
        assert val.origin == ValueOrigin.REPORTED
        assert val.text_value == "100 participants"

    def test_present_status_without_typed_value_raises(self):
        with pytest.raises(
            InvalidValueError,
            match="Extracted value for field 'sample_size' with status PRESENT must have at least one typed value",
        ):
            ExtractedValueState(
                field_key="sample_size",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
            )

    def test_unit_value_alone_is_not_extracted_evidence(self):
        with pytest.raises(InvalidValueError, match="PRESENT must have at least one typed value"):
            ExtractedValueState(
                field_key="effect_magnitude",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                unit_value="kWh",
                source_locator="Results table",
            )

    def test_unclear_unit_value_alone_is_not_tentative_evidence(self):
        with pytest.raises(InvalidValueError, match="Unclear field 'effect_magnitude'"):
            ExtractedValueState(
                field_key="effect_magnitude",
                status=ValueStatus.UNCLEAR,
                origin=ValueOrigin.REPORTED,
                unit_value="kWh",
                reviewer_note="The unit is mentioned without a magnitude.",
            )

    def test_numeric_value_with_unit_is_evidence(self):
        value = ExtractedValueState(
            field_key="effect_magnitude",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            float_value=12.5,
            unit_value="kWh",
            source_locator="Results table",
        )
        assert value.float_value == 12.5

    def test_not_reported_status_with_typed_value_raises(self):
        with pytest.raises(
            InvalidValueError,
            match="Extracted value for field 'sample_size' with status not_reported must have all typed values set to None",
        ):
            ExtractedValueState(
                field_key="sample_size",
                status=ValueStatus.NOT_REPORTED,
                origin=ValueOrigin.REPORTED,
                int_value=42,
            )

    def test_not_applicable_status_with_typed_value_raises(self):
        with pytest.raises(
            InvalidValueError,
            match="Extracted value for field 'sample_size' with status not_applicable must have all typed values set to None",
        ):
            ExtractedValueState(
                field_key="sample_size",
                status=ValueStatus.NOT_APPLICABLE,
                origin=ValueOrigin.REVIEWER_CODED,
                text_value="n/a",
            )

    def test_unclear_status_allows_null_or_typed_value(self):
        v1 = ExtractedValueState(
            field_key="country",
            status=ValueStatus.UNCLEAR,
            origin=ValueOrigin.REVIEWER_CODED,
            text_value="Unclear if UK or USA",
            reviewer_note="The source does not distinguish the country.",
        )
        assert v1.text_value == "Unclear if UK or USA"

        v2 = ExtractedValueState(
            field_key="country",
            status=ValueStatus.UNCLEAR,
            reviewer_note="The source is ambiguous.",
        )
        assert v2.text_value is None

    def test_invalid_origin_raises(self):
        with pytest.raises(ValueError):
            ExtractedValueState(
                field_key="country",
                status=ValueStatus.PRESENT,
                origin="derived",  # type: ignore
                text_value="UK",
            )


class TestExtractedGroupItemState:
    def test_valid_group_item(self):
        item = ExtractedGroupItemState(
            group_key="relationships",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="outcome",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Positive",
                    source_locator="Results table",
                )
            ],
        )
        assert item.group_key == "relationships"
        assert item.item_index == 1
        assert len(item.values) == 1

    def test_invalid_item_index_raises(self):
        with pytest.raises(InvalidValueError, match="item_index must be >= 1"):
            ExtractedGroupItemState(
                group_key="relationships",
                item_index=0,
            )

    def test_duplicate_field_keys_in_group_item_raises(self):
        v1 = ExtractedValueState(
            field_key="outcome",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Pos",
            source_locator="Results table",
        )
        v2 = ExtractedValueState(
            field_key="outcome",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Neg",
            source_locator="Results table",
        )
        with pytest.raises(
            InvalidValueError, match="Duplicate field_key 'outcome' in group item index 1"
        ):
            ExtractedGroupItemState(
                group_key="relationships",
                item_index=1,
                values=[v1, v2],
            )


class TestFieldDefinitionsAndValidation:
    def test_enum_field_definition_requires_allowed_values(self):
        with pytest.raises(
            InvalidTemplateError, match="requires allowed_values unless allow_custom_text is True"
        ):
            ExtractionFieldDefinition(
                field_key="study_design",
                name="Study Design",
                data_type=FieldDataType.ENUM,
            )

    def test_repeating_group_field_definition_requires_group_key(self):
        with pytest.raises(
            InvalidTemplateError, match="must specify group_key"
        ):
            ExtractionFieldDefinition(
                field_key="rel_group",
                name="Relationships",
                data_type=FieldDataType.REPEATING_GROUP,
            )

    def test_min_max_bounds_validation(self):
        with pytest.raises(InvalidTemplateError, match="min_value .* cannot exceed max_value"):
            ExtractionFieldDefinition(
                field_key="score",
                name="Score",
                data_type=FieldDataType.INTEGER,
                min_value=100.0,
                max_value=10.0,
            )

    def test_validate_all_field_data_types(self):
        # 1. TEXT
        f_text = ExtractionFieldDefinition(
            field_key="title",
            name="Title",
            data_type=FieldDataType.TEXT,
            min_length=3,
            max_length=20,
            regex_pattern=r"^[A-Z]",
        )
        assert f_text.validate_value(
            ExtractedValueState(
                field_key="title",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Alpha Study",
                source_locator="Fixture source",
            )
        ) == []
        assert len(f_text.validate_value(
            ExtractedValueState(
                field_key="title",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="al",
                source_locator="Fixture source",
            )
        )) > 0

        # 2. LONG_TEXT
        f_long = ExtractionFieldDefinition(
            field_key="summary", name="Summary", data_type=FieldDataType.LONG_TEXT
        )
        assert f_long.validate_value(
            ExtractedValueState(
                field_key="summary",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Detailed summary text...",
                source_locator="Fixture source",
            )
        ) == []

        # 3. INTEGER
        f_int = ExtractionFieldDefinition(
            field_key="count",
            name="Count",
            data_type=FieldDataType.INTEGER,
            min_value=1,
            max_value=100,
        )
        assert f_int.validate_value(
            ExtractedValueState(
                field_key="count",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                int_value=50,
                source_locator="Fixture source",
            )
        ) == []

        # 4. DECIMAL
        f_dec = ExtractionFieldDefinition(
            field_key="ratio",
            name="Ratio",
            data_type=FieldDataType.DECIMAL,
            min_value=0.0,
            max_value=1.0,
        )
        assert f_dec.validate_value(
            ExtractedValueState(
                field_key="ratio",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                float_value=0.75,
                source_locator="Fixture source",
            )
        ) == []

        # 5. BOOLEAN
        f_bool = ExtractionFieldDefinition(
            field_key="is_randomized", name="Randomized", data_type=FieldDataType.BOOLEAN
        )
        assert f_bool.validate_value(
            ExtractedValueState(
                field_key="is_randomized",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                bool_value=True,
                source_locator="Fixture source",
            )
        ) == []

        # 6. DATE
        f_date = ExtractionFieldDefinition(
            field_key="pub_date", name="Pub Date", data_type=FieldDataType.DATE
        )
        assert f_date.validate_value(
            ExtractedValueState(
                field_key="pub_date",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="2026-08-11",
                source_locator="Fixture source",
            )
        ) == []

        # 7. ENUM
        f_enum = ExtractionFieldDefinition(
            field_key="method",
            name="Method",
            data_type=FieldDataType.ENUM,
            allowed_values=["Case Study", "Survey", "Experiment"],
        )
        assert f_enum.validate_value(
            ExtractedValueState(
                field_key="method",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REVIEWER_CODED,
                text_value="Case Study",
                reviewer_note="Classified by reviewer from the methods description.",
            )
        ) == []

        # 8. MULTI_ENUM
        f_multi = ExtractionFieldDefinition(
            field_key="tags",
            name="Tags",
            data_type=FieldDataType.MULTI_ENUM,
            allowed_values=["tag1", "tag2", "tag3"],
        )
        assert f_multi.validate_value(
            ExtractedValueState(
                field_key="tags",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REVIEWER_CODED,
                json_value=["tag1", "tag2"],
                reviewer_note="Classified by reviewer from the methods description.",
            )
        ) == []

        # 9. IDENTIFIER
        f_id = ExtractionFieldDefinition(
            field_key="doi", name="DOI", data_type=FieldDataType.IDENTIFIER
        )
        assert f_id.validate_value(
            ExtractedValueState(
                field_key="doi",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="10.1000/182",
                source_locator="Fixture source",
            )
        ) == []

        # 10. URL
        f_url = ExtractionFieldDefinition(
            field_key="link", name="Link", data_type=FieldDataType.URL
        )
        assert f_url.validate_value(
            ExtractedValueState(
                field_key="link",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="https://example.com",
                source_locator="Fixture source",
            )
        ) == []

        # 11. NUMBER_WITH_UNIT
        f_num_unit = ExtractionFieldDefinition(
            field_key="effect_size",
            name="Effect Size",
            data_type=FieldDataType.NUMBER_WITH_UNIT,
            allowed_units=["%", "kWh", "GJ"],
            min_value=-100.0,
            max_value=100.0,
        )
        assert f_num_unit.validate_value(
            ExtractedValueState(
                field_key="effect_size",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                float_value=15.5,
                unit_value="kWh",
                source_locator="Fixture source",
            )
        ) == []


class TestExtractionTemplateVersionAndCompleteness:
    def create_sample_template_version(self) -> ExtractionTemplateVersion:
        f_country = ExtractionFieldDefinition(
            field_key="country",
            name="Country",
            data_type=FieldDataType.TEXT,
            is_required=True,
        )
        f_method = ExtractionFieldDefinition(
            field_key="method",
            name="Method",
            data_type=FieldDataType.ENUM,
            allowed_values=["Survey", "Case Study"],
            is_required=True,
            allowed_statuses=[ValueStatus.PRESENT, ValueStatus.NOT_REPORTED],
        )
        g_child_practice = ExtractionFieldDefinition(
            field_key="practice_name",
            name="Practice Name",
            data_type=FieldDataType.TEXT,
            is_required=True,
        )
        g_def = ExtractionRepeatingGroupDefinition(
            group_key="practices",
            name="Practices Group",
            min_items=1,
            max_items=5,
            field_definitions=[g_child_practice],
        )
        return ExtractionTemplateVersion(
            template_id="generic_template",
            version="1.0.0",
            name="Generic Extraction Template",
            publication_fields=[f_country, f_method],
            repeating_groups=[g_def],
        )

    def test_invalid_version_format_raises(self):
        with pytest.raises(InvalidTemplateError, match="must be a valid semver"):
            ExtractionTemplateVersion(
                template_id="t1",
                version="v1.0",
                name="T1",
            )

    def test_template_version_validation_success_and_completeness(self):
        ver = self.create_sample_template_version()

        v_country = ExtractedValueState(
            field_key="country",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REPORTED,
            text_value="Sweden",
            source_locator="Study metadata",
        )
        v_method = ExtractedValueState(
            field_key="method",
            status=ValueStatus.NOT_REPORTED,
        )
        g_item = ExtractedGroupItemState(
            group_key="practices",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="practice_name",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Automation",
                    source_locator="Results table",
                )
            ],
        )

        rev = ExtractionRevision(
            record_id=uuid4(),
            project_id="proj_1",
            publication_id=uuid4(),
            revision_index=1,
            reviewer_id="rev_user1",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            publication_values=[v_country, v_method],
            group_items=[g_item],
        )

        errors = ver.validate_revision(rev)
        assert errors == []
        completeness = ver.compute_completeness(rev)
        assert completeness == ExtractionCompletenessStatus.COMPLETE

    def test_template_version_validation_missing_required_field(self):
        ver = self.create_sample_template_version()

        v_method = ExtractedValueState(
            field_key="method",
            status=ValueStatus.PRESENT,
            origin=ValueOrigin.REVIEWER_CODED,
            text_value="Survey",
            reviewer_note="Classified by reviewer from methods.",
        )
        rev = ExtractionRevision(
            record_id=uuid4(),
            project_id="proj_1",
            publication_id=uuid4(),
            revision_index=1,
            reviewer_id="rev_user1",
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            publication_values=[v_method],
            group_items=[],
        )

        errors = ver.validate_revision(rev)
        assert any("Required publication field 'country' is missing" in e for e in errors)
        assert any("requires at least 1 item(s)" in e for e in errors)
        assert ver.compute_completeness(rev) == ExtractionCompletenessStatus.IN_PROGRESS


class TestExtractionTemplateAggregate:
    def test_template_and_version_management(self):
        ver1 = ExtractionTemplateVersion(
            template_id="tmpl_main",
            version="1.0.0",
            name="Version 1",
        )
        tmpl = ExtractionTemplate(
            template_id="tmpl_main",
            name="Main Template",
            versions=[ver1],
        )
        assert tmpl.get_version("1.0.0").name == "Version 1"

        ver2 = ExtractionTemplateVersion(
            template_id="tmpl_main",
            version="2.0.0",
            name="Version 2",
        )
        tmpl2 = tmpl.add_version(ver2)
        assert len(tmpl2.versions) == 2
        assert tmpl2.get_version("2.0.0").name == "Version 2"

    def test_add_duplicate_version_raises(self):
        ver1 = ExtractionTemplateVersion(
            template_id="tmpl_main",
            version="1.0.0",
            name="Version 1",
        )
        tmpl = ExtractionTemplate(
            template_id="tmpl_main",
            name="Main Template",
            versions=[ver1],
        )
        with pytest.raises(InvalidTemplateError, match="already exists"):
            tmpl.add_version(ver1)


class TestExtractionRevisionAndRecord:
    def test_valid_revision(self):
        rec_id = uuid4()
        pub_id = uuid4()
        rev = ExtractionRevision(
            record_id=rec_id,
            project_id="proj_alpha",
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer_42",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
        )
        assert rev.record_id == rec_id
        assert rev.revision_index == 1
        assert rev.reviewer_id == "reviewer_42"

    def test_invalid_reviewer_id_raises(self):
        with pytest.raises(InvalidRevisionError, match="reviewer_id must be a non-empty string"):
            ExtractionRevision(
                record_id=uuid4(),
                project_id="proj_alpha",
                publication_id=uuid4(),
                revision_index=1,
                reviewer_id="   ",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            )

    def test_revision_rejects_not_started_completeness_status(self):
        with pytest.raises(InvalidRevisionError, match="cannot be not_started"):
            ExtractionRevision(
                record_id=uuid4(),
                project_id="proj_alpha",
                publication_id=uuid4(),
                revision_index=1,
                reviewer_id="reviewer_42",
                completeness_status=ExtractionCompletenessStatus.NOT_STARTED,
            )

    def test_valid_extraction_record(self):
        pub_id = uuid4()
        rec = ExtractionRecord(
            project_id="proj_alpha",
            publication_id=pub_id,
            template_id="tmpl_main",
            template_version="1.0.0",
        )
        assert rec.project_id == "proj_alpha"
        assert rec.publication_id == pub_id
        assert rec.current_status == ExtractionCompletenessStatus.NOT_STARTED
