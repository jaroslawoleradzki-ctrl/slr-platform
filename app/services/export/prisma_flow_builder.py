"""Pure transformation service for building PRISMA 2020 flow models (v0.6.1 Slice 3).

Transforms authoritative PrismaMetrics into a presentation-neutral PrismaFlowModel.
Adds derived display figures (duplicates_removed, stage exclusions) and PRISMA 2020
band structure without modifying persisted metrics or embedding coordinates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.version import get_app_version
from app.domain.prisma_flow import (
    PrismaFlowEdge,
    PrismaFlowMetadata,
    PrismaFlowModel,
    PrismaFlowNode,
)

if TYPE_CHECKING:
    from app.domain.project import Project
    from app.services.prisma_metrics_service import PrismaMetrics


def build_flow_model(
    metrics: PrismaMetrics,
    project: Project | None = None,
    *,
    generated_at: datetime | None = None,
) -> PrismaFlowModel:
    """Transform authoritative PRISMA metrics into a presentation-neutral flow model."""
    now = generated_at or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    project_title = project.title if project is not None else f"Project {metrics.project_id}"
    protocol_version = project.protocol_version if project is not None else None

    # Presentation-level derived figures (plan §12, §13, D7)
    duplicates_removed = max(0, metrics.records_before_dedup - metrics.records_after_technical_merger)
    excluded_title_abstract = max(0, metrics.records_screened_title_abstract - metrics.records_screened_full_text)
    excluded_full_text = max(0, metrics.records_screened_full_text - metrics.studies_included_synthesis)

    removed = {
        "duplicates_removed": duplicates_removed,
        "excluded_title_abstract": excluded_title_abstract,
        "excluded_full_text": excluded_full_text,
    }

    annotations_other: dict[str, str] = {
        k: str(v) for k, v in sorted(metrics.manual_source_breakdown.items())
    }

    annotations_removed: dict[str, str] = {}
    if metrics.duplicate_groups_pending_review > 0:
        annotations_removed["pending_review"] = str(metrics.duplicate_groups_pending_review)

    nodes: list[PrismaFlowNode] = [
        PrismaFlowNode(
            node_id="identification.databases",
            stage="identification",
            label_key="prisma.identification.databases",
            values={"count": metrics.records_identified_providers},
        ),
        PrismaFlowNode(
            node_id="identification.other_methods",
            stage="identification",
            label_key="prisma.identification.other_methods",
            values={"count": metrics.records_identified_imports},
            annotations=annotations_other,
        ),
        PrismaFlowNode(
            node_id="identification.records_removed",
            stage="identification",
            label_key="prisma.identification.records_removed",
            values={"duplicates_removed": duplicates_removed},
            annotations=annotations_removed,
        ),
        PrismaFlowNode(
            node_id="identification.after_deduplication",
            stage="identification",
            label_key="prisma.identification.after_deduplication",
            values={"count": metrics.records_after_technical_merger},
        ),
        PrismaFlowNode(
            node_id="screening.title_abstract",
            stage="screening_tasft",
            label_key="prisma.screening.title_abstract",
            values={"count": metrics.records_screened_title_abstract},
        ),
        PrismaFlowNode(
            node_id="screening.excluded_title_abstract",
            stage="screening_tasft",
            label_key="prisma.screening.excluded_title_abstract",
            values={"count": excluded_title_abstract},
        ),
        PrismaFlowNode(
            node_id="screening.full_text",
            stage="screening_tasft",
            label_key="prisma.screening.full_text",
            values={"count": metrics.records_screened_full_text},
        ),
        PrismaFlowNode(
            node_id="screening.excluded_full_text",
            stage="screening_tasft",
            label_key="prisma.screening.excluded_full_text",
            values={"count": excluded_full_text},
        ),
        PrismaFlowNode(
            node_id="included.synthesis",
            stage="included",
            label_key="prisma.included.synthesis",
            values={"count": metrics.studies_included_synthesis},
        ),
    ]

    edges: list[PrismaFlowEdge] = [
        PrismaFlowEdge(from_node="identification.databases", to_node="identification.after_deduplication"),
        PrismaFlowEdge(from_node="identification.other_methods", to_node="identification.after_deduplication"),
        PrismaFlowEdge(from_node="identification.after_deduplication", to_node="identification.records_removed"),
        PrismaFlowEdge(from_node="identification.after_deduplication", to_node="screening.title_abstract"),
        PrismaFlowEdge(from_node="screening.title_abstract", to_node="screening.excluded_title_abstract"),
        PrismaFlowEdge(from_node="screening.title_abstract", to_node="screening.full_text"),
        PrismaFlowEdge(from_node="screening.full_text", to_node="screening.excluded_full_text"),
        PrismaFlowEdge(from_node="screening.full_text", to_node="included.synthesis"),
    ]

    counts_echo: dict[str, int] = {
        "records_identified_providers": metrics.records_identified_providers,
        "records_identified_imports": metrics.records_identified_imports,
        "total_identified": metrics.total_identified,
        "records_after_normalization": metrics.records_after_normalization,
        "records_before_dedup": metrics.records_before_dedup,
        "records_after_technical_merger": metrics.records_after_technical_merger,
        "duplicate_groups_pending_review": metrics.duplicate_groups_pending_review,
        "records_screened_title_abstract": metrics.records_screened_title_abstract,
        "records_screened_full_text": metrics.records_screened_full_text,
        "studies_included_synthesis": metrics.studies_included_synthesis,
    }

    metadata = PrismaFlowMetadata(
        project_id=metrics.project_id,
        project_title=project_title,
        protocol_version=protocol_version,
        application_version=get_app_version(),
        generated_at=now_iso,
        counts_echo=counts_echo,
    )

    return PrismaFlowModel(
        project_id=metrics.project_id,
        metadata=metadata,
        nodes=nodes,
        edges=edges,
        removed=removed,
    )
