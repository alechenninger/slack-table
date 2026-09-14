import unittest

from slack_table.core import (
    AmbiguousColumnsError,
    ParseError,
    Table,
    format_markdown,
    format_table,
    format_tsv,
    parse_table,
    render,
)


class CoreTests(unittest.TestCase):
    def test_renders_padded_markdown(self):
        self.assertEqual(
            render("Name,Count\nAlpha,12\nBeta,1000", output_format="markdown"),
            "| Name  | Count |\n| ----- | ----- |\n| Alpha | 12    |\n| Beta  | 1000  |",
        )

    def test_markdown_sizes_each_column_to_its_longest_header_or_body_cell(self):
        table = Table([
            ["Description", "Owner", "ID"],
            ["Short", "Al", "1"],
            ["Task", "Alexandra", "42"],
        ])

        self.assertEqual(
            format_markdown(table),
            "| Description | Owner     | ID  |\n"
            "| ----------- | --------- | --- |\n"
            "| Short       | Al        | 1   |\n"
            "| Task        | Alexandra | 42  |",
        )

    def test_markdown_keeps_short_and_empty_columns_at_least_three_characters_wide(self):
        table = Table([["A", "", "C"], ["", "", "xy"], ["z", "", ""]])

        self.assertEqual(
            format_markdown(table),
            "| A   |     | C   |\n"
            "| --- | --- | --- |\n"
            "|     |     | xy  |\n"
            "| z   |     |     |",
        )

    def test_markdown_normalizes_ragged_rows_and_escapes_cells(self):
        self.assertEqual(
            format_markdown(Table([["A", "B"], ["x|y", "a\nb"], ["z"]])),
            "| A    | B   |\n| ---- | --- |\n| x\\|y | a b |\n| z    |     |",
        )
        self.assertEqual(
            format_markdown(Table([["A", "B"], ["\\", "x"]])),
            "| A   | B   |\n| --- | --- |\n| \\\\  | x   |",
        )

    def test_markdown_header_only(self):
        self.assertEqual(format_markdown(Table([["A", "B"]])), "| A   | B   |\n| --- | --- |")

    def test_markdown_rejects_empty_table(self):
        with self.assertRaises(ParseError):
            format_markdown(Table([]))

    def test_rejects_unknown_output_format(self):
        with self.assertRaisesRegex(ParseError, "unknown output format"):
            render("A,B", output_format="invalid")

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

    def test_auto_detects_blank_line_separated_cells(self):
        text = """Component

Organization

Purpose

release-coordinator

example-labs

Coordinates staged releases, pre-deployment checks, and post-deployment checks

artifact-catalog

example-labs

Tracks deployable artifact versions

workspace-provisioner

example-labs

Creates workspaces and assigns them to groups

access-broker

example-labs

Manages credentials used during workspace provisioning"""

        self.assertEqual(
            render(text, columns=3),
            "Component\tOrganization\tPurpose\n"
            "release-coordinator\texample-labs\t"
            "Coordinates staged releases, pre-deployment checks, and post-deployment checks\n"
            "artifact-catalog\texample-labs\tTracks deployable artifact versions\n"
            "workspace-provisioner\texample-labs\tCreates workspaces and assigns them to groups\n"
            "access-broker\texample-labs\tManages credentials used during workspace provisioning",
        )

        with self.assertRaises(AmbiguousColumnsError) as raised:
            parse_table(text)
        self.assertEqual(raised.exception.candidates, [3, 5])

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
