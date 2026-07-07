import unittest

from slack_table.core import ParseError, format_table, format_tsv, parse_table, render


class CoreTests(unittest.TestCase):
    def test_renders_markdown_as_tsv_for_slack_native_tables(self):
        text = """
        | Header A | Header B |
        | --- | --- |
        | Data 1A | Data 1B |
        | Data 2A | Data 2B |
        """

        self.assertEqual(
            render(text),
            "Header A\tHeader B\nData 1A\tData 1B\nData 2A\tData 2B",
        )

    def test_format_table_is_native_tsv(self):
        table = parse_table("Name,Count\nAlpha,12\nBeta,1000\n")

        self.assertEqual(format_table(table), "Name\tCount\nAlpha\t12\nBeta\t1000")

    def test_formats_tsv_input_without_code_block_changes(self):
        text = "Name\tCount\nAlpha\t12\n"

        self.assertEqual(format_tsv(parse_table(text)), "Name\tCount\nAlpha\t12")

    def test_parses_escaped_markdown_pipes(self):
        table = parse_table(
            """
            | Key | Value |
            | --- | --- |
            | A | B\\|C |
            """,
            "markdown",
        )

        self.assertEqual(table.rows[1], ["A", "B|C"])

    def test_auto_detects_simple_pipe_rows(self):
        self.assertEqual(
            render("Name | Count\nAlpha | 12\n"),
            "Name\tCount\nAlpha\t12",
        )

    def test_rejects_empty_input(self):
        with self.assertRaises(ParseError):
            parse_table("")


if __name__ == "__main__":
    unittest.main()
