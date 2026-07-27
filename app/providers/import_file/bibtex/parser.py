from __future__ import annotations

from typing import TypedDict


class BibTeXRecord(TypedDict):
    entry_type: str
    citation_key: str
    fields: dict[str, str]


class _Parser:
    def __init__(self, content: str) -> None:
        self.content = content
        self.position = 0

    def parse(self) -> list[BibTeXRecord]:
        records: list[BibTeXRecord] = []
        while True:
            self._skip_whitespace_and_comments()
            if self._at_end():
                return records
            if self._current() != "@":
                raise ValueError("Expected '@' at the start of a BibTeX entry")
            records.extend(self._parse_entry())

    def _parse_entry(self) -> list[BibTeXRecord]:
        self.position += 1
        entry_type = self._read_identifier("entry type").lower()
        if entry_type in {"string", "preamble"}:
            raise ValueError(f"Unsupported BibTeX construct: @{entry_type}")

        self._skip_whitespace_and_comments()
        if self._at_end() or self._current() != "{":
            raise ValueError("Expected '{' after BibTeX entry type")
        self.position += 1

        if entry_type == "comment":
            self._skip_comment_entry()
            return []

        citation_key = self._read_citation_key()
        if not citation_key:
            raise ValueError("BibTeX entry is missing a citation key")
        if self._at_end():
            raise ValueError("BibTeX entry is missing its closing brace")

        delimiter = self._current()
        self.position += 1
        if delimiter == "}":
            return [
                {
                    "entry_type": entry_type,
                    "citation_key": citation_key,
                    "fields": {},
                }
            ]

        fields = self._parse_fields()
        return [
            {
                "entry_type": entry_type,
                "citation_key": citation_key,
                "fields": fields,
            }
        ]

    def _parse_fields(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        while True:
            self._skip_whitespace_and_comments()
            if self._at_end():
                raise ValueError("BibTeX entry is missing its closing brace")
            if self._current() == "}":
                self.position += 1
                return fields

            field_name = self._read_identifier("field name").lower()
            self._skip_whitespace_and_comments()
            if self._at_end() or self._current() != "=":
                raise ValueError(f"Missing '=' after BibTeX field '{field_name}'")
            self.position += 1
            self._skip_whitespace_and_comments()
            fields[field_name] = self._parse_value()

            self._skip_whitespace_and_comments()
            if self._at_end():
                raise ValueError("BibTeX entry is missing its closing brace")
            if self._current() == ",":
                self.position += 1
                continue
            if self._current() == "}":
                self.position += 1
                return fields
            raise ValueError("Expected another BibTeX field or the end of the entry")

    def _parse_value(self) -> str:
        if self._at_end():
            raise ValueError("BibTeX field is missing a value")
        if self._current() == "{":
            return self._parse_braced_value()
        if self._current() == '"':
            return self._parse_quoted_value()
        raise ValueError("BibTeX field values must use braces or quotes")

    def _parse_braced_value(self) -> str:
        self.position += 1
        start = self.position
        depth = 1
        while not self._at_end():
            character = self._current()
            if character == "{" and not self._is_escaped():
                depth += 1
            elif character == "}" and not self._is_escaped():
                depth -= 1
                if depth == 0:
                    value = self.content[start : self.position].strip()
                    self.position += 1
                    return value
            self.position += 1
        raise ValueError("Unclosed braced BibTeX value")

    def _parse_quoted_value(self) -> str:
        self.position += 1
        start = self.position
        while not self._at_end():
            if self._current() == '"' and not self._is_escaped():
                value = self.content[start : self.position].strip()
                self.position += 1
                return value
            self.position += 1
        raise ValueError("Unclosed quoted BibTeX value")

    def _skip_comment_entry(self) -> None:
        depth = 1
        while not self._at_end():
            character = self._current()
            if character == "{" and not self._is_escaped():
                depth += 1
            elif character == "}" and not self._is_escaped():
                depth -= 1
                if depth == 0:
                    self.position += 1
                    return
            self.position += 1
        raise ValueError("BibTeX comment is missing its closing brace")

    def _read_identifier(self, description: str) -> str:
        self._skip_whitespace_and_comments()
        start = self.position
        while not self._at_end() and (
            self._current().isalnum() or self._current() in "_-"
        ):
            self.position += 1
        identifier = self.content[start : self.position]
        if not identifier:
            raise ValueError(f"Expected BibTeX {description}")
        return identifier

    def _read_citation_key(self) -> str:
        parts: list[str] = []
        while not self._at_end() and self._current() not in ",}":
            if self._current() == "%":
                while not self._at_end() and self._current() not in "\r\n":
                    self.position += 1
                continue
            parts.append(self._current())
            self.position += 1
        return "".join(parts).strip()

    def _skip_whitespace_and_comments(self) -> None:
        while True:
            while not self._at_end() and self._current().isspace():
                self.position += 1
            if self._at_end() or self._current() != "%":
                return
            while not self._at_end() and self._current() not in "\r\n":
                self.position += 1

    def _is_escaped(self) -> bool:
        backslashes = 0
        position = self.position - 1
        while position >= 0 and self.content[position] == "\\":
            backslashes += 1
            position -= 1
        return backslashes % 2 == 1

    def _current(self) -> str:
        return self.content[self.position]

    def _at_end(self) -> bool:
        return self.position >= len(self.content)


def parse_bibtex(content: str) -> list[BibTeXRecord]:
    """Parse BibTeX content into normalized raw records."""
    return _Parser(content).parse()
