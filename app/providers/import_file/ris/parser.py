from __future__ import annotations

import re

# A valid RIS tag line: exactly two uppercase alphanumeric characters, then "  - " (two spaces, hyphen, space).
_TAG_LINE = re.compile(r'^([A-Z0-9]{2})  - (.*)')

# A line that is clearly a malformed RIS tag attempt — looks like a broken separator,
# but does not match the valid exact format.  Three narrow patterns:
#   1. ^[A-Z0-9]{2} -   e.g. "TY - JOUR"  (single space before the hyphen)
#   2. ^[A-Z0-9]{2}-[A-Z]  e.g. "TI-Title" (no space, value starts uppercase)
#   3. ^[A-Z0-9]{3,}\s*-\s  e.g. "TYY  - JOUR" (3+ tag chars with separator)
# This intentionally does NOT flag ordinary text such as:
#   "AI-based methods", "ISO-50001", "CO2-related" (continuation lines).
_MALFORMED_TAG_LINE = re.compile(
    r"^[A-Z0-9]{2} - "       # single-space separator variant
    r"|^[A-Z0-9]{2}-[A-Z]"   # no-space, uppercase-start value
    r"|^[A-Z0-9]{3,}\s*-\s"  # 3+ char tag with any spaces around hyphen
)


def parse_ris(content: str) -> list[dict[str, list[str]]]:
    """Parse RIS content into a list of raw records.

    Each record is returned as a dict mapping tag names to lists of values.
    Repeated tags (e.g. AU, KW) accumulate multiple list entries.
    Non-tag lines inside an open record are treated as continuation lines
    and appended (space-separated) to the most recently parsed field value.

    Raises ValueError on:
    - malformed tag-like lines (look like a tag but don't match TAG  - VALUE)
    - continuation line outside a record
    - ER before TY
    - nested TY (TY inside an unfinished record)
    - any tag before TY (other than ER caught separately)
    - EOF inside an unclosed record (missing ER)
    """
    records: list[dict[str, list[str]]] = []
    current_record: dict[str, list[str]] | None = None
    last_tag: str | None = None

    for line_num, raw_line in enumerate(content.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            # Blank lines are ignored everywhere
            continue

        m = _TAG_LINE.match(raw_line)
        if m:
            tag = m.group(1)
            value = m.group(2).strip()

            if tag == "TY":
                if current_record is not None:
                    raise ValueError(
                        f"Nested TY tag found at line {line_num} before finishing previous record"
                    )
                current_record = {"TY": [value]}
                last_tag = "TY"
            elif tag == "ER":
                if current_record is None:
                    raise ValueError(f"ER tag found at line {line_num} before any TY tag")
                records.append(current_record)
                current_record = None
                last_tag = None
            else:
                if current_record is None:
                    raise ValueError(f"Tag {tag} found at line {line_num} before any TY tag")
                current_record.setdefault(tag, []).append(value)
                last_tag = tag
        elif _MALFORMED_TAG_LINE.match(raw_line):
            # Looks like a tag attempt (e.g. "TI - value", "AB-text", "TYY  - JOUR") — always invalid
            raise ValueError(f"Malformed RIS line at line {line_num}: {repr(raw_line)}")
        else:
            # Plain text: treat as continuation of the most recent field.
            # last_tag is always set when current_record is open (TY sets it on entry).
            if current_record is None:
                raise ValueError(
                    f"Continuation line found outside a record at line {line_num}: {repr(raw_line)}"
                )
            current_record[last_tag][-1] = f"{current_record[last_tag][-1]} {line}"  # type: ignore[index]

    if current_record is not None:
        raise ValueError("EOF reached before last record was closed with ER tag")

    return records
