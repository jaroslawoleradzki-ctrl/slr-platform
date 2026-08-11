from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.repositories.project_repository import ProjectRepository, default_project_repository
from app.repositories.quality_assessment_repository import (
    ProjectQualityAssessmentConfigurationRepository,
    QualityAssessmentCatalogRepository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    default_project_quality_assessment_configuration_repository,
    default_quality_assessment_catalog_repository,
)

CASP_INSPIRED_TOOL_ID = "casp_inspired"
LEAN_ENERGY_TEMPLATE_ID = UUID("e2e85001-8501-4b11-9a22-000000000001")
LEAN_ENERGY_TEMPLATE_KEY = "lean_energy"

LEAN_ENERGY_CRITERIA_SPECS = [
    (
        UUID("e2e85001-8501-4b11-9a22-000000000011"),
        1,
        "Czy cel lub pytanie badawcze zostały jasno określone?",
        "YES: Cel lub pytanie badawcze zostały jednoznacznie sformułowane. CANNOT_DETERMINE: Brak jasnego sformułowania. NO: Brak celu lub sprzeczne założenia.",
    ),
    (
        UUID("e2e85001-8501-4b11-9a22-000000000012"),
        2,
        "Czy zastosowana metoda badawcza jest adekwatna do celu badania i została wystarczająco opisana?",
        "YES: Opis metody pozwala zrozumieć przebieg badania i jest właściwy. CANNOT_DETERMINE: Pobieżny opis metody. NO: Nieadekwatna metoda lub brak opisu.",
    ),
    (
        UUID("e2e85001-8501-4b11-9a22-000000000013"),
        3,
        "Czy sposób pozyskania oraz analizy danych został opisany w sposób umożliwiający ocenę wiarygodności badania?",
        "YES: Opisana próba, źródła danych oraz metody analizy. CANNOT_DETERMINE: Niepełny opis danych lub metody. NO: Brak opisu pozyskania/analizy.",
    ),
    (
        UUID("e2e85001-8501-4b11-9a22-000000000014"),
        4,
        "Czy zastosowane praktyki, narzędzia lub rozwiązania Lean Management zostały jednoznacznie zidentyfikowane i opisane?",
        "YES: Wskazano konkretne narzędzia Lean (np. 5S, VSM, TPM, Kaizen, Kanban, JIT). CANNOT_DETERMINE: Ogólne powoływanie się na Lean. NO: Brak identyfikacji praktyk Lean.",
    ),
    (
        UUID("e2e85001-8501-4b11-9a22-000000000015"),
        5,
        "Czy sposób pomiaru zużycia energii, efektywności energetycznej lub innych analizowanych efektów energetycznych został jasno określony?",
        "YES: Wskazano wskaźniki (np. SEC, kWh, emisje) lub sposób pomiaru zużycia energii. CANNOT_DETERMINE: Brak precyzyjnych wskaźników energetycznych. NO: Brak pomiaru efektów energetycznych.",
    ),
    (
        UUID("e2e85001-8501-4b11-9a22-000000000016"),
        6,
        "Czy przedstawione dane pozwalają ocenić związek pomiędzy Lean Management a obserwowanym efektem energetycznym?",
        "YES: Dane empiryczne lub jakościowe pokazują wpływ Lean na energię. CANNOT_DETERMINE: Oba aspekty opisane rozdzielnie bez wykazania związku. NO: Brak powiązania.",
    ),
    (
        UUID("e2e85001-8501-4b11-9a22-000000000017"),
        7,
        "Czy wnioski autorów znajdują uzasadnienie w przedstawionych wynikach oraz czy wskazano istotne ograniczenia badania?",
        "YES: Wnioski wynikają bezpośrednio z wyników i omówiono ograniczenia. CANNOT_DETERMINE: Wnioski wykraczają poza wyniki lub brak ograniczeń. NO: Nieuzasadnione wnioski.",
    ),
]


class ToolNotFoundError(Exception):
    def __init__(self, tool_id: str) -> None:
        self.tool_id = tool_id
        super().__init__(f"Quality assessment tool '{tool_id}' not found.")


class TemplateVersionNotFoundError(Exception):
    def __init__(self, template_id: UUID | str) -> None:
        self.template_id = str(template_id)
        super().__init__(f"Quality assessment template '{self.template_id}' not found.")


