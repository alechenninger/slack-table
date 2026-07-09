"""Small cross-platform clipboard adapter using common system commands."""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union


class ClipboardError(RuntimeError):
    """Raised when no supported clipboard command is available or usable."""


@dataclass(frozen=True)
class ClipboardCommands:
    read: List[str]
    write: List[str]


def _detect_commands() -> Optional[ClipboardCommands]:
    system = platform.system().lower()

    if system == "darwin" and shutil.which("pbpaste") and shutil.which("pbcopy"):
        return ClipboardCommands(["pbpaste"], ["pbcopy"])

    if system == "windows":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            return ClipboardCommands(
                [powershell, "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                [powershell, "-NoProfile", "-Command", "Set-Clipboard"],
            )

    if shutil.which("wl-paste") and shutil.which("wl-copy"):
        return ClipboardCommands(["wl-paste", "--no-newline"], ["wl-copy"])

    if shutil.which("xclip"):
        return ClipboardCommands(
            ["xclip", "-selection", "clipboard", "-out"],
            ["xclip", "-selection", "clipboard", "-in"],
        )

    if shutil.which("xsel"):
        return ClipboardCommands(
            ["xsel", "--clipboard", "--output"],
            ["xsel", "--clipboard", "--input"],
        )

    return None


def available() -> bool:
    return _detect_commands() is not None


def image_supported() -> bool:
    return platform.system().lower() == "darwin" and shutil.which("osascript") is not None


def read() -> str:
    commands = _detect_commands()
    if commands is None:
        raise ClipboardError("no supported clipboard command found")

    try:
        result = subprocess.run(
            commands.read,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise ClipboardError(str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise ClipboardError(detail) from exc

    return result.stdout


def read_image(path: Union[str, Path]) -> None:
    if platform.system().lower() != "darwin":
        raise ClipboardError("clipboard image input is only supported on macOS")
    if not shutil.which("osascript"):
        raise ClipboardError("macOS clipboard image input requires osascript")

    output_path = str(Path(path))
    script = [
        "on run argv",
        "set outputPath to item 1 of argv",
        "set openedFile to missing value",
        "try",
        "set imageData to the clipboard as «class PNGf»",
        "set openedFile to open for access (POSIX file outputPath) with write permission",
        "set eof of openedFile to 0",
        "write imageData to openedFile",
        "close access openedFile",
        "on error errMsg number errNum",
        "try",
        "if openedFile is not missing value then close access openedFile",
        "end try",
        "error errMsg number errNum",
        "end try",
        "end run",
    ]
    command = ["osascript"]
    for statement in script:
        command.extend(["-e", statement])
    command.append(output_path)

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise ClipboardError(str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "no image found on clipboard"
        raise ClipboardError(detail) from exc


def signature() -> str:
    if platform.system().lower() == "darwin" and shutil.which("osascript"):
        try:
            result = subprocess.run(
                ["osascript", "-e", "clipboard info"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout
        except (OSError, subprocess.CalledProcessError):
            pass

    return read()


def write(text: str) -> None:
    commands = _detect_commands()
    if commands is None:
        raise ClipboardError("no supported clipboard command found")

    try:
        subprocess.run(
            commands.write,
            input=text,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise ClipboardError(str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise ClipboardError(detail) from exc
