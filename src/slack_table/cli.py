"""Command line interface for slack-table."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from . import __version__
from . import clipboard
from .core import ParseError, format_tsv, parse_table


class CliError(RuntimeError):
    pass


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        text, copy_by_default = _read_input(args)
        table = parse_table(text, input_format=args.input)
        output = format_tsv(table)
        should_copy = args.copy or copy_by_default

        if should_copy:
            clipboard.write(output)
            if not args.quiet and sys.stderr.isatty():
                print("Copied Slack-native table data to the clipboard.", file=sys.stderr)

        if not args.quiet:
            print(output)
        return 0
    except (CliError, ClipboardError, ParseError) as exc:
        print(f"slack-table: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("slack-table: interrupted", file=sys.stderr)
        return 130


ClipboardError = clipboard.ClipboardError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slack-table",
        description="Convert pasted or piped tables to Slack-native table paste data.",
    )
    parser.add_argument("files", nargs="*", help="table files to read; omit for stdin or clipboard")
    parser.add_argument(
        "--input",
        choices=["auto", "markdown", "csv", "tsv", "pipe"],
        default="auto",
        help="input format to parse (default: auto)",
    )
    parser.add_argument(
        "-c",
        "--copy",
        action="store_true",
        help="copy Slack-native table data to the clipboard",
    )
    parser.add_argument(
        "--clipboard",
        "--clip",
        action="store_true",
        help="read input from the clipboard",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait for the next clipboard change, convert it, copy the result, and exit",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="do not print the formatted table to stdout",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _read_input(args: argparse.Namespace) -> tuple[str, bool]:
    if args.wait:
        if args.files or args.clipboard:
            raise CliError("--wait cannot be combined with files or --clipboard")
        return _wait_for_clipboard(), True

    if args.clipboard:
        if args.files:
            raise CliError("--clipboard cannot be combined with files")
        return _read_clipboard(), True

    if args.files:
        return _read_files(args.files), False

    if not sys.stdin.isatty():
        return sys.stdin.read(), False

    try:
        text = _read_clipboard()
    except CliError:
        _prompt_for_terminal_paste()
        return sys.stdin.read(), True

    if text.strip():
        return text, True

    _prompt_for_terminal_paste()
    return sys.stdin.read(), True


def _read_files(files: Iterable[str]) -> str:
    chunks = []
    for name in files:
        if name == "-":
            chunks.append(sys.stdin.read())
            continue
        try:
            chunks.append(Path(name).read_text())
        except OSError as exc:
            raise CliError(str(exc)) from exc
    return "\n".join(chunks)


def _read_clipboard() -> str:
    try:
        return clipboard.read()
    except ClipboardError as exc:
        raise CliError(f"could not read clipboard: {exc}") from exc


def _wait_for_clipboard() -> str:
    try:
        original = clipboard.read()
    except ClipboardError as exc:
        raise CliError(f"could not read clipboard: {exc}") from exc

    if sys.stderr.isatty():
        print("Copy a table now. Waiting for the clipboard to change...", file=sys.stderr)

    while True:
        time.sleep(0.2)
        try:
            current = clipboard.read()
        except ClipboardError as exc:
            raise CliError(f"could not read clipboard: {exc}") from exc

        if current != original and current.strip():
            return current


def _prompt_for_terminal_paste() -> None:
    if sys.stderr.isatty():
        print("Paste a table, then press Ctrl-D:", file=sys.stderr)
