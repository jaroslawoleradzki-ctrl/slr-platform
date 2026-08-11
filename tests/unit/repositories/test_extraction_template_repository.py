import pytest

from app.domain.extraction import (
    ExtractionFieldDefinition,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    FieldDataType,
)
from app.repositories.extraction_template_repository import (
    ExtractionTemplateConflictError,
    ExtractionTemplateNotFoundError,
    SqliteExtractionTemplateRepository,
)


@pytest.fixture
def repository(tmp_path):
    return SqliteExtractionTemplateRepository(tmp_path / "extraction-templates.db")


def template(template_id: str = "generic") -> ExtractionTemplate:
    return ExtractionTemplate(template_id=template_id, name="Generic extraction", description="A generic catalog entry")


def version(template_id: str = "generic", value: str = "1.0.0", *, active: bool = True, published: bool = True):
    return ExtractionTemplateVersion(
        template_id=template_id,
        version=value,
        name=f"Generic {value}",
        is_active=active,
        is_published=published,
        publication_fields=[
            ExtractionFieldDefinition(field_key="title", name="Title", data_type=FieldDataType.TEXT),
        ],
    )


def test_register_read_and_hydrate_template_versions(repository):
    repository.register_template(template())
    v1 = version()
    repository.register_version(v1)

    restored = repository.get_template("generic")
    assert restored.name == "Generic extraction"
    assert restored.versions == [v1]
    assert repository.get_version("generic", "1.0.0") == v1


def test_duplicate_template_and_version_are_immutable_conflicts(repository):
    repository.register_template(template())
    repository.register_version(version())
    with pytest.raises(ExtractionTemplateConflictError, match="already exists"):
        repository.register_template(template())
    with pytest.raises(ExtractionTemplateConflictError, match="immutable"):
        repository.register_version(version())


def test_list_only_active_published_versions_in_deterministic_order(repository):
    repository.register_template(template("zeta"))
    repository.register_template(template("alpha"))
    repository.register_version(version("zeta", "1.0.0"))
    repository.register_version(version("alpha", "2.0.0"))
    repository.register_version(version("alpha", "1.0.0", active=False))
    repository.register_version(version("zeta", "2.0.0", published=False))

    assert [(item.template_id, item.version) for item in repository.list_active_published_versions()] == [
        ("alpha", "2.0.0"),
        ("zeta", "1.0.0"),
    ]


def test_missing_template_or_version_raises(repository):
    with pytest.raises(ExtractionTemplateNotFoundError):
        repository.get_template("missing")
    repository.register_template(template())
    with pytest.raises(ExtractionTemplateNotFoundError):
        repository.get_version("generic", "9.9.9")
