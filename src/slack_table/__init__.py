"""Slack-friendly table formatting."""

from .core import ParseError, Table, format_table, format_tsv, parse_table, render
from .image import parse_image_table

__all__ = [
    "ParseError",
    "Table",
    "format_table",
    "format_tsv",
    "parse_image_table",
    "parse_table",
    "render",
]

__version__ = "0.1.0"
