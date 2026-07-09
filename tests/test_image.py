import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from slack_table.core import ParseError
from slack_table.image import OcrWord, _words_to_table_rows, parse_image_table


TESSERACT_TSV = """level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext
1\t1\t0\t0\t0\t0\t0\t0\t300\t100\t-1\t
5\t1\t1\t1\t1\t1\t10\t10\t35\t10\t95\tName
5\t1\t1\t1\t1\t2\t120\t10\t40\t10\t94\tCount
5\t1\t1\t1\t2\t1\t10\t40\t35\t10\t96\tAlpha
5\t1\t1\t1\t2\t2\t120\t40\t12\t10\t93\t12
"""


class ImageTests(unittest.TestCase):
    def test_extracts_rows_with_tesseract_command(self):
        def fake_run(command, capture_output, check, text, timeout):
            self.assertEqual(command[0], "tesseract")
            self.assertTrue(command[1].endswith("table.png"))
            self.assertEqual(command[2:], ["-", "-l", "eng", "--psm", "6", "tsv"])
            self.assertTrue(capture_output)
            self.assertFalse(check)
            self.assertTrue(text)
            self.assertEqual(timeout, 30)
            return subprocess.CompletedProcess(command, 0, stdout=TESSERACT_TSV, stderr="")

        with mock.patch("slack_table.image.shutil.which", return_value="/usr/bin/tesseract"):
            with mock.patch("slack_table.image.subprocess.run", side_effect=fake_run):
                with tempfile.TemporaryDirectory() as tempdir:
                    image_path = Path(tempdir) / "table.png"
                    image_path.write_bytes(b"fake png data")

                    table = parse_image_table(image_path, engine="tesseract")

        self.assertEqual(table.rows, [["Name", "Count"], ["Alpha", "12"]])
        self.assertEqual(table.source_format, "image")

    def test_reconstructs_multi_word_cells_from_word_boxes(self):
        rows = _words_to_table_rows(
            [
                OcrWord("First", 10, 10, 28, 10, 95),
                OcrWord("Name", 43, 10, 30, 10, 95),
                OcrWord("Score", 140, 10, 34, 10, 95),
                OcrWord("Ada", 10, 40, 24, 10, 95),
                OcrWord("Lovelace", 39, 40, 58, 10, 95),
                OcrWord("100", 140, 40, 22, 10, 95),
            ]
        )

        self.assertEqual(rows, [["First Name", "Score"], ["Ada Lovelace", "100"]])

    def test_missing_api_key_is_not_required(self):
        with self.assertRaisesRegex(ParseError, "image file not found"):
            parse_image_table("missing.png", engine="tesseract")

    def test_rejects_non_image_file_type(self):
        with tempfile.TemporaryDirectory() as tempdir:
            image_path = Path(tempdir) / "table.txt"
            image_path.write_text("not an image")

            with self.assertRaisesRegex(ParseError, "unsupported image type"):
                parse_image_table(image_path, engine="tesseract")

    def test_missing_local_ocr_reports_install_options(self):
        with tempfile.TemporaryDirectory() as tempdir:
            image_path = Path(tempdir) / "table.png"
            image_path.write_bytes(b"fake png data")

            with mock.patch("slack_table.image.shutil.which", return_value=None):
                with self.assertRaisesRegex(ParseError, "tesserocr package or the tesseract command"):
                    parse_image_table(image_path, engine="tesseract")

    def test_tesseract_error_message_is_surfaced(self):
        def fake_run(command, capture_output, check, text, timeout):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="bad image")

        with mock.patch("slack_table.image.shutil.which", return_value="/usr/bin/tesseract"):
            with mock.patch("slack_table.image.subprocess.run", side_effect=fake_run):
                with tempfile.TemporaryDirectory() as tempdir:
                    image_path = Path(tempdir) / "table.png"
                    image_path.write_bytes(b"fake png data")

                    with self.assertRaisesRegex(ParseError, "bad image"):
                        parse_image_table(image_path, engine="tesseract")


if __name__ == "__main__":
    unittest.main()
