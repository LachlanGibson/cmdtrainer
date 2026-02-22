"""Application service for profiles, modules, and spaced-repetition practice."""

from __future__ import annotations

import random
import shlex
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .content_loader import load_modules
from .models import Card, Module
from .progress import Profile, ProgressStore


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
            for lesson in module.lessons:
                for card in lesson.cards:
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
        user_command = _normalize_command(user_input)
        if user_command is None:
            return False
        for answer in card.answers:
            expected = _normalize_command(answer)
            if expected is not None and user_command == expected:
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
            for lesson in module.lessons:
                for card in lesson.cards:
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
    stripped = command.strip()
    if not stripped:
        return None
    try:
        tokens = shlex.split(stripped, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    return _canonicalize_tokens(tuple(token.strip() for token in tokens))


def _canonicalize_tokens(tokens: tuple[str, ...]) -> NormalizedCommand | None:
    """Build canonical command structure from shell tokens."""
    command = tokens[0]
    options: list[tuple[str, str | None]] = []
    positionals: list[str] = []
    force_positionals = False

    index = 1
    while index < len(tokens):
        token = tokens[index]

        if force_positionals:
            positionals.append(token)
            index += 1
            continue

        if token == "--":
            force_positionals = True
            index += 1
            continue

        if token.startswith("--") and len(token) > 2:
            key, value, consumed = _parse_long_option(tokens, index)
            options.append((key, value))
            index += consumed
            continue

        if token.startswith("-") and len(token) > 1:
            short_options, consumed = _parse_short_option(tokens, index)
            options.extend(short_options)
            index += consumed
            continue

        positionals.append(token)
        index += 1

    options.sort(key=lambda pair: (pair[0], "" if pair[1] is None else pair[1]))
    return NormalizedCommand(command=command, options=tuple(options), positionals=tuple(positionals))


def _parse_long_option(tokens: tuple[str, ...], index: int) -> tuple[str, str | None, int]:
    """Parse one long option token and optional value."""
    token = tokens[index]
    if "=" in token:
        key, value = token.split("=", 1)
        return (key, value, 1)
    if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
        return (token, tokens[index + 1], 2)
    return (token, None, 1)


def _parse_short_option(tokens: tuple[str, ...], index: int) -> tuple[list[tuple[str, str | None]], int]:
    """Parse short options, handling grouped boolean flags and single option values."""
    token = tokens[index]
    # Combined single-letter flags like `-la` and `-al` are equivalent.
    if len(token) > 2 and token[1:].isalpha():
        flags = sorted(token[1:])
        return ([(f"-{flag}", None) for flag in flags], 1)

    # Attached value form like `-p22`.
    if len(token) > 2:
        return ([(token[:2], token[2:])], 1)

    return ([(token, None)], 1)
