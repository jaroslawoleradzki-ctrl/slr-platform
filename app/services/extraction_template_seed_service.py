"""Service for seeding production extraction templates into the template catalog (Phase 9.7).

This service is completely domain-agnostic and provides idempotent seeding of the
Lean Energy Extraction v1.0.0 template definition (E1–E14) into the catalog.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.extraction import (
    ExtractionFieldDefinition,
    ExtractionRepeatingGroupDefinition,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    FieldDataType,
)
from app.repositories.extraction_template_repository import (
    ExtractionTemplateConflictError,
    ExtractionTemplateNotFoundError,
    SqliteExtractionTemplateRepository,
    default_extraction_template_repository,
)

LEAN_ENERGY_TEMPLATE_ID = "lean_energy"
LEAN_ENERGY_VERSION = "1.0.0"


def get_lean_energy_v1_template_version() -> ExtractionTemplateVersion:
    """Returns the immutable schema definition of Lean Energy Extraction v1.0.0 (E1–E14)."""
    now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    publication_fields = [
        ExtractionFieldDefinition(
            field_key="study_country_industry",
            name="Kontekst badania: Kraj i Branża (E2)",
            data_type=FieldDataType.TEXT,
            description="Kraj, region oraz sektor przemysłowy lub fabryka (E2 Study Context)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="study_design",
            name="Typ badania i metodologia (E3)",
            data_type=FieldDataType.ENUM,
            description="Wiodąca metodologia badawcza przyjęta w pracy (E3 Study Type & Method)",
            is_required=True,
            allowed_values=[
                "Empirical / Field Experiment",
                "Case Study",
                "Survey / Cross-Sectional",
                "Simulation / Modeling",
                "Action Research",
                "Conceptual / Literature Review",
                "Other",
            ],
        ),
        ExtractionFieldDefinition(
            field_key="main_conclusions",
            name="Główne wnioski z badania (E12)",
            data_type=FieldDataType.LONG_TEXT,
            description="Syntetyczne podsumowanie najważniejszych ustaleń autorów pracy (E12 Main Conclusions)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="study_limitations",
            name="Ograniczenia badania (E13)",
            data_type=FieldDataType.LONG_TEXT,
            description="Ograniczenia metodologiczne i próby podane przez autorów (E13 Study Limitations)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="research_gaps",
            name="Luki badawcze i kierunki dalszych prac (E14)",
            data_type=FieldDataType.LONG_TEXT,
            description="Wskazane przez autorów luki w wiedzy oraz rekomendacje dla przyszłych badań (E14 Research Gaps)",
            is_required=False,
        ),
    ]

    relationship_fields = [
        ExtractionFieldDefinition(
            field_key="lean_practice",
            name="Praktyka / Narzędzie Lean Management (E4)",
            data_type=FieldDataType.ENUM,
            description="Praktyka lub metoda Lean powiązana z opisanym skutkiem energetycznym (E4 Lean Practice / Tool)",
            is_required=True,
            allowed_values=[
                "5S",
                "TPM (Total Productive Maintenance)",
                "VSM (Value Stream Mapping)",
                "SMED (Single-Minute Exchange of Die)",
                "Kaizen / Continuous Improvement",
                "Standardized Work",
                "Just-In-Time (JIT) / Kanban",
                "Jidoka / Autonomation",
                "Poka-Yoke",
                "OEE Optimization",
                "Other Lean Practice",
            ],
            allow_custom_text=True,
        ),
        ExtractionFieldDefinition(
            field_key="application_scope",
            name="Zakres i poziom wdrożenia Lean (E5)",
            data_type=FieldDataType.TEXT,
            description="Poziom aplikacji praktyki Lean (np. stanowisko, linia, cały zakład, łańcuch dostaw) (E5 Lean Scope)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="energy_effect_indicator",
            name="Wskaźnik / Efekt Energetyczny (E6)",
            data_type=FieldDataType.ENUM,
            description="Mierzony lub opisany parametr efektywności energetycznej (E6 Energy Effect / Indicator)",
            is_required=True,
            allowed_values=[
                "Electricity Consumption",
                "Natural Gas / Fuel Usage",
                "Peak Power Demand",
                "Thermal / Heat Loss",
                "CO2 / Carbon Footprint",
                "Specific Energy Consumption (SEC)",
                "Standby / Idle Energy",
                "Other Energy Indicator",
            ],
        ),
        ExtractionFieldDefinition(
            field_key="measurement_method",
            name="Metoda pomiaru i jednostki (E7)",
            data_type=FieldDataType.TEXT,
            description="Metoda zbierania danych energetycznych (np. sub-metering, rachunki, symulacja) (E7 Measurement Method)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="effect_magnitude",
            name="Wielkość i kierunek efektu energetycznego (E8)",
            data_type=FieldDataType.NUMBER_WITH_UNIT,
            description="Wartość i jednostka określająca zmianę zużycia energii (np. -15 %, -250 kWh/dobę) (E8 Effect Magnitude)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="evidence_character",
            name="Charakter dowodu empirycznego (E9)",
            data_type=FieldDataType.ENUM,
            description="Siła i charakter powiązania Lean-Energy zaraportowane w artykule (E9 Evidence Character)",
            is_required=True,
            allowed_values=[
                "Empirically Demonstrated",
                "Quantitatively Measured",
                "Qualitatively Described",
                "Estimated / Modeled",
                "Postulated / Theoretical",
                "Unstated / Unclear",
            ],
        ),
        ExtractionFieldDefinition(
            field_key="impact_mechanism",
            name="Mechanizm wpływu Lean–Energy (E10)",
            data_type=FieldDataType.LONG_TEXT,
            description="Opis ścieżki przyczynowo-skutkowej łączącej wdrożenie Lean ze zmianą zużycia energii (E10 Mechanism)",
            is_required=False,
        ),
        ExtractionFieldDefinition(
            field_key="moderating_conditions",
            name="Czynniki kontekstowe i moderujące (E11)",
            data_type=FieldDataType.LONG_TEXT,
            description="Warunki organizacyjne, technologiczne lub zarządcze wpływające na relację Lean–Energy (E11 Moderating Factors)",
            is_required=False,
        ),
    ]

    repeating_group = ExtractionRepeatingGroupDefinition(
        group_key="lean_energy_relationships",
        name="Relacje Lean Management – Efektywność Energetyczna (E4–E11)",
        description="Poszczególne zaobserwowane powiązania między praktyką Lean a efektem energetycznym w badaniu",
        min_items=1,
        max_items=None,
        field_definitions=relationship_fields,
    )

    return ExtractionTemplateVersion(
        template_id=LEAN_ENERGY_TEMPLATE_ID,
        version=LEAN_ENERGY_VERSION,
        name="Lean Energy Data Extraction",
        description="Protokół ekstrakcji danych Lean Management & Energy Efficiency (E1–E14)",
        is_published=True,
        is_active=True,
        publication_fields=publication_fields,
        repeating_groups=[repeating_group],
        created_at=now,
    )


class ExtractionTemplateSeedService:
    """Service for idempotently registering system seed extraction templates."""

    def __init__(
        self,
        template_repo: SqliteExtractionTemplateRepository | None = None,
    ) -> None:
        self._template_repo = template_repo or default_extraction_template_repository()

    def seed_lean_energy_v1(self) -> ExtractionTemplateVersion:
        """Idempotently seeds Lean Energy Extraction v1.0.0 into the template catalog repository.

        Rules:
        - Creates template header if missing.
        - Returns existing published version if version 1.0.0 exists with identical schema.
        - Fails loudly (ExtractionTemplateConflictError) if existing version 1.0.0 conflicts structurally.
        - Never mutates an existing published version.
        """
        target_version = get_lean_energy_v1_template_version()

        # 1. Register base template header if missing
        try:
            self._template_repo.get_template(LEAN_ENERGY_TEMPLATE_ID)
        except ExtractionTemplateNotFoundError:
            self._template_repo.register_template(
                ExtractionTemplate(
                    template_id=LEAN_ENERGY_TEMPLATE_ID,
                    name=target_version.name,
                    description=target_version.description,
                    created_at=target_version.created_at,
                )
            )

        # 2. Check if version already exists
        try:
            existing = self._template_repo.get_version(LEAN_ENERGY_TEMPLATE_ID, LEAN_ENERGY_VERSION)
            # Idempotency check: verify schema match
            target_dump = target_version.model_dump(mode="json")
            existing_dump = existing.model_dump(mode="json")
            if target_dump != existing_dump:
                raise ExtractionTemplateConflictError(
                    f"Template version '{LEAN_ENERGY_TEMPLATE_ID}' v{LEAN_ENERGY_VERSION} already exists with a different schema."
                )
            return existing
        except ExtractionTemplateNotFoundError:
            # Not found: register version cleanly
            return self._template_repo.register_version(target_version)


def seed_lean_energy_v1_template(
    template_repo: SqliteExtractionTemplateRepository | None = None,
) -> ExtractionTemplateVersion:
    service = ExtractionTemplateSeedService(template_repo=template_repo)
    return service.seed_lean_energy_v1()
