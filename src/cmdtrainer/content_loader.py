"""Load declarative module content from bundled JSON resources."""

from __future__ import annotations

import json
import shlex
from importlib import resources
from pathlib import Path
from typing import Any

from .models import Card, Lesson, Module

CONTENT_PACKAGE = "cmdtrainer.content.modules"


def _card_from_dict(module_id: str, lesson_id: str, raw: dict[str, Any]) -> Card:
    """Build a card from raw JSON content."""
    answers = [str(value).strip() for value in raw.get("answers", []) if str(value).strip()]
    if not answers:
        raise ValueError(f"Card '{raw.get('id', '<unknown>')}' has no valid answers.")

    command = str(raw.get("command", "")).strip()
    if not command:
        command = _infer_command(answers[0])

    raw_tested_flags = raw.get("tested_flags", [])
    if raw_tested_flags:
        tested_flags = sorted({str(flag).strip() for flag in raw_tested_flags if str(flag).strip()})
    else:
        tested_flags = _infer_flags(answers)

    return Card(
        id=str(raw["id"]),
        module_id=module_id,
        lesson_id=lesson_id,
        prompt=str(raw["prompt"]),
        answers=answers,
        explanation=str(raw.get("explanation", "")),
        command=command,
        tested_flags=tested_flags,
    )


def _lesson_from_dict(module_id: str, raw: dict[str, Any]) -> Lesson:
    """Build a lesson from raw JSON content."""
    lesson_id = str(raw["id"])
    cards = [_card_from_dict(module_id, lesson_id, item) for item in raw.get("cards", [])]
    return Lesson(id=lesson_id, title=str(raw["title"]), order=int(raw.get("order", 0)), cards=cards)


def _module_from_dict(raw: dict[str, Any]) -> Module:
    """Build a module from raw JSON content."""
    module_id = str(raw["id"])
    lessons = [_lesson_from_dict(module_id, lesson) for lesson in raw.get("lessons", [])]
    lessons.sort(key=lambda item: item.order)
    return Module(
        id=module_id,
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        content_version=int(raw.get("content_version", 1)),
        prerequisites=[str(item) for item in raw.get("prerequisites", [])],
        lessons=lessons,
    )


def load_modules() -> dict[str, Module]:
    """Load bundled modules."""
    modules: dict[str, Module] = {}
    for entry in resources.files(CONTENT_PACKAGE).iterdir():
        if entry.name.endswith(".json"):
            raw = json.loads(entry.read_text(encoding="utf-8-sig"))
            module = _module_from_dict(raw)
            if module.id in modules:
                raise ValueError(f"Duplicate module id: {module.id}")
            modules[module.id] = module
    _validate_module_dependencies(modules)
    _validate_unique_card_ids(modules)
    return modules


def load_modules_from_dir(path: Path) -> dict[str, Module]:
    """Load modules from directory for tests/tools."""
    modules: dict[str, Module] = {}
    for file_path in sorted(path.glob("*.json")):
        raw = json.loads(file_path.read_text(encoding="utf-8-sig"))
        module = _module_from_dict(raw)
        if module.id in modules:
            raise ValueError(f"Duplicate module id: {module.id}")
        modules[module.id] = module
    _validate_module_dependencies(modules)
    _validate_unique_card_ids(modules)
    return modules


def _validate_module_dependencies(modules: dict[str, Module]) -> None:
    """Validate prerequisites exist and dependency graph has no cycles."""
    for module in modules.values():
        for prerequisite in module.prerequisites:
            if prerequisite not in modules:
                raise ValueError(f"Module '{module.id}' has unknown prerequisite '{prerequisite}'.")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_id: str, path: list[str]) -> None:
        if module_id in visited:
            return
        if module_id in visiting:
            cycle_start = path.index(module_id)
            cycle_path = path[cycle_start:] + [module_id]
            raise ValueError(f"Circular module dependency detected: {' -> '.join(cycle_path)}")

        visiting.add(module_id)
        path.append(module_id)
        module = modules[module_id]
        for prerequisite in module.prerequisites:
            visit(prerequisite, path)
        path.pop()
        visiting.remove(module_id)
        visited.add(module_id)

    for module_id in modules:
        visit(module_id, [])


def _validate_unique_card_ids(modules: dict[str, Module]) -> None:
    """Validate that card IDs are globally unique across all modules."""
    seen: dict[str, str] = {}
    for module in modules.values():
        for lesson in module.lessons:
            for card in lesson.cards:
                previous = seen.get(card.id)
                if previous is not None:
                    raise ValueError(f"Duplicate card id: {card.id} (in {previous} and {module.id})")
                seen[card.id] = module.id


def _infer_command(answer: str) -> str:
    """Infer a normalized command path from one answer string."""
    tokens = _tokenize(answer)
    if not tokens:
        return ""

    first = tokens[0]
    if first == "docker":
        if len(tokens) > 2 and tokens[1] == "compose":
            return "docker compose " + tokens[2]
        if len(tokens) > 1 and not tokens[1].startswith("-"):
            return "docker " + tokens[1]
        return "docker"

    if first in {"git", "apt"}:
        if len(tokens) > 1 and not tokens[1].startswith("-"):
            return f"{first} {tokens[1]}"
        return first

    return first


def _infer_flags(answers: list[str]) -> list[str]:
    """Infer canonical tested flags from accepted answers."""
    flags: set[str] = set()
    for answer in answers:
        for token in _tokenize(answer):
            if token == "--":
                continue
            if token.startswith("--") and len(token) > 2:
                flags.add(token.split("=", 1)[0])
                continue
            if token.startswith("-") and len(token) > 1:
                if len(token) > 2 and token[1:].isalpha():
                    for char in token[1:]:
                        flags.add(f"-{char}")
                else:
                    flags.add(token[:2] if len(token) > 2 else token)
    return sorted(flags)


def _tokenize(command: str) -> tuple[str, ...]:
    """Tokenize shell-like command string for metadata inference."""
    try:
        tokens = shlex.split(command.strip(), posix=True)
    except ValueError:
        return ()
    return tuple(tokens)
