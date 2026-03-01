"""Application service for profiles, modules, and spaced-repetition practice."""

from __future__ import annotations

import json
import random
import shlex
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from . import __version__
from .content_loader import load_modules
from .models import Card, Module
from .progress import SCHEMA_VERSION, Profile, ProgressStore

EXPORT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ModuleState:
    """Module state for one profile."""

    module: Module
    unlocked: bool
    started: bool
    completed: bool
    outdated: bool


@dataclass(frozen=True)
class CommandReference:
    """Aggregated command + tested flags metadata for module reference view."""

    command: str
    tested_flags: tuple[str, ...]


@dataclass(frozen=True)
class LessonReference:
    """Lesson metadata for module reference view."""

    lesson_id: str
    title: str
    order: int
    card_count: int
    command_count: int


@dataclass(frozen=True)
class LessonProgress:
    """Per-lesson progression summary."""

    lesson_id: str
    title: str
    order: int
    total_cards: int
    attempted_cards: int
    correct_cards: int


@dataclass(frozen=True)
class ModuleProgression:
    """Module progression summary with lesson breakdown."""

    module_id: str
    module_title: str
    stage: str
    total_cards: int
    attempted_cards: int
    correct_cards: int
    lessons: tuple[LessonProgress, ...]


@dataclass(frozen=True)
class QueueItem:
    """One scheduling queue row for display."""

    card_id: str
    module_id: str
    prompt: str
    due_at: str
    status: str
    streak: int
    spacing_score: float
    interval_minutes: int
    seen_count: int
    command: str


@dataclass(frozen=True)
class ProfileTransferSummary:
    """Summary emitted by profile export/import operations."""

    profile_id: int
    profile_name: str
    module_rows: int
    card_rows: int
    attempt_rows: int


