import argparse
import unittest
from unittest import mock

from slack_table import cli


class CliTests(unittest.TestCase):
    def test_copy_writes_tsv_to_clipboard(self):
        args = argparse.Namespace(
            input="csv",
            copy=True,
            quiet=True,
            files=[],
            clipboard=False,
            wait=False,
        )

        with mock.patch.object(cli, "_build_parser") as build_parser:
            with mock.patch.object(cli, "_read_input", return_value=("Header A,Header B\nData 1A,Data 1B\n", False)):
                with mock.patch.object(cli.clipboard, "write") as write:
                    build_parser.return_value.parse_args.return_value = args

                    self.assertEqual(cli.main([]), 0)

        write.assert_called_once_with("Header A\tHeader B\nData 1A\tData 1B")


if __name__ == "__main__":
    unittest.main()
