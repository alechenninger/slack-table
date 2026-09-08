import argparse
import io
import unittest
from unittest import mock

from slack_table import cli


class CliTests(unittest.TestCase):
    def test_output_selection_from_stdin(self):
        for flags in ([], ["--output", "slack"], ["--output", "markdown"]):
            with self.subTest(flags=flags):
                with mock.patch.object(cli.sys, "stdin", io.StringIO("Name,Count\nAlpha,12")):
                    with mock.patch.object(cli.sys, "stdout", new_callable=io.StringIO) as stdout:
                        self.assertEqual(cli.main(flags), 0)
                expected = (
                    "| Name  | Count |\n| ----- | ----- |\n| Alpha | 12    |\n"
                    if "markdown" in flags else "Name\tCount\nAlpha\t12\n"
                )
                self.assertEqual(stdout.getvalue(), expected)

    def test_markdown_clipboard_workflows(self):
        for flags in (["--copy"], ["--clipboard"], ["--wait"]):
            with self.subTest(flags=flags):
                table = cli.Table([["A", "B"], ["1", "2"]])
                with mock.patch.object(cli, "_read_table", return_value=(table, flags != ["--copy"])):
                    with mock.patch.object(cli.clipboard, "write") as write:
                        with mock.patch.object(cli.sys, "stdout", new_callable=io.StringIO) as stdout:
                            self.assertEqual(cli.main([*flags, "--output", "markdown", "-q"]), 0)
                write.assert_called_once_with("| A   | B   |\n| --- | --- |\n| 1   | 2   |")
                self.assertEqual(stdout.getvalue(), "")

    def test_copy_writes_tsv_to_clipboard(self):
        args = argparse.Namespace(
            input="csv",
            output="slack",
            copy=True,
            quiet=True,
            files=[],
            clipboard=False,
            wait=False,
            image=None,
            image_engine="auto",
            image_lang="eng",
            image_psm=6,
        )

        with mock.patch.object(cli, "_build_parser") as build_parser:
            table = cli.Table([["Header A", "Header B"], ["Data 1A", "Data 1B"]], "csv")
            with mock.patch.object(cli, "_read_table", return_value=(table, False)):
                with mock.patch.object(cli.clipboard, "write") as write:
                    build_parser.return_value.parse_args.return_value = args

                    self.assertEqual(cli.main([]), 0)

        write.assert_called_once_with("Header A\tHeader B\nData 1A\tData 1B")

    def test_image_input_uses_image_extractor(self):
        args = argparse.Namespace(
            input="auto",
            output="slack",
            copy=False,
            quiet=True,
            files=[],
            clipboard=False,
            wait=False,
            image="table.png",
            image_engine="tesserocr",
            image_lang="eng+fra",
            image_psm=11,
        )

        with mock.patch.object(cli, "_build_parser") as build_parser:
            with mock.patch.object(cli, "parse_image_table") as parse_image_table:
                build_parser.return_value.parse_args.return_value = args
                parse_image_table.return_value = cli.Table([["Name", "Count"], ["Alpha", "12"]], "image")

                self.assertEqual(cli.main([]), 0)

        parse_image_table.assert_called_once_with(
            "table.png",
            engine="tesserocr",
            lang="eng+fra",
            psm=11,
        )

    def test_clipboard_image_is_used_when_clipboard_text_is_empty(self):
        args = argparse.Namespace(
            input="auto",
            copy=False,
            quiet=True,
            files=[],
            clipboard=True,
            wait=False,
            image=None,
            image_engine="tesseract",
            image_lang="eng",
            image_psm=6,
        )

        def fake_read_image(path):
            self.assertTrue(str(path).endswith("clipboard.png"))

        with mock.patch.object(cli.clipboard, "read", return_value=""):
            with mock.patch.object(cli.clipboard, "image_supported", return_value=True):
                with mock.patch.object(cli.clipboard, "read_image", side_effect=fake_read_image):
                    with mock.patch.object(cli, "parse_image_table") as parse_image_table:
                        parse_image_table.return_value = cli.Table([["Name", "Count"], ["Alpha", "12"]], "image")

                        table = cli._read_clipboard_table(args, require_image_support=True)

        self.assertEqual(table.rows, [["Name", "Count"], ["Alpha", "12"]])
        _, kwargs = parse_image_table.call_args
        self.assertEqual(kwargs, {"engine": "tesseract", "lang": "eng", "psm": 6})


if __name__ == "__main__":
    unittest.main()
