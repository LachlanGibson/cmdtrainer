import json
from pathlib import Path

from cmdtrainer.content_loader import load_modules, load_modules_from_dir


def test_load_modules_contains_base() -> None:
    modules = load_modules()
    assert "base-linux" in modules
    assert modules["apt"].prerequisites == ["base-linux"]
    assert modules["node"].prerequisites == ["base-linux"]
    assert modules["npm"].prerequisites == ["node"]
    assert modules["npm-workspaces"].prerequisites == ["npm"]
    assert modules["node-release"].prerequisites == ["git", "npm"]
    assert modules["docker-context"].prerequisites == ["docker", "ssh"]
    assert modules["http-clients"].prerequisites == ["network-basics"]
    assert modules["base-linux"].content_version == 1
    assert modules["base-linux"].lessons[0].cards[0].command == "pwd"


def test_load_modules_from_dir(tmp_path: Path) -> None:
    root = tmp_path / "loader"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "m",
        "title": "M",
        "description": "D",
        "content_version": 3,
        "prerequisites": [],
        "lessons": [
            {
                "id": "l",
                "title": "L",
                "order": 1,
                "cards": [
                    {
                        "id": "c",
                        "prompt": "P",
                        "answers": ["ls -la"],
                        "explanation": "E",
                    }
                ],
            }
        ],
    }
    (root / "m.json").write_text(json.dumps(payload), encoding="utf-8")

    modules = load_modules_from_dir(root)
    assert modules["m"].lessons[0].cards[0].id == "c"
    assert modules["m"].content_version == 3
    assert modules["m"].lessons[0].cards[0].command == "ls"
    assert modules["m"].lessons[0].cards[0].tested_flags == ["-a", "-l"]


def test_load_modules_from_dir_rejects_circular_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "loader-cycle"
    root.mkdir(parents=True, exist_ok=True)
    a = {
        "id": "a",
        "title": "A",
        "description": "",
        "prerequisites": ["b"],
        "lessons": [],
    }
    b = {
        "id": "b",
        "title": "B",
        "description": "",
        "prerequisites": ["a"],
        "lessons": [],
    }
    (root / "a.json").write_text(json.dumps(a), encoding="utf-8")
    (root / "b.json").write_text(json.dumps(b), encoding="utf-8")

    try:
        load_modules_from_dir(root)
        raise AssertionError("Expected a ValueError for circular dependencies.")
    except ValueError as exc:
        assert "Circular module dependency" in str(exc)


def test_load_modules_from_dir_rejects_unknown_prerequisite(tmp_path: Path) -> None:
    root = tmp_path / "loader-missing-prereq"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "m",
        "title": "M",
        "description": "",
        "prerequisites": ["does-not-exist"],
        "lessons": [],
    }
    (root / "m.json").write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_modules_from_dir(root)
        raise AssertionError("Expected a ValueError for unknown prerequisites.")
    except ValueError as exc:
        assert "unknown prerequisite" in str(exc)