class InactiveToolSelectionError(Exception):
    def __init__(self, tool_id: str) -> None:
        self.tool_id = tool_id
        super().__init__(f"Quality assessment tool '{tool_id}' is inactive and cannot be selected.")


class InactiveTemplateSelectionError(Exception):
    def __init__(self, template_id: UUID | str) -> None:
        self.template_id = str(template_id)
        super().__init__(f"Quality assessment template '{self.template_id}' is inactive and cannot be selected.")


class CrossToolTemplateMismatchError(Exception):
    def __init__(self, tool_id: str, template_tool_id: str) -> None:
        self.tool_id = tool_id
        self.template_tool_id = template_tool_id
        super().__init__(
            f"Template belonging to tool '{template_tool_id}' cannot be configured for selected tool '{tool_id}'."
        )


class SeedCatalogConflictError(Exception):
    def __init__(self, item_id: str, reason: str) -> None:
        self.item_id = item_id
        self.reason = reason
        super().__init__(f"Seed catalog conflict for '{item_id}': {reason}")


@runtime_checkable
class QualityAssessmentConfigurationService(Protocol):
    """Service for managing global Quality Assessment catalog and project-scoped configurations."""

    def seed_built_in_catalog(self) -> None: ...

    def list_tools(self, is_active_only: bool = True) -> list[QualityAssessmentTool]: ...

    def get_tool(self, tool_id: str) -> QualityAssessmentTool: ...

    def list_templates_for_tool(
        self, tool_id: str, is_active_only: bool = True
    ) -> list[QualityAssessmentTemplate]: ...

    def get_template_version(self, template_id: UUID) -> QualityAssessmentTemplate: ...

    def get_project_configuration(
        self, project_id: str
    ) -> ProjectQualityAssessmentConfiguration | None: ...

    def configure_project(
        self, project_id: str, tool_id: str, template_id: UUID, confirm_template_change: bool = False
    ) -> ProjectQualityAssessmentConfiguration: ...


