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

    def test_auto_detects_cursor_canvas_wrapped_tsv(self):
        text = (
            "Workload\tSystem A\tSystem B\tWinner\tDelta\n"
            "Scenario A\n"
            "10.0 ops/s \u00b7 100.0 ms/op\t20.0 ops/s \u00b7 50.0 ms/op\t\n"
            "2.0x faster\n"
            "Scenario B\n"
            "8.0 ops/s \u00b7 125.0 ms/op\t4.0 ops/s \u00b7 250.0 ms/op\t\n"
            "2.0x faster\n"
        )

        self.assertEqual(
            render(text),
            "Workload\tSystem A\tSystem B\tWinner\tDelta\n"
            "Scenario A\t10.0 ops/s \u00b7 100.0 ms/op\t"
            "20.0 ops/s \u00b7 50.0 ms/op\t\t2.0x faster\n"
            "Scenario B\t8.0 ops/s \u00b7 125.0 ms/op\t"
            "4.0 ops/s \u00b7 250.0 ms/op\t\t2.0x faster",
        )

    def test_auto_detects_single_cell_wrapped_tsv_rows(self):
        text = (
            "Scenario\tp50\tmean\tp95\n"
            "Scenario A\n"
            "2.2 ms\n"
            "2.6 ms\n"
            "5.5 ms\n"
            "Scenario B\n"
            "2.0 ms\n"
            "2.1 ms\n"
            "2.6 ms\n"
            "Scenario C\n"
            "3.1 ms\n"
            "3.3 ms\n"
            "5.3 ms\n"
        )

        self.assertEqual(
            render(text),
            "Scenario\tp50\tmean\tp95\n"
            "Scenario A\t2.2 ms\t2.6 ms\t5.5 ms\n"
            "Scenario B\t2.0 ms\t2.1 ms\t2.6 ms\n"
            "Scenario C\t3.1 ms\t3.3 ms\t5.3 ms",
        )

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
