"""Module entrypoint for `python -m cmdtrainer`."""

from __future__ import annotations

from .main import main_entry


def main() -> None:
    """Run the CLI."""
    main_entry()


if __name__ == "__main__":  # pragma: no cover
    main()
