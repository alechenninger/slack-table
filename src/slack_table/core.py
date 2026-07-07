"""Parse text tables and render Slack-native table paste data."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence


class ParseError(ValueError):
    """Raised when input cannot be parsed as a table."""


@dataclass(frozen=True)
class Table:
    rows: List[List[str]]
    source_format: str = "auto"


_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")


def render(text: str, input_format: str = "auto") -> str:
    """Parse text and return tab-separated rows for Slack native table paste."""

    return format_tsv(parse_table(text, input_format))


def parse_table(text: str, input_format: str = "auto") -> Table:
    """Parse text as a table.

    Supported input formats are ``auto``, ``markdown``, ``csv``, ``tsv``, and
    ``pipe``. The parser list is intentionally small and explicit so new formats
    can be added without touching the Slack renderer.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        raise ParseError("no table input found")

    parsers = {
        "markdown": _parse_markdown,
        "csv": _parse_csv,
        "tsv": _parse_tsv,
        "pipe": _parse_pipe,
    }

    if input_format != "auto":
        try:
            parser = parsers[input_format]
        except KeyError as exc:
            names = ", ".join(["auto"] + sorted(parsers))
            raise ParseError(f"unknown input format {input_format!r}; expected {names}") from exc
        return parser(text)

    for parser in (_parse_markdown, _parse_tsv, _parse_csv, _parse_pipe):
        try:
            return parser(text)
        except ParseError:
            pass

    raise ParseError("could not detect a supported table format")


def format_tsv(table: Table) -> str:
    """Render table cells as tab-separated values for Slack native table paste."""

    rows = _normalized(table.rows)
    if not rows:
        raise ParseError("no table rows found")
    return "\n".join("\t".join(_tsv_cell(cell) for cell in row) for row in rows)


def format_table(table: Table) -> str:
    """Alias for the Slack-native table representation."""

    return format_tsv(table)


def _parse_markdown(text: str) -> Table:
    lines = _non_empty_lines(text)
    if len(lines) < 2:
        raise ParseError("markdown tables need a header and separator")

    for separator_index in range(1, len(lines)):
        separator_cells = _split_markdown_row(lines[separator_index])
        if not _is_separator_row(separator_cells):
            continue

        header = _split_markdown_row(lines[separator_index - 1])
        if len(header) < 2:
            raise ParseError("markdown header must have at least two columns")

        body: List[List[str]] = []
        expected_cols = max(len(header), len(separator_cells))
        for line in lines[separator_index + 1 :]:
            row = _split_markdown_row(line)
            if len(row) < 2:
                break
            body.append(row)

        return Table(rows=_normalized([header] + body, expected_cols), source_format="markdown")

    raise ParseError("no markdown table separator found")


def _parse_pipe(text: str) -> Table:
    lines = _non_empty_lines(text)
    if len(lines) < 1 or not any("|" in line for line in lines):
        raise ParseError("no pipe-delimited rows found")

    rows = [_split_markdown_row(line) for line in lines]
    if len(rows[0]) < 2:
        raise ParseError("pipe-delimited input must have at least two columns")

    if len(rows) > 1 and _is_separator_row(rows[1]):
        rows = [rows[0]] + rows[2:]

    return Table(rows=_normalized(rows), source_format="pipe")


def _parse_csv(text: str) -> Table:
    if "," not in text:
        raise ParseError("no comma-delimited rows found")
    return _parse_delimited(text, "csv", lambda data: csv.reader(data))


def _parse_tsv(text: str) -> Table:
    if "\t" not in text:
        raise ParseError("no tab-delimited rows found")
    return _parse_delimited(text, "tsv", lambda data: csv.reader(data, delimiter="\t"))


def _parse_delimited(
    text: str,
    source_format: str,
    reader_factory: Callable[[io.StringIO], Iterable[Sequence[str]]],
) -> Table:
    try:
        rows = [
            [_clean_cell(cell) for cell in row]
            for row in reader_factory(io.StringIO(text))
            if any(cell.strip() for cell in row)
        ]
    except csv.Error as exc:
        raise ParseError(str(exc)) from exc

    if not rows:
        raise ParseError(f"no {source_format} rows found")
    if max(len(row) for row in rows) < 2:
        raise ParseError(f"{source_format} input must have at least two columns")

    return Table(rows=_normalized(rows), source_format=source_format)


def _non_empty_lines(text: str) -> List[str]:
    return [line for line in text.split("\n") if line.strip()]


def _split_markdown_row(line: str) -> List[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]

    cells: List[str] = []
    current: List[str] = []
    escaped = False

    for char in line:
        if escaped:
            current.append(char if char == "|" else "\\" + char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append(_clean_cell("".join(current)))
            current = []
            continue
        current.append(char)

    if escaped:
        current.append("\\")
    cells.append(_clean_cell("".join(current)))
    return cells


def _clean_cell(cell: str) -> str:
    return " ".join(cell.replace("\n", " ").split())


def _is_separator_row(cells: Sequence[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_RE.match(cell.strip()) for cell in cells)


def _normalized(rows: Sequence[Sequence[str]], min_columns: Optional[int] = None) -> List[List[str]]:
    if not rows:
        return []

    column_count = max(max(len(row) for row in rows), min_columns or 0)
    return [[_clean_cell(cell) for cell in row] + [""] * (column_count - len(row)) for row in rows]


def _tsv_cell(value: str) -> str:
    return _clean_cell(value).replace("\t", " ")
