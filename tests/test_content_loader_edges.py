import json
from pathlib import Path

from cmdtrainer import content_loader
from cmdtrainer.content_loader import load_modules_from_dir


def test_card_without_answers_raises_value_error(tmp_path: Path) -> None:
    root = tmp_path / "loader-empty-answers"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "m",
        "title": "M",
        "description": "",
        "prerequisites": [],
        "lessons": [{"id": "l", "title": "L", "order": 1, "cards": [{"id": "c", "prompt": "P", "answers": []}]}],
    }
    (root / "m.json").write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_modules_from_dir(root)
        raise AssertionError("Expected ValueError for card with empty answers.")
    except ValueError as exc:
        assert "no valid answers" in str(exc)


def test_duplicate_module_id_in_dir_raises(tmp_path: Path) -> None:
    root = tmp_path / "loader-dup-id"
    root.mkdir(parents=True, exist_ok=True)
    first = {"id": "same", "title": "A", "prerequisites": [], "lessons": []}
    second = {"id": "same", "title": "B", "prerequisites": [], "lessons": []}
    (root / "a.json").write_text(json.dumps(first), encoding="utf-8")
    (root / "b.json").write_text(json.dumps(second), encoding="utf-8")

    try:
        load_modules_from_dir(root)
        raise AssertionError("Expected ValueError for duplicate module ids.")
    except ValueError as exc:
        assert "Duplicate module id" in str(exc)


def test_duplicate_card_id_across_modules_raises(tmp_path: Path) -> None:
    root = tmp_path / "loader-dup-card-id"
    root.mkdir(parents=True, exist_ok=True)
    first = {
        "id": "m1",
        "title": "M1",
        "prerequisites": [],
        "lessons": [
            {"id": "l1", "title": "L1", "order": 1, "cards": [{"id": "same", "prompt": "P1", "answers": ["pwd"]}]}
        ],
    }
    second = {
        "id": "m2",
        "title": "M2",
        "prerequisites": [],
        "lessons": [
            {"id": "l2", "title": "L2", "order": 1, "cards": [{"id": "same", "prompt": "P2", "answers": ["ls"]}]}
        ],
    }
    (root / "a.json").write_text(json.dumps(first), encoding="utf-8")
    (root / "b.json").write_text(json.dumps(second), encoding="utf-8")

    try:
        load_modules_from_dir(root)
        raise AssertionError("Expected ValueError for duplicate card ids.")
    except ValueError as exc:
        assert "Duplicate card id" in str(exc)


def test_infer_command_branches() -> None:
    assert content_loader._infer_command("docker --help") == "docker"
    assert content_loader._infer_command("docker ps -a") == "docker ps"
    assert content_loader._infer_command("docker compose up -d") == "docker compose up"
    assert content_loader._infer_command("git --version") == "git"
    assert content_loader._infer_command("git status -s") == "git status"
    assert content_loader._infer_command("apt update") == "apt update"
    assert content_loader._infer_command("npm install -D vitest") == "npm"
    assert content_loader._infer_command("node --test") == "node"
    assert content_loader._infer_command('"') == ""


def test_infer_flags_and_tokenize_edge_cases() -> None:
    flags = content_loader._infer_flags(["cmd -- --color=auto -xz -p22 -n value", "cmd --long=1 --long=2"])
    assert "--color" in flags
    assert "--long" in flags
    assert "-x" in flags
    assert "-z" in flags
    assert "-p" in flags
    assert "-n" in flags
    assert content_loader._tokenize('"') == ()
