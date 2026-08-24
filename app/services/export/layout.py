"""Shared layout geometry and styling definitions for PRISMA 2020 renderers (v0.6.1 Slice 3/4).

Maintains a single authoritative geometry table shared across SVG and PDF renderers.
Ensures identical dimensions, stage bands, and box coordinates across export formats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.prisma_flow import PrismaFlowModel


CANVAS_WIDTH = 860.0
CANVAS_HEIGHT = 980.0

COLOR_BG = "#FFFFFF"
COLOR_TEXT_PRIMARY = "#1E293B"
COLOR_TEXT_SECONDARY = "#475569"
COLOR_TEXT_MUTED = "#64748B"
COLOR_BORDER = "#CBD5E1"
COLOR_BOX_FILL = "#F8FAFC"
COLOR_SIDE_BOX_FILL = "#F1F5F9"
COLOR_ARROW = "#475569"

COLOR_STAGE_IDENTIFICATION = "#E0F2FE"
COLOR_STAGE_IDENTIFICATION_BORDER = "#7DD3FC"
COLOR_STAGE_IDENTIFICATION_TEXT = "#0369A1"

COLOR_STAGE_SCREENING = "#FEF3C7"
COLOR_STAGE_SCREENING_BORDER = "#FCD34D"
COLOR_STAGE_SCREENING_TEXT = "#B45309"

COLOR_STAGE_INCLUDED = "#DCFCE7"
COLOR_STAGE_INCLUDED_BORDER = "#86EFAC"
COLOR_STAGE_INCLUDED_TEXT = "#15803D"


@dataclass(frozen=True, slots=True)
class StageBandLayout:
    stage_key: str
    label: str
    x: float
    y: float
    width: float
    height: float
    fill_color: str
    border_color: str
    text_color: str


@dataclass(frozen=True, slots=True)
class NodeBoxLayout:
    node_id: str
    x: float
    y: float
    width: float
    height: float
    is_side_box: bool = False


@dataclass(frozen=True, slots=True)
class NodeBoxContent:
    node_id: str
    title: str
    lines: tuple[str, ...]
    is_side_box: bool = False


@dataclass(frozen=True, slots=True)
class ArrowConnector:
    from_x: float
    from_y: float
    to_x: float
    to_y: float


STAGE_BANDS: tuple[StageBandLayout, ...] = (
    StageBandLayout(
        stage_key="identification",
        label="Identification",
        x=20.0,
        y=60.0,
        width=110.0,
        height=260.0,
        fill_color=COLOR_STAGE_IDENTIFICATION,
        border_color=COLOR_STAGE_IDENTIFICATION_BORDER,
        text_color=COLOR_STAGE_IDENTIFICATION_TEXT,
    ),
    StageBandLayout(
        stage_key="screening_tasft",
        label="Screening",
        x=20.0,
        y=340.0,
        width=110.0,
        height=400.0,
        fill_color=COLOR_STAGE_SCREENING,
        border_color=COLOR_STAGE_SCREENING_BORDER,
        text_color=COLOR_STAGE_SCREENING_TEXT,
    ),
    StageBandLayout(
        stage_key="included",
        label="Included",
        x=20.0,
        y=760.0,
        width=110.0,
        height=180.0,
        fill_color=COLOR_STAGE_INCLUDED,
        border_color=COLOR_STAGE_INCLUDED_BORDER,
        text_color=COLOR_STAGE_INCLUDED_TEXT,
    ),
)


NODE_LAYOUTS: dict[str, NodeBoxLayout] = {
    "identification.databases": NodeBoxLayout(
        node_id="identification.databases",
        x=150.0,
        y=60.0,
        width=330.0,
        height=100.0,
    ),
    "identification.other_methods": NodeBoxLayout(
        node_id="identification.other_methods",
        x=500.0,
        y=60.0,
        width=340.0,
        height=100.0,
    ),
    "identification.after_deduplication": NodeBoxLayout(
        node_id="identification.after_deduplication",
        x=150.0,
        y=200.0,
        width=330.0,
        height=90.0,
    ),
    "identification.records_removed": NodeBoxLayout(
        node_id="identification.records_removed",
        x=500.0,
        y=200.0,
        width=340.0,
        height=90.0,
        is_side_box=True,
    ),
    "screening.title_abstract": NodeBoxLayout(
        node_id="screening.title_abstract",
        x=150.0,
        y=360.0,
        width=330.0,
        height=90.0,
    ),
    "screening.excluded_title_abstract": NodeBoxLayout(
        node_id="screening.excluded_title_abstract",
        x=500.0,
        y=360.0,
        width=340.0,
        height=90.0,
        is_side_box=True,
    ),
    "screening.full_text": NodeBoxLayout(
        node_id="screening.full_text",
        x=150.0,
        y=520.0,
        width=330.0,
        height=90.0,
    ),
    "screening.excluded_full_text": NodeBoxLayout(
        node_id="screening.excluded_full_text",
        x=500.0,
        y=520.0,
        width=340.0,
        height=90.0,
        is_side_box=True,
    ),
    "included.synthesis": NodeBoxLayout(
        node_id="included.synthesis",
        x=150.0,
        y=800.0,
        width=330.0,
        height=90.0,
    ),
}


ARROWS: tuple[ArrowConnector, ...] = (
    # Identification: Databases -> After Deduplication
    ArrowConnector(from_x=315.0, from_y=160.0, to_x=315.0, to_y=200.0),
    # Identification: Other Methods -> After Deduplication (horizontal entry from right)
    ArrowConnector(from_x=670.0, from_y=160.0, to_x=480.0, to_y=230.0),
    # Identification: After Deduplication -> Records Removed (side box)
    ArrowConnector(from_x=480.0, from_y=245.0, to_x=500.0, to_y=245.0),
    # Identification -> Screening: After Deduplication -> Title & Abstract Screening
    ArrowConnector(from_x=315.0, from_y=290.0, to_x=315.0, to_y=360.0),
    # Screening: Title & Abstract -> Excluded Title & Abstract (side box)
    ArrowConnector(from_x=480.0, from_y=405.0, to_x=500.0, to_y=405.0),
    # Screening: Title & Abstract -> Full-Text Screening
    ArrowConnector(from_x=315.0, from_y=450.0, to_x=315.0, to_y=520.0),
    # Screening: Full-Text -> Excluded Full-Text (side box)
    ArrowConnector(from_x=480.0, from_y=565.0, to_x=500.0, to_y=565.0),
    # Screening -> Included: Full-Text -> Included in Synthesis
    ArrowConnector(from_x=315.0, from_y=610.0, to_x=315.0, to_y=800.0),
)


def extract_node_contents(model: PrismaFlowModel) -> dict[str, NodeBoxContent]:
    """Map flow model nodes to structured presentation contents."""
    node_map = {n.node_id: n for n in model.nodes}
    result: dict[str, NodeBoxContent] = {}

    # 1. Databases
    db_node = node_map.get("identification.databases")
    db_count = db_node.values.get("count", 0) if db_node else 0
    result["identification.databases"] = NodeBoxContent(
        node_id="identification.databases",
        title="Records identified from databases & registers",
        lines=(f"Database records (n = {db_count})",),
    )

    # 2. Other methods
    other_node = node_map.get("identification.other_methods")
    other_count = other_node.values.get("count", 0) if other_node else 0
    other_lines: list[str] = [f"Manual file imports (n = {other_count})"]
    if other_node and other_node.annotations:
        for k, v in sorted(other_node.annotations.items()):
            other_lines.append(f"  • {k}: {v}")
    result["identification.other_methods"] = NodeBoxContent(
        node_id="identification.other_methods",
        title="Records identified from other methods",
        lines=tuple(other_lines),
    )

    # 3. After deduplication
    after_node = node_map.get("identification.after_deduplication")
    after_count = after_node.values.get("count", 0) if after_node else 0
    result["identification.after_deduplication"] = NodeBoxContent(
        node_id="identification.after_deduplication",
        title="Records after duplicate removal",
        lines=(f"Active canonical records (n = {after_count})",),
    )

    # 4. Records removed
    removed_node = node_map.get("identification.records_removed")
    dup_removed = model.removed.get("duplicates_removed", 0)
    removed_lines: list[str] = [f"Technical duplicates merged (n = {dup_removed})"]
    if removed_node and "pending_review" in removed_node.annotations:
        removed_lines.append(f"Candidate groups pending review: {removed_node.annotations['pending_review']}")
    result["identification.records_removed"] = NodeBoxContent(
        node_id="identification.records_removed",
        title="Duplicates removed",
        lines=tuple(removed_lines),
        is_side_box=True,
    )

    # 5. Title & Abstract screened
    ta_node = node_map.get("screening.title_abstract")
    ta_count = ta_node.values.get("count", 0) if ta_node else 0
    result["screening.title_abstract"] = NodeBoxContent(
        node_id="screening.title_abstract",
        title="Records screened",
        lines=(f"Title & Abstract screened (n = {ta_count})",),
    )

    # 6. Excluded Title & Abstract
    ex_ta_count = model.removed.get("excluded_title_abstract", 0)
    result["screening.excluded_title_abstract"] = NodeBoxContent(
        node_id="screening.excluded_title_abstract",
        title="Records excluded",
        lines=(f"Title & Abstract excluded (n = {ex_ta_count})",),
        is_side_box=True,
    )

    # 7. Full-Text screened
    ft_node = node_map.get("screening.full_text")
    ft_count = ft_node.values.get("count", 0) if ft_node else 0
    result["screening.full_text"] = NodeBoxContent(
        node_id="screening.full_text",
        title="Reports sought for retrieval & assessed",
        lines=(f"Full-Text reports assessed (n = {ft_count})",),
    )

    # 8. Excluded Full-Text
    ex_ft_count = model.removed.get("excluded_full_text", 0)
    result["screening.excluded_full_text"] = NodeBoxContent(
        node_id="screening.excluded_full_text",
        title="Reports excluded",
        lines=(f"Full-Text excluded (n = {ex_ft_count})",),
        is_side_box=True,
    )

    # 9. Included in synthesis (D4 verified: final Full-Text INCLUDE population)
    inc_node = node_map.get("included.synthesis")
    inc_count = inc_node.values.get("count", 0) if inc_node else 0
    result["included.synthesis"] = NodeBoxContent(
        node_id="included.synthesis",
        title="Studies included in review",
        lines=(f"Studies included in synthesis (n = {inc_count})",),
    )

    return result
