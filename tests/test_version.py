from pathlib import Path

import cmdtrainer


def _project_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    in_project = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project and stripped.startswith('version = "'):
            return stripped.split('"', 2)[1]
    raise AssertionError("Could not find [project].version in pyproject.toml")


def test_package_version_matches_pyproject() -> None:
    assert cmdtrainer.__version__ == _project_version()
