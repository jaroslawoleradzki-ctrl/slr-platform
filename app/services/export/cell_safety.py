"""Excel-safe cell serialization shared by XLSX export builders (v0.6.1 Slice 2).

Guarantees for every string cell written to a workbook:

- control characters that Excel/openpyxl reject are stripped (plan §17);
- values beginning with formula trigger characters (``=`` ``+`` ``-`` ``@``
  TAB CR) are neutralized with a leading apostrophe so hostile metadata can
  never execute as a spreadsheet formula;
- overlong values are truncated to the hard 32 767-character XLSX cell limit
  with an explicit marker instead of raising.
"""

from __future__ import annotations

from typing import Any

_MAX_XLSX_CELL_LENGTH = 32767
_TRUNCATION_MARKER = "…[truncated]"

_FORMULA_TRIGGER_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Control characters stripped from every emitted value (plan §17).
_CONTROL_CHARACTERS = frozenset(
    "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"
)


def excel_safe_cell(value: str | None) -> str:
    """Return *value* made safe for an XLSX string cell; ``None`` → empty."""
    if value is None:
        return ""
    cleaned = "".join(character for character in value if character not in _CONTROL_CHARACTERS)
    if cleaned.startswith(_FORMULA_TRIGGER_PREFIXES):
        cleaned = "'" + cleaned
    if len(cleaned) > _MAX_XLSX_CELL_LENGTH:
        keep = _MAX_XLSX_CELL_LENGTH - len(_TRUNCATION_MARKER)
        cleaned = cleaned[:keep] + _TRUNCATION_MARKER
    return cleaned


def sanitize_csv_cell(value: Any) -> str:
    """Return *value* as a formula-safe string for CSV cells."""
    if value is None:
        return ""
    val_str = str(value)
    cleaned = "".join(character for character in val_str if character not in _CONTROL_CHARACTERS)
    if cleaned.startswith(_FORMULA_TRIGGER_PREFIXES):
        cleaned = "'" + cleaned
    return cleaned
