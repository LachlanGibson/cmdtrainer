from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _tmp_path_fixture() -> Iterator[Path]:
    """Provide per-test temporary directory path inside the workspace.

    This intentionally overrides pytest's builtin ``tmp_path`` fixture for this
    repository. In this environment, system temp locations and builtin tmp-path
    setup are not reliable, so tests keep temporary files under the project
    working directory at ``.tmp_pytest/``.
    """
    base = ROOT / ".tmp_pytest"
    base.mkdir(parents=True, exist_ok=True)
    path = base / str(uuid4())
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            next(base.iterdir())
        except StopIteration:
            base.rmdir()
        except FileNotFoundError:
            pass


tmp_path = pytest.fixture(name="tmp_path")(_tmp_path_fixture)
