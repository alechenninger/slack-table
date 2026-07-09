import subprocess
import unittest
from pathlib import Path
from unittest import mock

from slack_table import clipboard


class ClipboardTests(unittest.TestCase):
    def test_read_image_writes_macos_clipboard_png_with_osascript(self):
        calls = []

        def fake_run(command, check, stdout, stderr, text):
            calls.append(command)
            self.assertTrue(check)
            self.assertEqual(stdout, subprocess.PIPE)
            self.assertEqual(stderr, subprocess.PIPE)
            self.assertTrue(text)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with mock.patch("slack_table.clipboard.platform.system", return_value="Darwin"):
            with mock.patch("slack_table.clipboard.shutil.which", return_value="/usr/bin/osascript"):
                with mock.patch("slack_table.clipboard.subprocess.run", side_effect=fake_run):
                    clipboard.read_image(Path("/tmp/table.png"))

        command = calls[0]
        self.assertEqual(command[0], "osascript")
        self.assertIn("set imageData to the clipboard as «class PNGf»", command)
        self.assertEqual(command[-1], "/tmp/table.png")

    def test_read_image_rejects_unsupported_os(self):
        with mock.patch("slack_table.clipboard.platform.system", return_value="Linux"):
            with self.assertRaisesRegex(clipboard.ClipboardError, "only supported on macOS"):
                clipboard.read_image("/tmp/table.png")


if __name__ == "__main__":
    unittest.main()
