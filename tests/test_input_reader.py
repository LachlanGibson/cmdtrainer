import sys
from typing import Any

import cmdtrainer.input_reader as input_reader


def test_readkey_flushes_stdout_before_reading_key(monkeypatch: Any) -> None:
    """readkey must flush pending menu output before blocking on the keypress.

    Menus print without an explicit flush and call readkey with an empty prompt;
    without a flush here, a buffered stdout can leave the menu invisible while
    the key read blocks, so the app appears frozen until later output happens to
    flush the buffer. This is a regression guard for that freeze.
    """
    events: list[str] = []

    class RecordingStdout:
        def write(self, text: str) -> int:
            return len(text)

        def flush(self) -> None:
            events.append("flush")

    monkeypatch.setattr(sys, "stdout", RecordingStdout())
    monkeypatch.setattr(input_reader, "_getch", lambda: events.append("getch") or "x")

    result = input_reader.TerminalInputReader().readkey("")

    assert result == "x"
    # The flush must happen before the blocking key read, not after.
    assert events == ["flush", "getch"]
