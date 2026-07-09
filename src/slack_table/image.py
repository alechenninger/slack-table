"""Extract table rows from image files using local Tesseract OCR."""

from __future__ import annotations

import csv
import mimetypes
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Iterable, List, Optional, Sequence, Union

from .core import ParseError, Table


DEFAULT_IMAGE_ENGINE = "auto"
DEFAULT_IMAGE_LANG = "eng"
DEFAULT_IMAGE_PSM = 6
SUPPORTED_IMAGE_ENGINES = {"auto", "tesserocr", "tesseract"}
SUPPORTED_IMAGE_MIME_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}


class EmbeddedTesseractUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2


@dataclass(frozen=True)
class CellSegment:
    text: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left


def parse_image_table(
    image_path: Union[str, Path],
    *,
    engine: str = DEFAULT_IMAGE_ENGINE,
    lang: str = DEFAULT_IMAGE_LANG,
    psm: int = DEFAULT_IMAGE_PSM,
    timeout: float = 30,
) -> Table:
    """Parse an image of a table into logical rows using local OCR only."""

    if engine not in SUPPORTED_IMAGE_ENGINES:
        names = ", ".join(sorted(SUPPORTED_IMAGE_ENGINES))
        raise ParseError(f"unknown image OCR engine {engine!r}; expected {names}")

    path = _validate_image_path(image_path)
    words = _ocr_words(path, engine=engine, lang=lang, psm=psm, timeout=timeout)
    return Table(rows=_words_to_table_rows(words), source_format="image")


def _validate_image_path(image_path: Union[str, Path]) -> Path:
    path = Path(image_path)
    if not path.exists():
        raise ParseError(f"image file not found: {path}")
    if not path.is_file():
        raise ParseError(f"image path is not a file: {path}")

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_MIME_TYPES))
        raise ParseError(f"unsupported image type for {path}; expected one of {supported}")

    return path


def _ocr_words(
    path: Path,
    *,
    engine: str,
    lang: str,
    psm: int,
    timeout: float,
) -> List[OcrWord]:
    if engine in {"auto", "tesserocr"}:
        try:
            return _ocr_words_tesserocr(path, lang=lang, psm=psm)
        except EmbeddedTesseractUnavailable as exc:
            if engine == "tesserocr":
                raise ParseError(str(exc)) from exc

    return _ocr_words_tesseract(path, lang=lang, psm=psm, timeout=timeout)


def _ocr_words_tesserocr(path: Path, *, lang: str, psm: int) -> List[OcrWord]:
    try:
        import tesserocr
    except ImportError as exc:
        raise EmbeddedTesseractUnavailable(
            "embedded Tesseract OCR requires the tesserocr package"
        ) from exc

    try:
        with tesserocr.PyTessBaseAPI(lang=lang, psm=psm) as api:
            api.SetImageFile(str(path))
            api.Recognize()
            iterator = api.GetIterator()
            if iterator is None:
                return []

            words: List[OcrWord] = []
            level = tesserocr.RIL.WORD
            for result in tesserocr.iterate_level(iterator, level):
                text = (result.GetUTF8Text(level) or "").strip()
                if not text:
                    continue
                bbox = result.BoundingBox(level)
                if bbox is None:
                    continue
                left, top, right, bottom = bbox
                words.append(
                    OcrWord(
                        text=text,
                        left=int(left),
                        top=int(top),
                        width=int(right - left),
                        height=int(bottom - top),
                        confidence=float(result.Confidence(level)),
                    )
                )
            return words
    except RuntimeError as exc:
        raise ParseError(f"embedded Tesseract OCR failed: {exc}") from exc


