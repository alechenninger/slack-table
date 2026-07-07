"""Small cross-platform clipboard adapter using common system commands."""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


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

