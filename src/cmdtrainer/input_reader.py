"""Input reader abstraction for single-keypress and line-input modes."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Protocol


class InputReader(Protocol):
    """Protocol for reading user input in two modes."""

    def readline(self, prompt: str) -> str:
        """Read a full line of text terminated by Enter."""
        ...

    def readkey(self, prompt: str) -> str:
        """Read a single keypress without requiring Enter.

        Prints *prompt* (if non-empty) before waiting.
        Returns the pressed character lowercased, or an empty string for
        unrecognised special keys (arrow keys, function keys, etc.).
        """
        ...


class TerminalInputReader:  # pragma: no cover
    """Real terminal implementation of InputReader."""

    def readline(self, prompt: str) -> str:
        """Read a full line from stdin."""
        return input(prompt)

    def readkey(self, prompt: str) -> str:
        """Read a single keypress from the terminal without echo."""
        if prompt:
            print(prompt, end="", flush=True)
        # Flush any pending menu output before blocking on the hidden keypress
        # read. Menus print with `print` (no explicit flush) and call this with
        # an empty prompt, so without this a buffered stdout can leave the menu
        # invisible while `_getch` blocks — the app appears frozen until later
        # output happens to flush the buffer.
        sys.stdout.flush()
        return _getch()


def _getch() -> str:  # pragma: no cover
    """Read one character from the terminal without Enter or echo."""
    if sys.platform == "win32":
        import msvcrt

        ch: str = msvcrt.getwch()  # type: ignore[attr-defined]
        if ch in ("\x00", "\xe0"):
            # Two-byte special key (arrows, F-keys) — discard second byte.
            msvcrt.getwch()  # type: ignore[attr-defined]
            return ""
        return ch.lower()
    else:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                # Escape sequence (arrow keys etc.) — consume and discard.
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    sys.stdin.read(1)
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        sys.stdin.read(1)
                return ""
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


class FakeInputReader:
    """Test double that pops responses from a shared iterator.

    Both *readline* and *readkey* draw from the same sequence so tests
    can describe the full interaction as a flat list of expected inputs
    without caring which call uses which mode.
    """

    def __init__(self, responses: Iterator[str]) -> None:
        """Store the response iterator."""
        self._responses = responses

    def readline(self, prompt: str) -> str:
        """Return the next response (ignores prompt)."""
        return next(self._responses)

    def readkey(self, prompt: str) -> str:
        """Return the next response (ignores prompt)."""
        return next(self._responses)
