"""Server-side standard-library SVG renderer for PRISMA 2020 flow diagrams (v0.6.1 Slice 3).

Renders a presentation-neutral PrismaFlowModel into a standalone, printable,
XML-valid SVG document using the shared geometry defined in layout.py.

Guarantees:
- Stdlib-only: zero external rendering dependencies (no browser/headless engine).
- Strict XML safety: all text content escaped via xml.sax.saxutils.escape.
- Reproducibility: zero timestamps inside SVG; byte-identical output for identical input.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from app.domain.prisma_flow import PrismaFlowModel
from app.services.export.layout import (
    ARROWS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COLOR_ARROW,
    COLOR_BG,
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

_CONTROL_CHARACTERS = frozenset(
    "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"
)


def render_prisma_svg(model: PrismaFlowModel) -> str:
    """Render a PRISMA 2020 flow model into a standalone, deterministic SVG string."""
    contents = extract_node_contents(model)

    raw_title = "".join(c for c in model.metadata.project_title if c not in _CONTROL_CHARACTERS)
    display_title = raw_title[:100] + ("…" if len(raw_title) > 100 else "")
    raw_protocol = "".join(c for c in (model.metadata.protocol_version or "") if c not in _CONTROL_CHARACTERS)

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {int(CANVAS_WIDTH)} {int(CANVAS_HEIGHT)}" width="{int(CANVAS_WIDTH)}" height="{int(CANVAS_HEIGHT)}">',
        '  <defs>',
        '    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">',
        f'      <polygon points="0 0, 8 3, 0 6" fill="{COLOR_ARROW}" />',
        '    </marker>',
        '    <style>',
        '      .title-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "DejaVu Sans", Arial, sans-serif; font-size: 15px; font-weight: 600; fill: ' + COLOR_TEXT_PRIMARY + '; }',
        '      .meta-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "DejaVu Sans", Arial, sans-serif; font-size: 11px; fill: ' + COLOR_TEXT_MUTED + '; }',
        '      .stage-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "DejaVu Sans", Arial, sans-serif; font-size: 13px; font-weight: 700; text-anchor: middle; letter-spacing: 0.5px; }',
        '      .box-title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "DejaVu Sans", Arial, sans-serif; font-size: 11.5px; font-weight: 600; fill: ' + COLOR_TEXT_PRIMARY + '; }',
        '      .box-line { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "DejaVu Sans", Arial, sans-serif; font-size: 11px; fill: ' + COLOR_TEXT_SECONDARY + '; }',
        '      .box-subline { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "DejaVu Sans", Arial, sans-serif; font-size: 10px; fill: ' + COLOR_TEXT_MUTED + '; }',
        '    </style>',
        '  </defs>',
        '  <!-- Background -->',
        f'  <rect width="{int(CANVAS_WIDTH)}" height="{int(CANVAS_HEIGHT)}" fill="{COLOR_BG}" />',
        '',
        '  <!-- Header -->',
        f'  <text x="20" y="30" class="title-text">PRISMA 2020 Flow Diagram — {escape(display_title)}</text>',
    ]

    if raw_protocol:
        lines.append(f'  <text x="{int(CANVAS_WIDTH) - 20}" y="30" text-anchor="end" class="meta-text">Protocol: {escape(raw_protocol)}</text>')

    lines.append('')
    lines.append('  <!-- Stage Bands -->')
    for band in STAGE_BANDS:
        lines.append(
            f'  <rect x="{band.x}" y="{band.y}" width="{band.width}" height="{band.height}" rx="6" ry="6" '
            f'fill="{band.fill_color}" stroke="{band.border_color}" stroke-width="1.5" />'
        )
        center_x = band.x + (band.width / 2.0)
        center_y = band.y + (band.height / 2.0) + 5.0
        lines.append(
            f'  <text x="{center_x}" y="{center_y}" class="stage-text" fill="{band.text_color}">{escape(band.label)}</text>'
        )

    lines.append('')
    lines.append('  <!-- Flow Arrows -->')
    for arrow in ARROWS:
        if arrow.from_node in contents and arrow.to_node in contents:
            lines.append(
                f'  <line x1="{arrow.from_x}" y1="{arrow.from_y}" x2="{arrow.to_x}" y2="{arrow.to_y}" '
                f'stroke="{COLOR_ARROW}" stroke-width="1.5" marker-end="url(#arrowhead)" />'
            )

    lines.append('')
    lines.append('  <!-- Flow Boxes -->')
    for node_id, layout in sorted(NODE_LAYOUTS.items()):
        content = contents.get(node_id)
        if content is None:
            continue
        fill_color = COLOR_SIDE_BOX_FILL if layout.is_side_box else COLOR_BOX_FILL
        lines.append(
            f'  <rect x="{layout.x}" y="{layout.y}" width="{layout.width}" height="{layout.height}" rx="4" ry="4" '
            f'fill="{fill_color}" stroke="{COLOR_BORDER}" stroke-width="1.2" />'
        )
        title_y = layout.y + 20.0
        lines.append(
            f'  <text x="{layout.x + 12.0}" y="{title_y}" class="box-title">{escape(content.title)}</text>'
        )
        curr_y = title_y + 18.0
        for idx, line in enumerate(content.lines):
            line_class = "box-line" if idx == 0 else "box-subline"
            lines.append(
                f'  <text x="{layout.x + 12.0}" y="{curr_y}" class="{line_class}">{escape(line)}</text>'
            )
            curr_y += 15.0

    lines.append('</svg>')
    return '\n'.join(lines) + '\n'