class LearnService:
    """Coordinates profile state and learning flows."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize service with database path."""
        self.modules = load_modules()
        self.progress = ProgressStore(db_path)
        self._last_presented_card_id: dict[int, str] = {}

    def list_profiles(self) -> list[Profile]:
        """Return all profiles."""
        return self.progress.list_profiles()

    def create_profile(self, name: str) -> Profile:
        """Create profile by name."""
        return self.progress.create_profile(name.strip())

    def delete_profile(self, profile_id: int) -> bool:
        """Delete one profile by id."""
        return self.progress.delete_profile(profile_id)

    def export_profile(self, profile_id: int, export_path: Path | str) -> ProfileTransferSummary:
        """Export a profile and all progress state to a JSON file."""
        profile = self.progress.get_profile(profile_id)
        if profile is None:
            raise KeyError(profile_id)

        module_rows = self.progress.list_module_progress_rows(profile_id)
        card_rows = self.progress.list_card_progress_rows(profile_id)
        attempt_rows = self.progress.list_attempt_rows(profile_id)
        payload = {
            "format_version": EXPORT_FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "source": {
                "app_version": __version__,
                "schema_version": SCHEMA_VERSION,
            },
            "profile": {
                "name": profile.name,
            },
            "module_progress": module_rows,
            "card_progress": card_rows,
            "attempts": attempt_rows,
        }

        path = Path(export_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ProfileTransferSummary(
            profile_id=profile.id,
            profile_name=profile.name,
            module_rows=len(module_rows),
            card_rows=len(card_rows),
            attempt_rows=len(attempt_rows),
        )

    def import_profile(self, import_path: Path | str, profile_name: str | None = None) -> ProfileTransferSummary:
        """Import a profile export JSON file as a new profile."""
        path = Path(import_path)
        raw_obj: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_obj, dict):
            raise ValueError("Import file root must be a JSON object.")
        raw = cast(dict[str, object], raw_obj)

        version_raw: object = raw.get("format_version", 0)
        format_version = _coerce_int(version_raw)
        if format_version is None:
            raise ValueError("Import file has invalid format_version.")
        if format_version > EXPORT_FORMAT_VERSION:
            raise ValueError(
                f"Import file format version {format_version} is newer than supported {EXPORT_FORMAT_VERSION}."
            )

        target_name = (profile_name or "").strip()
        if not target_name:
            profile_section_obj = raw.get("profile")
            if isinstance(profile_section_obj, dict):
                profile_section = cast(dict[str, object], profile_section_obj)
                profile_name_raw: object = profile_section.get("name")
                if isinstance(profile_name_raw, str):
                    target_name = profile_name_raw.strip()
        if not target_name:
            raise ValueError("Could not determine profile name from import file.")

        now = datetime.now(UTC).isoformat()
        module_rows = _normalize_module_progress_rows(raw.get("module_progress"), now)
        card_rows = _normalize_card_progress_rows(raw.get("card_progress"), now)
        attempt_rows = _normalize_attempt_rows(raw.get("attempts"), now)

        profile = self.create_profile(target_name)
        self.progress.replace_profile_data(profile.id, module_rows, card_rows, attempt_rows)
        return ProfileTransferSummary(
            profile_id=profile.id,
            profile_name=profile.name,
            module_rows=len(module_rows),
            card_rows=len(card_rows),
            attempt_rows=len(attempt_rows),
        )

    def list_module_states(self, profile_id: int) -> list[ModuleState]:
        """Return module states sorted by module id."""
        completed = self.progress.completed_module_ids(profile_id)
        states: list[ModuleState] = []
        for module in sorted(self.modules.values(), key=lambda item: item.id):
            started, done, completed_version = self.progress.module_state(profile_id, module.id)
            prerequisites_met = all(dep in completed for dep in module.prerequisites)
            # Grandfather started/completed modules if prerequisites tighten in later content versions.
            unlocked = prerequisites_met or started or done
            completed_at_version = completed_version or 0
            outdated = done and completed_at_version < module.content_version
            states.append(
                ModuleState(module=module, unlocked=unlocked, started=started, completed=done, outdated=outdated)
            )
        return states

    def get_module(self, module_id: str) -> Module | None:
        """Get module by id."""
        return self.modules.get(module_id)

    def begin_module(self, profile_id: int, module_id: str) -> Module:
        """Mark module started and return module object."""
        module = self.modules[module_id]
        self.progress.mark_module_started(profile_id, module_id)
        return module

    def correct_card_ids_for_module(self, profile_id: int, module_id: str) -> set[str]:
        """Return card ids with at least one correct attempt for a module."""
        module = self.modules[module_id]
        card_ids = [card.id for lesson in module.lessons for card in lesson.cards]
        return self.progress.correct_card_ids(profile_id, card_ids)

    def list_module_command_references(self, module_id: str) -> list[CommandReference]:
        """Return unique commands in a module with aggregated tested flags."""
        module = self.modules[module_id]
        command_flags: dict[str, set[str]] = {}
        for lesson in module.lessons:
            for card in lesson.cards:
                flags = command_flags.setdefault(card.command, set())
                flags.update(card.tested_flags)

        references = [
            CommandReference(command=command, tested_flags=tuple(sorted(flags)))
            for command, flags in command_flags.items()
        ]
        references.sort(key=lambda item: item.command)
        return references

    def list_module_lesson_references(self, module_id: str) -> list[LessonReference]:
        """Return ordered lesson metadata for a module."""
        module = self.modules[module_id]
        references = [
            LessonReference(
                lesson_id=lesson.id,
                title=lesson.title,
                order=lesson.order,
                card_count=len(lesson.cards),
                command_count=len({card.command for card in lesson.cards}),
            )
            for lesson in sorted(module.lessons, key=lambda item: item.order)
        ]
        return references

    def get_module_progression(self, profile_id: int, module_id: str) -> ModuleProgression:
        """Return module progression based on attempted/correct cards."""
        module = self.modules[module_id]
        started, completed, completed_version = self.progress.module_state(profile_id, module_id)
        stage = "new"
        if completed:
            stage = "completed"
            if (completed_version or 0) < module.content_version:
                stage = "outdated"
        elif started:
            stage = "started"

        all_card_ids = [card.id for lesson in module.lessons for card in lesson.cards]
        attempted_card_ids = self.progress.attempted_card_ids(profile_id, all_card_ids)
        correct_card_ids = self.progress.correct_card_ids(profile_id, all_card_ids)

        lesson_rows: list[LessonProgress] = []
        for lesson in sorted(module.lessons, key=lambda item: item.order):
            lesson_card_ids = [card.id for card in lesson.cards]
            attempted = len([card_id for card_id in lesson_card_ids if card_id in attempted_card_ids])
            correct = len([card_id for card_id in lesson_card_ids if card_id in correct_card_ids])
            lesson_rows.append(
                LessonProgress(
                    lesson_id=lesson.id,
                    title=lesson.title,
                    order=lesson.order,
                    total_cards=len(lesson_card_ids),
                    attempted_cards=attempted,
                    correct_cards=correct,
                )
            )

        return ModuleProgression(
            module_id=module.id,
            module_title=module.title,
            stage=stage,
            total_cards=len(all_card_ids),
            attempted_cards=len(attempted_card_ids),
            correct_cards=len(correct_card_ids),
            lessons=tuple(lesson_rows),
        )

    def force_unlock_module_with_dependencies(self, profile_id: int, module_id: str) -> list[str]:
        """Force-complete a module and all prerequisite modules recursively."""
        if module_id not in self.modules:
            raise KeyError(module_id)

        visited: set[str] = set()
        order: list[str] = []

        def visit(current: str) -> None:
            if current in visited:
                return
            visited.add(current)
            module = self.modules[current]
            for prerequisite in module.prerequisites:
                visit(prerequisite)
            order.append(current)

        visit(module_id)
        for item in order:
            self.progress.mark_module_started(profile_id, item)
            self.progress.mark_module_completed(profile_id, item, self.modules[item].content_version)
        return order

    def practice_queue(self, profile_id: int, limit: int = 30) -> list[QueueItem]:
        """Return upcoming practice queue for eligible modules."""
        eligible_modules = self.progress.completed_module_ids(profile_id)
        if not eligible_modules:
            eligible_modules = self.progress.started_module_ids(profile_id)
        if not eligible_modules:
            return []

        now = datetime.now(UTC)
        items: list[tuple[datetime, QueueItem]] = []
        for module_id in sorted(eligible_modules):
            module = self.modules.get(module_id)
            if module is None:
                continue
            module_card_ids = [card.id for lesson in module.lessons for card in lesson.cards]
            correct_ids = self.progress.correct_card_ids(profile_id, module_card_ids)
            for lesson in module.lessons:
                for card in lesson.cards:
                    if card.id not in correct_ids:
                        continue
                    schedule = self.progress.get_card_schedule(profile_id, card.id)
                    if schedule is None:
                        item = QueueItem(
                            card_id=card.id,
                            module_id=module_id,
                            prompt=card.prompt,
                            due_at=now.isoformat(),
                            status="new",
                            streak=0,
                            spacing_score=0.0,
                            interval_minutes=0,
                            seen_count=0,
                            command=card.answers[0],
                        )
                        items.append((now, item))
                        continue
                    due_time = datetime.fromisoformat(schedule.due_at)
                    status = "due" if due_time <= now else "scheduled"
                    item = QueueItem(
                        card_id=card.id,
                        module_id=module_id,
                        prompt=card.prompt,
                        due_at=schedule.due_at,
                        status=status,
                        streak=schedule.streak,
                        spacing_score=schedule.spacing_score,
                        interval_minutes=schedule.interval_minutes,
                        seen_count=schedule.seen_count,
                        command=card.answers[0],
                    )
                    items.append((due_time, item))

        items.sort(key=lambda pair: pair[0])
        return [item for _, item in items[:limit]]

    def card_is_correct(self, card: Card, user_input: str) -> bool:
        """Validate user command against accepted card answers."""
        if _normalize_command(user_input) is None:
            return False
        user_variants = _normalize_command_variants(user_input)
        for answer in card.answers:
            if _normalize_command(answer) is None:
                continue
            expected_variants = _normalize_command_variants(answer)
            if expected_variants and not user_variants.isdisjoint(expected_variants):
                return True
        return False

    def record_answer(self, profile_id: int, card: Card, user_input: str) -> bool:
        """Record one card answer and return correctness."""
        correct = self.card_is_correct(card, user_input)
        self.progress.record_attempt(profile_id, card.id, user_input, correct)
        return correct

    def complete_module_if_mastered(self, profile_id: int, module: Module) -> bool:
        """Mark module complete when all cards have at least one correct attempt."""
        all_card_ids = [card.id for lesson in module.lessons for card in lesson.cards]
        for card_id in all_card_ids:
            schedule = self.progress.get_card_schedule(profile_id, card_id)
            if schedule is None or schedule.seen_count <= 0 or schedule.streak < 1:
                return False
        self.progress.mark_module_completed(profile_id, module.id, module.content_version)
        return True

    def due_cards(self, profile_id: int, limit: int = 10) -> list[Card]:
        """Return randomized due cards for spaced-repetition practice."""
        eligible_modules = self.progress.completed_module_ids(profile_id)
        if not eligible_modules:
            eligible_modules = self.progress.started_module_ids(profile_id)

        if not eligible_modules:
            return []

        now = datetime.now(UTC)
        due: list[Card] = []
        future: list[tuple[datetime, Card]] = []
        for module_id in eligible_modules:
            module = self.modules.get(module_id)
            if module is None:
                continue
            module_card_ids = [card.id for lesson in module.lessons for card in lesson.cards]
            correct_ids = self.progress.correct_card_ids(profile_id, module_card_ids)
            for lesson in module.lessons:
                for card in lesson.cards:
                    if card.id not in correct_ids:
                        continue
                    schedule = self.progress.get_card_schedule(profile_id, card.id)
                    if schedule is None:
                        due.append(card)
                        continue
                    due_at = datetime.fromisoformat(schedule.due_at)
                    if due_at <= now:
                        due.append(card)
                    else:
                        future.append((due_at, card))

        random.shuffle(due)
        if due:
            ordered_due = self._avoid_immediate_repeat(profile_id, due)
            selected = ordered_due[:limit]
            self._remember_last_presented(profile_id, selected)
            return selected

        future.sort(key=lambda item: item[0])
        ordered_future = self._avoid_immediate_repeat(profile_id, [item[1] for item in future])
        selected = ordered_future[:limit]
        self._remember_last_presented(profile_id, selected)
        return selected

    def _avoid_immediate_repeat(self, profile_id: int, cards: list[Card]) -> list[Card]:
        """Reorder cards to avoid showing the same card twice in a row when possible."""
        if len(cards) <= 1:
            return cards
        last_id = self._last_presented_card_id.get(profile_id)
        if last_id is None or cards[0].id != last_id:
            return cards
        for index in range(1, len(cards)):
            if cards[index].id != last_id:
                cards[0], cards[index] = cards[index], cards[0]
                break
        return cards

    def _remember_last_presented(self, profile_id: int, cards: list[Card]) -> None:
        """Remember the last card shown in the latest practice batch."""
        if cards:
            self._last_presented_card_id[profile_id] = cards[-1].id

    def close(self) -> None:
        """Close resources."""
        self.progress.close()

    def __del__(self) -> None:  # pragma: no cover
        """Best-effort cleanup for test/process teardown."""
        try:
            self.close()
        except Exception:
            pass


