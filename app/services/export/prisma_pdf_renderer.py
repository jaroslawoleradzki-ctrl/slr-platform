"""Deterministic semantic PRISMA 2020 PDF diagram renderer (v0.6.1 Slice 4).

Renders a presentation-neutral PrismaFlowModel into a standalone, printable PDF
document using fpdf2 and bundled OFL-compatible Unicode fonts (DejaVu Sans).
Reuses shared layout geometry from layout.py without creating any second PRISMA
counting implementation.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF

from app.services.export.layout import (
    ARROWS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COLOR_ARROW,
    COLOR_BORDER,
    COLOR_BOX_FILL,
    COLOR_SIDE_BOX_FILL,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    NODE_LAYOUTS,
    STAGE_BANDS,
    extract_node_contents,
)

if TYPE_CHECKING:
    from app.domain.prisma_flow import PrismaFlowModel


def _get_font_paths() -> tuple[Path, Path]:
    """Resolve paths to bundled regular and bold DejaVuSans TTF fonts."""
    candidates: list[Path] = []

    env_dir = os.getenv("SLR_FONTS_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    # In-repo bundled font assets: <repo_root>/assets/fonts
    repo_assets = Path(__file__).resolve().parents[3] / "assets" / "fonts"
    candidates.append(repo_assets)

    # Standard Linux system fallback
    candidates.append(Path("/usr/share/fonts/truetype/dejavu"))

    for directory in candidates:
        regular = directory / "DejaVuSans.ttf"
        bold = directory / "DejaVuSans-Bold.ttf"
        if regular.is_file() and bold.is_file():
            return regular, bold

    raise FileNotFoundError(
        f"Could not locate DejaVuSans.ttf and DejaVuSans-Bold.ttf in any search location: "
        f"{[str(p) for p in candidates]}"
    )


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string (#RRGGBB) to (R, G, B) integer tuple."""
    hex_clean = hex_color.lstrip("#")
    if len(hex_clean) == 6:
        return int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)
    return 0, 0, 0


def render_prisma_pdf(model: PrismaFlowModel) -> bytes:
    """Render a presentation-neutral PrismaFlowModel into standalone PDF bytes.

    All counts and stage structures are taken directly from the supplied model.
    No repository queries or arithmetic re-derivations occur in this renderer.
    """
    regular_font, bold_font = _get_font_paths()
    contents = extract_node_contents(model)

    pdf = FPDF(orientation="P", unit="pt", format=(CANVAS_WIDTH, CANVAS_HEIGHT))
    pdf.set_auto_page_break(False)

    # Deterministic creation timestamp from flow model metadata
    if model.metadata.generated_at:
        try:
            gen_dt = datetime.fromisoformat(model.metadata.generated_at)
            pdf.set_creation_date(gen_dt)
        except Exception:
            pdf.set_creation_date(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
    else:
        pdf.set_creation_date(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))

    pdf.add_page()

    # Register bundled OFL Unicode fonts
    pdf.add_font("DejaVuSans", "", str(regular_font))
    pdf.add_font("DejaVuSans", "B", str(bold_font))

    # 1. Header
    pdf.set_text_color(*_hex_to_rgb(COLOR_TEXT_PRIMARY))
    pdf.set_font("DejaVuSans", "B", 14)
    pdf.text(20.0, 32.0, "PRISMA 2020 Flow Diagram")

    # Optional project title & protocol subtitle
    subtitle_parts: list[str] = []
    if model.metadata.project_title:
        subtitle_parts.append(model.metadata.project_title)
    if model.metadata.protocol_version:
        subtitle_parts.append(f"({model.metadata.protocol_version})")

    if subtitle_parts:
        subtitle = " — ".join(subtitle_parts)
        pdf.set_text_color(*_hex_to_rgb(COLOR_TEXT_MUTED))
        pdf.set_font("DejaVuSans", "", 8.5)
        pdf.text(20.0, 46.0, subtitle)

    # 2. Stage Bands (left vertical bands)
    for band in STAGE_BANDS:
        pdf.set_fill_color(*_hex_to_rgb(band.fill_color))
        pdf.set_draw_color(*_hex_to_rgb(band.border_color))
        pdf.set_line_width(1.0)
        pdf.rect(band.x, band.y, band.width, band.height, style="FD")

        pdf.set_text_color(*_hex_to_rgb(band.text_color))
        pdf.set_font("DejaVuSans", "B", 11)
        pdf.set_xy(band.x, band.y)
        pdf.cell(band.width, band.height, band.label, align="C")

    # 3. Flow Arrows & Arrowheads
    pdf.set_draw_color(*_hex_to_rgb(COLOR_ARROW))
    pdf.set_fill_color(*_hex_to_rgb(COLOR_ARROW))
    pdf.set_line_width(1.5)
    for arrow in ARROWS:
        if arrow.from_node in contents and arrow.to_node in contents:
            pdf.line(arrow.from_x, arrow.from_y, arrow.to_x, arrow.to_y)
            # Arrowhead vector calculation
            dx = arrow.to_x - arrow.from_x
            dy = arrow.to_y - arrow.from_y
            dist = math.hypot(dx, dy)
            if dist > 0:
                ux = dx / dist
                uy = dy / dist
                px = -uy
                py = ux
                tip_x, tip_y = arrow.to_x, arrow.to_y
                base_l = (tip_x - 6.0 * ux + 3.5 * px, tip_y - 6.0 * uy + 3.5 * py)
                base_r = (tip_x - 6.0 * ux - 3.5 * px, tip_y - 6.0 * uy - 3.5 * py)
                pdf.polygon([(tip_x, tip_y), base_l, base_r], style="F")

    # 4. Node Boxes & Text Contents
    for node_id, layout in sorted(NODE_LAYOUTS.items()):
        content = contents.get(node_id)
        if content is None:
            continue

        fill_color = COLOR_SIDE_BOX_FILL if content.is_side_box else COLOR_BOX_FILL
        pdf.set_fill_color(*_hex_to_rgb(fill_color))
        pdf.set_draw_color(*_hex_to_rgb(COLOR_BORDER))
        pdf.set_line_width(1.0)
        pdf.rect(layout.x, layout.y, layout.width, layout.height, style="FD")

        # Box Title (Bold)
        pdf.set_text_color(*_hex_to_rgb(COLOR_TEXT_PRIMARY))
        pdf.set_font("DejaVuSans", "B", 9.0)
        pdf.set_xy(layout.x + 8.0, layout.y + 6.0)
        pdf.cell(layout.width - 16.0, 12.0, content.title, align="L")

        # Box Content Lines (Counts & Annotations)
        pdf.set_text_color(*_hex_to_rgb(COLOR_TEXT_SECONDARY))
        pdf.set_font("DejaVuSans", "", 8.0)
        cur_y = layout.y + 22.0
        for line in content.lines:
            pdf.set_xy(layout.x + 8.0, cur_y)
            pdf.cell(layout.width - 16.0, 11.0, line, align="L")
            cur_y += 12.0

    return bytes(pdf.output())