class DefaultQualityAssessmentConfigurationService:
    def __init__(
        self,
        catalog_repo: QualityAssessmentCatalogRepository | None = None,
        config_repo: ProjectQualityAssessmentConfigurationRepository | None = None,
        project_repo: ProjectRepository | None = None,
    ) -> None:
        self._catalog_repo = catalog_repo or default_quality_assessment_catalog_repository()
        self._config_repo = (
            config_repo or default_project_quality_assessment_configuration_repository()
        )
        self._project_repo = project_repo or default_project_repository()

    def seed_built_in_catalog(self) -> None:
        """Idempotent seed for built-in catalog tools (casp_inspired) and production Lean Energy QA v1 template.

        If tool or template exists with different content, raises SeedCatalogConflictError.
        """
        existing_tool = self._catalog_repo.get_tool(CASP_INSPIRED_TOOL_ID)
        casp_tool = QualityAssessmentTool(
            tool_id=CASP_INSPIRED_TOOL_ID,
            name="CASP-inspired Quality Assessment",
            description="Methodological quality appraisal tools adapted from critical appraisal principles for systematic literature reviews.",
            is_active=True,
        )
        if existing_tool is None:
            self._catalog_repo.create_tool(casp_tool)
        else:
            if existing_tool.name != casp_tool.name:
                raise SeedCatalogConflictError(
                    CASP_INSPIRED_TOOL_ID,
                    f"Existing tool name '{existing_tool.name}' conflicts with seed tool name '{casp_tool.name}'",
                )

        # Seed production template: Lean Energy Quality Assessment v1
        lean_energy_criteria = [
            QualityAssessmentTemplateCriterion(
                criterion_id=c_id,
                template_id=LEAN_ENERGY_TEMPLATE_ID,
                display_order=order,
                question=q,
                guidance=g,
                is_required=True,
            )
            for c_id, order, q, g in LEAN_ENERGY_CRITERIA_SPECS
        ]

        lean_energy_template = QualityAssessmentTemplate(
            template_id=LEAN_ENERGY_TEMPLATE_ID,
            tool_id=CASP_INSPIRED_TOOL_ID,
            template_key=LEAN_ENERGY_TEMPLATE_KEY,
            name="Lean Energy Quality Assessment",
            version=1,
            description="Quality assessment template adapted for the systematic review of Lean Management and energy efficiency in manufacturing enterprises.",
            is_active=True,
            criteria=lean_energy_criteria,
        )

        existing_template = self._catalog_repo.get_template_version_by_key(
            CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_KEY, 1
        )
        if existing_template is None:
            self._catalog_repo.create_template_version(lean_energy_template)
        else:
            # Verify immutable content equality
            if (
                existing_template.name != lean_energy_template.name
                or existing_template.description != lean_energy_template.description
                or len(existing_template.criteria) != len(lean_energy_template.criteria)
            ):
                raise SeedCatalogConflictError(
                    f"{CASP_INSPIRED_TOOL_ID}/{LEAN_ENERGY_TEMPLATE_KEY}/v1",
                    "Existing template content conflicts with seed template definition",
                )
            for e_crit, s_crit in zip(existing_template.criteria, lean_energy_template.criteria, strict=True):
                if (
                    e_crit.question != s_crit.question
                    or e_crit.guidance != s_crit.guidance
                    or e_crit.display_order != s_crit.display_order
                    or e_crit.is_required != s_crit.is_required
                ):
                    raise SeedCatalogConflictError(
                        f"{CASP_INSPIRED_TOOL_ID}/{LEAN_ENERGY_TEMPLATE_KEY}/v1",
                        f"Criterion '{e_crit.criterion_id}' content conflicts with seed criterion definition",
                    )

    def list_tools(self, is_active_only: bool = True) -> list[QualityAssessmentTool]:
        tools = self._catalog_repo.list_tools()
        if is_active_only:
            return [t for t in tools if t.is_active]
        return tools

    def get_tool(self, tool_id: str) -> QualityAssessmentTool:
        tool = self._catalog_repo.get_tool(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id)
        return tool

    def list_templates_for_tool(
        self, tool_id: str, is_active_only: bool = True
    ) -> list[QualityAssessmentTemplate]:
        # Ensure tool exists
        _ = self.get_tool(tool_id)
        return self._catalog_repo.list_template_versions(
            tool_id=tool_id, is_active_only=is_active_only
        )

    def get_template_version(self, template_id: UUID) -> QualityAssessmentTemplate:
        template = self._catalog_repo.get_template_version(template_id)
        if template is None:
            raise TemplateVersionNotFoundError(template_id)
        return template

    def get_project_configuration(
        self, project_id: str
    ) -> ProjectQualityAssessmentConfiguration | None:
        # Verify project existence
        _ = self._project_repo.get(project_id)
        return self._config_repo.get_configuration(project_id)

    def configure_project(
        self, project_id: str, tool_id: str, template_id: UUID, confirm_template_change: bool = False
    ) -> ProjectQualityAssessmentConfiguration:
        # 1. Verify project exists
        _ = self._project_repo.get(project_id)

        # 2. Verify tool exists & is active
        tool = self._catalog_repo.get_tool(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id)

        # 3. Verify template exists
        template = self._catalog_repo.get_template_version(template_id)
        if template is None:
            raise TemplateVersionNotFoundError(template_id)

        # 4. Authoritative check: Template MUST belong to selected tool_id
        if template.tool_id != tool_id:
            raise CrossToolTemplateMismatchError(tool_id, template.tool_id)

        # 5. Check if project already has configuration
        existing_config = self._config_repo.get_configuration(project_id)

        # For NEW configuration (or changing from a previous configuration), enforce active status
        if existing_config is None or existing_config.template_id != template_id:
            if not tool.is_active:
                raise InactiveToolSelectionError(tool_id)
            if not template.is_active:
                raise InactiveTemplateSelectionError(template_id)

        now = datetime.now(timezone.utc)
        configured_at = existing_config.configured_at if existing_config is not None else now

        new_config = ProjectQualityAssessmentConfiguration(
            project_id=project_id,
            tool_id=tool_id,
            template_id=template_id,
            configured_at=configured_at,
            updated_at=now,
        )
        return self._config_repo.save_configuration(new_config)


def default_quality_assessment_configuration_service() -> (
    DefaultQualityAssessmentConfigurationService
):
    return DefaultQualityAssessmentConfigurationService()