def _ocr_words_tesseract(path: Path, *, lang: str, psm: int, timeout: float) -> List[OcrWord]:
    if not shutil.which("tesseract"):
        raise ParseError(
            "local image input requires either the tesserocr package "
            "or the tesseract command on PATH; on macOS run "
            "`brew install tesseract` and reinstall slack-table"
        )

    command = ["tesseract", str(path), "-", "-l", lang, "--psm", str(psm), "tsv"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParseError(f"Tesseract OCR timed out after {timeout:g} seconds") from exc
    except OSError as exc:
        raise ParseError(f"could not run Tesseract OCR: {exc}") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or "unknown error"
        raise ParseError(f"Tesseract OCR failed: {message}")

    return _words_from_tsv(completed.stdout)


def _words_from_tsv(text: str) -> List[OcrWord]:
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    words: List[OcrWord] = []

    for row in reader:
        if row.get("level") != "5":
            continue

        word_text = (row.get("text") or "").strip()
        if not word_text:
            continue

        confidence = _float(row.get("conf"), default=-1)
        if confidence < 0:
            continue

        try:
            words.append(
                OcrWord(
                    text=word_text,
                    left=_int(row.get("left")),
                    top=_int(row.get("top")),
                    width=_int(row.get("width")),
                    height=_int(row.get("height")),
                    confidence=confidence,
                )
            )
        except ValueError as exc:
            raise ParseError("Tesseract OCR returned malformed TSV output") from exc

    return words


def _words_to_table_rows(words: Sequence[OcrWord]) -> List[List[str]]:
    if not words:
        raise ParseError("no text recognized in image")

    lines = _group_words_by_line(words)
    gap_threshold = _cell_gap_threshold(words)
    rows = [_segments_for_line(line, gap_threshold) for line in lines]
    rows = [row for row in rows if row]
    if not rows:
        raise ParseError("no table cells recognized in image")

    columns = _column_positions([segment for row in rows for segment in row])
    if len(columns) < 2:
        raise ParseError("image table must have at least two columns")

    table_rows: List[List[str]] = []
    for row in rows:
        cells = [""] * len(columns)
        for segment in row:
            column = _nearest_column(segment.left, columns)
            cells[column] = " ".join(part for part in [cells[column], segment.text] if part)
        if any(cell.strip() for cell in cells):
            table_rows.append(cells)

    return _trim_empty_edge_columns(table_rows)


def _group_words_by_line(words: Sequence[OcrWord]) -> List[List[OcrWord]]:
    row_threshold = max(8.0, _median([word.height for word in words]) * 0.8)
    grouped: List[List[OcrWord]] = []
    centers: List[float] = []

    for word in sorted(words, key=lambda item: (item.center_y, item.left)):
        best_index: Optional[int] = None
        best_distance = row_threshold
        for index, center in enumerate(centers):
            distance = abs(word.center_y - center)
            if distance <= best_distance:
                best_index = index
                best_distance = distance

        if best_index is None:
            grouped.append([word])
            centers.append(word.center_y)
            continue

        grouped[best_index].append(word)
        centers[best_index] = _median([item.center_y for item in grouped[best_index]])

    return [sorted(row, key=lambda item: item.left) for row in grouped]


def _segments_for_line(words: Sequence[OcrWord], gap_threshold: float) -> List[CellSegment]:
    if not words:
        return []

    segments: List[CellSegment] = []
    current = [words[0]]
    for word in words[1:]:
        gap = word.left - current[-1].right
        if gap > gap_threshold:
            segments.append(_segment(current))
            current = [word]
        else:
            current.append(word)

    segments.append(_segment(current))
    return segments


def _segment(words: Sequence[OcrWord]) -> CellSegment:
    return CellSegment(
        text=" ".join(word.text for word in words),
        left=min(word.left for word in words),
        top=min(word.top for word in words),
        right=max(word.right for word in words),
        bottom=max(word.top + word.height for word in words),
    )


def _cell_gap_threshold(words: Sequence[OcrWord]) -> float:
    median_height = _median([word.height for word in words])
    return max(12.0, median_height * 1.25)


def _column_positions(segments: Sequence[CellSegment]) -> List[float]:
    widths = [segment.width for segment in segments if segment.width > 0]
    threshold = max(16.0, _median(widths) * 0.45)
    columns: List[List[float]] = []

    for left in sorted(segment.left for segment in segments):
        if not columns or abs(left - _median(columns[-1])) > threshold:
            columns.append([float(left)])
            continue
        columns[-1].append(float(left))

    return [_median(column) for column in columns]


def _nearest_column(left: int, columns: Sequence[float]) -> int:
    return min(range(len(columns)), key=lambda index: abs(left - columns[index]))


def _trim_empty_edge_columns(rows: Sequence[Sequence[str]]) -> List[List[str]]:
    if not rows:
        return []

    first = 0
    last = max(len(row) for row in rows) - 1

    while first <= last and all(first >= len(row) or not row[first].strip() for row in rows):
        first += 1
    while last >= first and all(last >= len(row) or not row[last].strip() for row in rows):
        last -= 1

    trimmed = [list(row[first : last + 1]) for row in rows]
    if max(len(row) for row in trimmed) < 2:
        raise ParseError("image table must have at least two columns")
    return trimmed


def _median(values: Iterable[float]) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return float(median(collected))


def _int(value: Optional[str]) -> int:
    if value is None:
        raise ValueError("missing integer")
    return int(float(value))


def _float(value: Optional[str], *, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)
