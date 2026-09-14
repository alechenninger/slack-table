"""Command line interface for slack-table."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Optional

from . import __version__
from . import clipboard
from .core import AmbiguousColumnsError, ParseError, Table, format_table, parse_table
from .image import DEFAULT_IMAGE_ENGINE, DEFAULT_IMAGE_LANG, DEFAULT_IMAGE_PSM, parse_image_table


class CliError(RuntimeError):
    pass


def markdown_main(argv: Optional[Iterable[str]] = None) -> int:
    return main(argv, prog="md-table", default_output="markdown")


def main(
    argv: Optional[Iterable[str]] = None,
    *,
    prog: str = "slack-table",
    default_output: str = "slack",
) -> int:
    parser = _build_parser(prog=prog, default_output=default_output)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        table, copy_by_default = _read_table(args)
        output = format_table(table, args.output)
        should_copy = args.copy or copy_by_default

        if should_copy:
            clipboard.write(output)
            if not args.quiet and sys.stderr.isatty():
                label = "Markdown table" if args.output == "markdown" else "Slack-native table data"
                print(f"Copied {label} to the clipboard.", file=sys.stderr)

        if not args.quiet:
            print(output)
        return 0
    except (CliError, ClipboardError, ParseError) as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(f"{prog}: interrupted", file=sys.stderr)
        return 130


ClipboardError = clipboard.ClipboardError


def _build_parser(
    *, prog: str = "slack-table", default_output: str = "slack"
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Convert pasted or piped tables to Slack-native data or Markdown tables.",
    )
    parser.add_argument("files", nargs="*", help="table files to read; omit for stdin or clipboard")
    parser.add_argument(
        "--input",
        choices=["auto", "markdown", "cursor", "csv", "tsv", "pipe", "spaced"],
        default="auto",
        help="input format to parse (default: auto)",
    )
    parser.add_argument(
        "--columns",
        type=_column_count,
        metavar="N",
        help="column count for blank-line-separated cells; prompts if ambiguous",
    )
    parser.add_argument(
        "--output",
        choices=["slack", "markdown"],
        default=default_output,
        help="output format (default: %(default)s)",
    )
    parser.add_argument(
        "-c",
        "--copy",
        action="store_true",
        help="copy the formatted table to the clipboard",
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
        "--image",
        metavar="PATH",
        help="extract a table from an image file using local Tesseract OCR",
    )
    parser.add_argument(
        "--image-engine",
        choices=["auto", "tesserocr", "tesseract"],
        default=DEFAULT_IMAGE_ENGINE,
        help="OCR engine to use with --image (default: auto)",
    )
    parser.add_argument(
        "--image-lang",
        default=DEFAULT_IMAGE_LANG,
        help=f"Tesseract language to use with --image (default: {DEFAULT_IMAGE_LANG})",
    )
    parser.add_argument(
        "--image-psm",
        type=int,
        default=DEFAULT_IMAGE_PSM,
        help=f"Tesseract page segmentation mode to use with --image (default: {DEFAULT_IMAGE_PSM})",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="do not print the formatted table to stdout",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _read_table(args: argparse.Namespace) -> tuple[Table, bool]:
    if args.image:
        if args.files or args.clipboard or args.wait:
            raise CliError("--image cannot be combined with files, --clipboard, or --wait")
        if args.input != "auto":
            raise CliError("--input cannot be combined with --image")
        return (
            parse_image_table(
                args.image,
                engine=args.image_engine,
                lang=args.image_lang,
                psm=args.image_psm,
            ),
            False,
        )

    if args.wait:
        if args.files or args.clipboard:
            raise CliError("--wait cannot be combined with files or --clipboard")
        return _wait_for_clipboard_table(args), True

    if args.clipboard:
        if args.files:
            raise CliError("--clipboard cannot be combined with files")
        return _read_clipboard_table(args, require_image_support=True), True

    if args.files:
        return _parse_text(_read_files(args.files), args), False

    if not sys.stdin.isatty():
        return _parse_text(sys.stdin.read(), args), False

    try:
        return _read_clipboard_table(args, require_image_support=False), True
    except CliError:
        _prompt_for_terminal_paste()
        return _parse_text(sys.stdin.read(), args), True


def _read_clipboard_table(args: argparse.Namespace, *, require_image_support: bool) -> Table:
    text_error: Optional[ParseError] = None
    try:
        text = clipboard.read()
    except ClipboardError as exc:
        text = ""
        if require_image_support:
            text_error = ParseError(f"could not read clipboard text: {exc}")

    if text.strip():
        try:
            return _parse_text(text, args)
        except ParseError as exc:
            text_error = exc

    if clipboard.image_supported() or require_image_support:
        try:
            return _read_clipboard_image_table(args)
        except CliError:
            if text_error is None:
                raise

    if text_error is not None:
        raise text_error
    raise CliError("no table text or supported image found on the clipboard")


def _read_clipboard_image_table(args: argparse.Namespace) -> Table:
    with TemporaryDirectory() as tempdir:
        image_path = Path(tempdir) / "clipboard.png"
        try:
            clipboard.read_image(image_path)
        except ClipboardError as exc:
            raise CliError(f"could not read clipboard image: {exc}") from exc
        return parse_image_table(
            image_path,
            engine=args.image_engine,
            lang=args.image_lang,
            psm=args.image_psm,
        )


def _read_files(files: Iterable[str]) -> str:
    chunks = []
    for name in files:
        if name == "-":
            chunks.append(sys.stdin.read())
            continue
        try:
            chunks.append(Path(name).read_text())
        except (OSError, UnicodeError) as exc:
            raise CliError(str(exc)) from exc
    return "\n".join(chunks)


def _parse_text(text: str, args: argparse.Namespace) -> Table:
    try:
        return parse_table(text, input_format=args.input, columns=getattr(args, "columns", None))
    except AmbiguousColumnsError as exc:
        if not sys.stdin.isatty():
            raise CliError(f"{exc}; specify one with --columns N") from exc
        columns = _prompt_for_column_count(exc.candidates)
        return parse_table(text, input_format=args.input, columns=columns)


def _prompt_for_column_count(candidates: Iterable[int]) -> int:
    choices = list(candidates)
    label = ", ".join(str(choice) for choice in choices)
    while True:
        print(f"Number of columns ({label}): ", end="", file=sys.stderr, flush=True)
        response = sys.stdin.readline()
        if not response:
            raise CliError("no column count selected")
        try:
            selected = int(response)
        except ValueError:
            selected = 0
        if selected in choices:
            return selected
        print(f"Choose one of: {label}.", file=sys.stderr)


def _column_count(value: str) -> int:
    try:
        columns = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if columns < 2:
        raise argparse.ArgumentTypeError("must be at least 2")
    return columns


def _read_clipboard() -> str:
    try:
        return clipboard.read()
    except ClipboardError as exc:
        raise CliError(f"could not read clipboard: {exc}") from exc


def _wait_for_clipboard_table(args: argparse.Namespace) -> Table:
    try:
        original = clipboard.signature()
    except ClipboardError as exc:
        raise CliError(f"could not read clipboard: {exc}") from exc

    if sys.stderr.isatty():
        print("Copy a table now. Waiting for the clipboard to change...", file=sys.stderr)

    while True:
        time.sleep(0.2)
        try:
            current = clipboard.signature()
        except ClipboardError as exc:
            raise CliError(f"could not read clipboard: {exc}") from exc

        if current != original:
            return _read_clipboard_table(args, require_image_support=True)


def _prompt_for_terminal_paste() -> None:
    if sys.stderr.isatty():
        print("Paste a table, then press Ctrl-D:", file=sys.stderr)