@dataclass(frozen=True)
class NormalizedCommand:
    """Canonical command shape for answer validation."""

    command: str
    options: tuple[tuple[str, str | None], ...]
    positionals: tuple[str, ...]


def _normalize_command(command: str) -> NormalizedCommand | None:
    """Return command with order-insensitive options and ordered positionals."""
    variants = _normalize_command_variants(command)
    if not variants:
        return None
    return min(variants, key=_normalized_command_sort_key)


def _normalize_command_variants(command: str) -> set[NormalizedCommand]:
    """Return all plausible normalized commands for ambiguous short-option forms."""
    stripped = command.strip()
    if not stripped:
        return set()
    try:
        tokens = shlex.split(stripped, posix=True)
    except ValueError:
        return set()
    if not tokens:
        return set()
    return _canonicalize_tokens_variants(tuple(token.strip() for token in tokens))


def _normalized_command_sort_key(
    command: NormalizedCommand,
) -> tuple[str, tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Return stable sort key for deterministic single-result normalization."""
    normalized_options = tuple((key, "" if value is None else value) for key, value in command.options)
    return (command.command, normalized_options, command.positionals)


def _canonicalize_tokens_variants(tokens: tuple[str, ...]) -> set[NormalizedCommand]:
    """Build canonical command structures from shell tokens, including ambiguous forms."""
    command = tokens[0]
    results: set[NormalizedCommand] = set()

    def walk(
        index: int,
        force_positionals: bool,
        options: tuple[tuple[str, str | None], ...],
        positionals: tuple[str, ...],
    ) -> None:
        if index >= len(tokens):
            normalized_options = tuple((_normalize_option_key(command, key), value) for key, value in options)
            sorted_options = tuple(
                sorted(normalized_options, key=lambda pair: (pair[0], "" if pair[1] is None else pair[1]))
            )
            results.add(NormalizedCommand(command=command, options=sorted_options, positionals=positionals))
            return

        token = tokens[index]

        if force_positionals:
            walk(index + 1, True, options, positionals + (token,))
            return

        if token == "--":
            walk(index + 1, True, options, positionals)
            return

        if token.startswith("--") and len(token) > 2:
            key, value, consumed = _parse_long_option(tokens, index)
            walk(index + consumed, False, options + ((key, value),), positionals)
            return

        if token.startswith("-") and len(token) > 1:
            for short_options, consumed in _parse_short_option_variants(command, tokens, index):
                walk(index + consumed, False, options + tuple(short_options), positionals)
            return

        walk(index + 1, False, options, positionals + (token,))

    walk(index=1, force_positionals=False, options=tuple(), positionals=tuple())
    return results


def _parse_long_option(tokens: tuple[str, ...], index: int) -> tuple[str, str | None, int]:
    """Parse one long option token and optional value."""
    token = tokens[index]
    if "=" in token:
        key, value = token.split("=", 1)
        return (key, value, 1)
    if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
        return (token, tokens[index + 1], 2)
    return (token, None, 1)


def _normalize_option_key(command: str, key: str) -> str:
    """Map equivalent option keys to one canonical form for a command."""
    if command == "npm" and key == "--workspace":
        return "-w"
    return key


def _parse_short_option_variants(
    command: str, tokens: tuple[str, ...], index: int
) -> list[tuple[list[tuple[str, str | None]], int]]:
    """Parse short options, including ambiguous split-value forms."""
    token = tokens[index]
    # Combined single-letter flags like `-la` and `-al` are equivalent.
    if len(token) > 2 and token[1:].isalpha():
        # npm: `-w` consumes workspace value, so bundles containing `w`
        # cannot be treated as order-insensitive short-flag sets.
        if command == "npm" and "w" in token[1:]:
            bundle = token[1:]
            options: list[tuple[str, str | None]] = []
            consumed = 1
            i = 0
            while i < len(bundle):
                flag = bundle[i]
                key = f"-{flag}"
                if flag == "w":
                    attached = bundle[i + 1 :]
                    if attached:
                        options.append((key, attached))
                        i = len(bundle)
                        continue
                    if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                        options.append((key, tokens[index + 1]))
                        consumed = 2
                    else:
                        options.append((key, None))
                    i += 1
                    continue
                options.append((key, None))
                i += 1
            return [(options, consumed)]

        flags = sorted(token[1:])
        return [([(f"-{flag}", None) for flag in flags], 1)]

    # Attached value form like `-p22`.
    if len(token) > 2:
        return [([(token[:2], token[2:])], 1)]

    if command == "npm" and token == "-w":
        if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
            return [([("-w", tokens[index + 1])], 2)]
        return [([("-w", None)], 1)]

    variants: list[tuple[list[tuple[str, str | None]], int]] = [([(token, None)], 1)]
    if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
        variants.append(([(token, tokens[index + 1])], 2))
    return variants


def _normalize_module_progress_rows(raw: object, now: str) -> list[dict[str, object]]:
    """Normalize raw module progress rows from import payload."""
    if not isinstance(raw, list):
        return []
    raw_rows = cast(list[object], raw)
    rows: list[dict[str, object]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        row = cast(dict[str, object], item)
        module_id: object = row.get("module_id")
        if not isinstance(module_id, str) or not module_id.strip():
            continue
        started_at_value: object = row.get("started_at")
        started_at = started_at_value if isinstance(started_at_value, str) and started_at_value else now
        completed_at_value: object = row.get("completed_at")
        completed_at = completed_at_value if isinstance(completed_at_value, str) and completed_at_value else None
        completed_version_value: object = row.get("completed_content_version")
        completed_content_version = _coerce_int(completed_version_value)
        rows.append(
            {
                "module_id": module_id.strip(),
                "started_at": started_at,
                "completed_at": completed_at,
                "completed_content_version": completed_content_version,
            }
        )
    return rows


def _normalize_card_progress_rows(raw: object, now: str) -> list[dict[str, object]]:
    """Normalize raw card progress rows from import payload."""
    if not isinstance(raw, list):
        return []
    raw_rows = cast(list[object], raw)
    rows: list[dict[str, object]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        row = cast(dict[str, object], item)
        card_id: object = row.get("card_id")
        if not isinstance(card_id, str) or not card_id.strip():
            continue

        streak = _coerce_int(row.get("streak", 0), default=0) or 0
        spacing_score = _coerce_float(row.get("spacing_score", 0.0), default=0.0) or 0.0
        interval_minutes = _coerce_int(row.get("interval_minutes", 0), default=0) or 0
        due_at: object = row.get("due_at")
        if not isinstance(due_at, str) or not due_at:
            due_at = now
        last_seen_at: object = row.get("last_seen_at")
        if not isinstance(last_seen_at, str) or not last_seen_at:
            last_seen_at = now
        last_result = _coerce_int(row.get("last_result", 0), default=0) or 0
        seen_count = _coerce_int(row.get("seen_count", 0), default=0) or 0

        rows.append(
            {
                "card_id": card_id.strip(),
                "streak": max(0, streak),
                "spacing_score": max(0.0, spacing_score),
                "interval_minutes": max(0, interval_minutes),
                "due_at": due_at,
                "last_seen_at": last_seen_at,
                "last_result": 1 if last_result else 0,
                "seen_count": max(0, seen_count),
            }
        )
    return rows


def _normalize_attempt_rows(raw: object, now: str) -> list[dict[str, object]]:
    """Normalize raw attempts rows from import payload."""
    if not isinstance(raw, list):
        return []
    raw_rows = cast(list[object], raw)
    rows: list[dict[str, object]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        row = cast(dict[str, object], item)
        card_id: object = row.get("card_id")
        if not isinstance(card_id, str) or not card_id.strip():
            continue
        user_input = row.get("user_input", "")
        if not isinstance(user_input, str):
            user_input = str(user_input)
        is_correct = _coerce_int(row.get("is_correct", 0), default=0) or 0
        created_at: object = row.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            created_at = now
        rows.append(
            {
                "card_id": card_id.strip(),
                "user_input": user_input,
                "is_correct": 1 if is_correct else 0,
                "created_at": created_at,
            }
        )
    return rows


def _coerce_int(value: object, default: int | None = None) -> int | None:
    """Coerce value to int for import normalization."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_float(value: object, default: float | None = None) -> float | None:
    """Coerce value to float for import normalization."""
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default
