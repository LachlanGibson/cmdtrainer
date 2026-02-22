"""cmdtrainer package."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

__all__ = ["__version__"]


def _version_from_pyproject() -> str | None:
    """Best-effort version lookup from local pyproject.toml for source runs."""
    for base in Path(__file__).resolve().parents:
        pyproject = base / "pyproject.toml"
        if not pyproject.exists():
            continue
        text = pyproject.read_text(encoding="utf-8")
        in_project = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_project = stripped == "[project]"
                continue
            if not in_project:
                continue
            match = re.match(r'^version\s*=\s*"([^"]+)"\s*$', stripped)
            if match:
                return match.group(1)
    return None


_project_version = _version_from_pyproject()
if _project_version is not None:
    __version__ = _project_version
else:
    try:
        __version__ = version("cmdtrainer")
    except PackageNotFoundError:
        __version__ = "0+unknown"
