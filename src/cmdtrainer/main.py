"""CLI entrypoint for command flashcard learning app."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .input_reader import InputReader, TerminalInputReader
from .models import Card, Module
from .service import LearnService

PrintFn = Callable[[str], None]

# ── Key constants ──────────────────────────────────────────────────────────────
KEY_BACK = "b"
KEY_QUIT = "q"
KEY_NEXT = "n"
KEY_PREV = "p"

# Only used during card-answer readline input (multi-char commands are possible).
CARD_EXIT_COMMANDS = {":back", ":b", ":quit", ":exit", ":q"}


class QuitApp(Exception):
    """Signal immediate app exit from nested menu flows."""


# ── Infrastructure ─────────────────────────────────────────────────────────────


def _service() -> LearnService:  # pragma: no cover
    """Create app service with local database path."""
    db_path = Path(".cmdtrainer") / "progress.db"
    return LearnService(db_path=db_path)


def _row(key: str, label: str) -> str:
    """Format a single instant-key option row."""
    return f"  [{key}] {label}"


def _paginated_select[T](
    items: list[T],
    reader: InputReader,
    print_fn: PrintFn,
    *,
    format_fn: Callable[[T], str],
    page_size: int = 9,
) -> T | None:
    """Single-keypress selection from a numbered list with optional pagination.

    Returns the selected item, or *None* on back.  Raises *QuitApp* on quit.
    Invalid keys are silently ignored and the page is re-rendered.
    """
    page = 0
    while True:
        total_pages = max(1, (len(items) + page_size - 1) // page_size)
        page = min(page, total_pages - 1)
        start = page * page_size
        page_items = items[start : start + page_size]

        if total_pages > 1:
            print_fn(f"  (Page {page + 1}/{total_pages})")
        for i, item in enumerate(page_items, 1):
            print_fn(_row(str(i), format_fn(item)))

        footer: list[str] = []
        if total_pages > 1 and page > 0:
            footer.append(f"[{KEY_PREV}] Prev")
        if total_pages > 1 and page < total_pages - 1:
            footer.append(f"[{KEY_NEXT}] Next")
        footer.extend([f"[{KEY_BACK}] Back", f"[{KEY_QUIT}] Quit"])
        print_fn("  " + "   ".join(footer))

        key = reader.readkey("")
        if key == KEY_BACK:
            return None
        if key == KEY_QUIT:
            raise QuitApp()
        if key == KEY_NEXT and page < total_pages - 1:
            page += 1
        elif key == KEY_PREV and page > 0:
            page -= 1
        elif key.isdigit():
            index = int(key) - 1
            if 0 <= index < len(page_items):
                return page_items[index]


# ── Entry points ───────────────────────────────────────────────────────────────


def run(argv: list[str] | None = None) -> int:
    """Run the CLI application."""
    parser = argparse.ArgumentParser(prog="cmdtrainer", description="Profile-based command practice")
    parser.add_argument("command", nargs="?", default="play", choices=["play"])
    _ = parser.parse_args(argv)
    return play_shell()


def play_shell(reader: InputReader | None = None, print_fn: PrintFn = print) -> int:
    """Run persistent menu-driven shell."""
    _reader: InputReader = reader if reader is not None else TerminalInputReader()
    service = _service()
    try:
        selected = _select_profile(service, _reader, print_fn, allow_cancel=False)
        if selected is None:
            return 0
        profile_id, profile_name = selected
        try:
            while True:
                print_fn("\n=== Command Practice ===")
                print_fn(f"Profile: {profile_name}")
                print_fn(_row("1", "Learn a module"))
                print_fn(_row("2", "General practice"))
                print_fn(_row("3", "Status"))
                print_fn(_row("4", "Admin"))
                print_fn("  [b] Switch profile   [q] Quit")
                choice = _reader.readkey("")

                if choice == "1":
                    _learn_module_flow(service, profile_id, _reader, print_fn)
                elif choice == "2":
                    _general_practice_flow(service, profile_id, _reader, print_fn)
                elif choice == "3":
                    _status_flow(service, profile_id, print_fn)
                elif choice == "4":
                    _admin_flow(service, profile_id, _reader, print_fn)
                elif choice == KEY_BACK:
                    switched = _select_profile(service, _reader, print_fn, allow_cancel=True)
                    if switched is None:
                        return 0
                    profile_id, profile_name = switched
                elif choice == KEY_QUIT:
                    return 0
        except QuitApp:
            return 0
    finally:
        service.close()


# ── Profile flows ──────────────────────────────────────────────────────────────


def _select_profile(
    service: LearnService, reader: InputReader, print_fn: PrintFn, *, allow_cancel: bool
) -> tuple[int, str] | None:
    """Select existing profile or create a new one."""
    page = 0
    page_size = 9
    while True:
        profiles = service.list_profiles()
        total_pages = max(1, (len(profiles) + page_size - 1) // page_size)
        page = min(page, total_pages - 1)
        start = page * page_size
        page_profiles = profiles[start : start + page_size]

        print_fn("\n=== Profiles ===")
        if total_pages > 1:
            print_fn(f"  (Page {page + 1}/{total_pages})")
        if page_profiles:
            for i, profile in enumerate(page_profiles, 1):
                print_fn(_row(str(i), profile.name))
        else:
            print_fn("  No profiles yet.")

        footer: list[str] = []
        if total_pages > 1 and page > 0:
            footer.append(f"[{KEY_PREV}] Prev")
        if total_pages > 1 and page < total_pages - 1:
            footer.append(f"[{KEY_NEXT}] Next")
        footer.extend(["[c] Create new", "[i] Import", "[d] Delete", "[q] Quit"])
        print_fn("  " + "   ".join(footer))

        key = reader.readkey("")

        if key == KEY_QUIT:
            return None
        if key == KEY_NEXT and total_pages > 1 and page < total_pages - 1:
            page += 1
            continue
        if key == KEY_PREV and total_pages > 1 and page > 0:
            page -= 1
            continue
        if key == "c":
            name = reader.readline("New profile name: ").strip()
            if not name:
                print_fn("Profile name is required.")
                continue
            try:
                created = service.create_profile(name)
            except Exception:
                print_fn("Could not create profile (name may already exist).")
                continue
            return (created.id, created.name)
        if key == "d":
            _delete_profile_flow(service, reader, print_fn)
            continue
        if key == "i":
            _import_profile_flow(service, reader, print_fn)
            continue
        if key.isdigit():
            index = int(key) - 1
            if 0 <= index < len(page_profiles):
                selected = page_profiles[index]
                return (selected.id, selected.name)


def _delete_profile_flow(service: LearnService, reader: InputReader, print_fn: PrintFn) -> None:
    """Delete a profile with explicit confirmation safeguard."""
    profiles = service.list_profiles()
    if not profiles:
        print_fn("No profiles available to delete.")
        return

    print_fn("\nDelete profile")
    selected = _paginated_select(
        profiles,
        reader,
        print_fn,
        format_fn=lambda p: p.name,
    )
    if selected is None:
        return

    warning = (
        f"WARNING: This permanently deletes profile '{selected.name}' and all progress "
        "(attempts, schedules, module state)."
    )
    print_fn(warning)
    confirm = reader.readline("Type YES to confirm deletion: ").strip()
    if confirm != "YES":
        print_fn("Deletion cancelled.")
        return
    deleted = service.delete_profile(selected.id)
    if deleted:
        print_fn(f"Deleted profile '{selected.name}'.")
    else:
        print_fn("Profile was not found.")


# ── Status flow (read-only, no input) ──────────────────────────────────────────


def _status_flow(service: LearnService, profile_id: int, print_fn: PrintFn) -> None:
    """Print module progress status."""
    print_fn("\n=== Module Status ===")
    states = service.list_module_states(profile_id)
    completed_ids = {state.module.id for state in states if state.completed}
    rows: list[tuple[str, str, str, str, str]] = []
    for state in states:
        unlocked = "unlocked" if state.unlocked else "locked"
        stage = (
            "outdated"
            if state.outdated
            else ("completed" if state.completed else ("started" if state.started else "new"))
        )
        missing = [dep for dep in state.module.prerequisites if dep not in completed_ids]
        if state.module.prerequisites:
            prereq_items = [f"*{dep}" if dep in missing else dep for dep in state.module.prerequisites]
            prerequisites = ", ".join(prereq_items)
        else:
            prerequisites = "none"
        rows.append((state.module.id, state.module.title, unlocked, stage, prerequisites))

    module_width = max(len("Module"), max(len(row[0]) for row in rows))
    title_width = max(len("Title"), max(len(row[1]) for row in rows))
    unlock_width = max(len("Unlock"), max(len(row[2]) for row in rows))
    stage_width = max(len("Stage"), max(len(row[3]) for row in rows))
    prereq_width = max(len("Prerequisites"), max(len(row[4]) for row in rows))
    header = (
        f"{'Module':<{module_width}} "
        f"{'Title':<{title_width}} "
        f"{'Unlock':<{unlock_width}} "
        f"{'Stage':<{stage_width}} "
        f"{'Prerequisites':<{prereq_width}}"
    )
    print_fn(header)
    print_fn("-" * len(header))
    for row in rows:
        print_fn(
            f"{row[0]:<{module_width}} "
            f"{row[1]:<{title_width}} "
            f"{row[2]:<{unlock_width}} "
            f"{row[3]:<{stage_width}} "
            f"{row[4]:<{prereq_width}}"
        )


# ── Learn flows ────────────────────────────────────────────────────────────────


def _learn_module_flow(service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn) -> None:
    """Run guided learning flow for one module, with grouped outdated shortcut."""
    all_states = service.list_module_states(profile_id)
    states = [state for state in all_states if state.unlocked]
    if not states:
        print_fn("No unlocked modules available yet.")
        return

    page = 0
    page_size = 9

    while True:
        total_pages = max(1, (len(states) + page_size - 1) // page_size)
        page = min(page, total_pages - 1)
        start = page * page_size
        page_states = states[start : start + page_size]

        print_fn("\n=== Learn Module ===")

        id_width = max(9, max(len(state.module.id) for state in all_states))
        status_width = 9
        prereq_width = max(
            12,
            max(
                len(", ".join(state.module.prerequisites) if state.module.prerequisites else "none")
                for state in all_states
            ),
        )
        if total_pages > 1:
            print_fn(f"  (Page {page + 1}/{total_pages})")
        header = f"{'#':>2} {'Module':<{id_width}} {'Status':<{status_width}} {'Prerequisites':<{prereq_width}} Title"
        print_fn(header)
        print_fn("-" * len(header))
        completed_ids = {state.module.id for state in all_states if state.completed}
        for idx, state in enumerate(page_states, start=1):
            status = (
                "outdated"
                if state.outdated
                else ("completed" if state.completed else ("started" if state.started else "new"))
            )
            prerequisites = ", ".join(state.module.prerequisites) if state.module.prerequisites else "none"
            print_fn(
                f"{idx:>2} "
                f"{state.module.id:<{id_width}} "
                f"{status:<{status_width}} "
                f"{prerequisites:<{prereq_width}} "
                f"{state.module.title}"
            )

        locked_states = [state for state in all_states if not state.unlocked]
        if locked_states:
            print_fn("\nLocked Modules")
            locked_header = f"{'Module':<{id_width}} Missing prerequisites"
            print_fn(locked_header)
            print_fn("-" * len(locked_header))
            for state in all_states:
                if state.unlocked:
                    continue
                missing = [dep for dep in state.module.prerequisites if dep not in completed_ids]
                print_fn(f"{state.module.id:<{id_width}} {', '.join(missing)}")

        has_outdated = any(s.outdated for s in all_states if s.unlocked)
        footer: list[str] = []
        if has_outdated:
            footer.append("[g] Grouped outdated")
        if total_pages > 1 and page > 0:
            footer.append(f"[{KEY_PREV}] Prev")
        if total_pages > 1 and page < total_pages - 1:
            footer.append(f"[{KEY_NEXT}] Next")
        footer.extend([f"[{KEY_BACK}] Back", f"[{KEY_QUIT}] Quit"])
        print_fn("  " + "   ".join(footer))

        key = reader.readkey("")

        if key == "g":
            _learn_outdated_modules_flow(service, profile_id, reader, print_fn)
            return
        if key == KEY_BACK:
            return
        if key == KEY_QUIT:
            raise QuitApp()
        if key == KEY_NEXT and page < total_pages - 1:
            page += 1
            continue
        if key == KEY_PREV and page > 0:
            page -= 1
            continue
        if key.isdigit():
            index = int(key) - 1
            if 0 <= index < len(page_states):
                selected_state = page_states[index]
                module = service.begin_module(profile_id, selected_state.module.id)
                restart = False
                if selected_state.started:
                    print_fn(_row("Enter", "Resume") + "   " + _row("r", "Restart"))
                    restart = reader.readkey("") == "r"
                _run_guided_module(service, profile_id, module, reader, print_fn, restart=restart)
                return


def _learn_outdated_modules_flow(
    service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn
) -> None:
    """Run guided updates across all outdated modules."""
    states = [state for state in service.list_module_states(profile_id) if state.outdated and state.unlocked]
    if not states:
        print_fn("No outdated modules to update.")
        return

    print_fn("\n=== Grouped Outdated Modules ===")
    for item in states:
        print_fn(f"- {item.module.id}: {item.module.title}")
    print_fn(_row("Enter", "Start updates") + "   " + _row(KEY_BACK, "Cancel") + "   " + _row(KEY_QUIT, "Quit"))
    key = reader.readkey("")
    if key == KEY_BACK:
        return
    if key == KEY_QUIT:
        raise QuitApp()

    updated = 0
    for state in states:
        module = service.begin_module(profile_id, state.module.id)
        completed = _run_guided_module(service, profile_id, module, reader, print_fn, restart=False)
        if not completed:
            print_fn(f"Stopped early after updating {updated} module(s).")
            return
        updated += 1
    print_fn(f"Outdated module update complete: {updated} module(s).")


# ── Module detail flows (read-only helpers) ────────────────────────────────────


def _module_lessons_flow(service: LearnService, module: Module, print_fn: PrintFn) -> None:
    """Show lesson list for one module."""
    lessons = service.list_module_lesson_references(module.id)
    print_fn(f"\nLessons in {module.title}:")
    if not lessons:
        print_fn("No lessons defined.")
        return
    order_width = max(len("Order"), max(len(str(item.order)) for item in lessons))
    id_width = max(len("Lesson ID"), max(len(item.lesson_id) for item in lessons))
    cards_width = max(len("Cards"), max(len(str(item.card_count)) for item in lessons))
    commands_width = max(len("Commands"), max(len(str(item.command_count)) for item in lessons))
    header = (
        f"{'Order':>{order_width}} "
        f"{'Lesson ID':<{id_width}} "
        f"{'Cards':>{cards_width}} "
        f"{'Commands':>{commands_width}} "
        "Title"
    )
    print_fn(header)
    print_fn("-" * len(header))
    for item in lessons:
        print_fn(
            f"{item.order:>{order_width}} "
            f"{item.lesson_id:<{id_width}} "
            f"{item.card_count:>{cards_width}} "
            f"{item.command_count:>{commands_width}} "
            f"{item.title}"
        )


def _module_progression_flow(service: LearnService, profile_id: int, module: Module, print_fn: PrintFn) -> None:
    """Show per-module progression summary with lesson breakdown."""
    progression = service.get_module_progression(profile_id, module.id)
    remaining = progression.total_cards - progression.correct_cards
    percent = 100.0 if progression.total_cards == 0 else (100.0 * progression.correct_cards / progression.total_cards)

    print_fn(f"\nProgression in {module.title}:")
    print_fn(f"- Stage: {progression.stage}")
    print_fn(f"- Cards: {progression.correct_cards}/{progression.total_cards} correct ({percent:.1f}%)")
    print_fn(f"- Attempted: {progression.attempted_cards}")
    print_fn(f"- Remaining: {remaining}")

    if not progression.lessons:
        return

    lesson_id_width = max(len("Lesson ID"), max(len(item.lesson_id) for item in progression.lessons))
    total_width = max(len("Total"), max(len(str(item.total_cards)) for item in progression.lessons))
    attempted_width = max(len("Attempted"), max(len(str(item.attempted_cards)) for item in progression.lessons))
    correct_width = max(len("Correct"), max(len(str(item.correct_cards)) for item in progression.lessons))
    remaining_width = max(
        len("Remaining"),
        max(len(str(item.total_cards - item.correct_cards)) for item in progression.lessons),
    )
    pct_width = len("%")
    header = (
        f"{'Lesson ID':<{lesson_id_width}} "
        f"{'Total':>{total_width}} "
        f"{'Attempted':>{attempted_width}} "
        f"{'Correct':>{correct_width}} "
        f"{'Remaining':>{remaining_width}} "
        f"{'%':>{pct_width}} "
        "Title"
    )
    print_fn("\nBy lesson:")
    print_fn(header)
    print_fn("-" * len(header))
    for item in progression.lessons:
        lesson_remaining = item.total_cards - item.correct_cards
        lesson_pct = 100.0 if item.total_cards == 0 else (100.0 * item.correct_cards / item.total_cards)
        print_fn(
            f"{item.lesson_id:<{lesson_id_width}} "
            f"{item.total_cards:>{total_width}} "
            f"{item.attempted_cards:>{attempted_width}} "
            f"{item.correct_cards:>{correct_width}} "
            f"{lesson_remaining:>{remaining_width}} "
            f"{lesson_pct:>{pct_width}.0f} "
            f"{item.title}"
        )


def _module_details_flow(service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn) -> None:
    """Show command, lesson, and progression details for one selected module."""
    modules = sorted(service.modules.values(), key=lambda item: item.id)
    print_fn("\n=== Module Details ===")
    module = _paginated_select(
        modules,
        reader,
        print_fn,
        format_fn=lambda m: f"{m.id} - {m.title}",
    )
    if module is None:
        return

    while True:
        print_fn(f"\n=== Module Details: {module.id} ===")
        print_fn(_row("1", "Commands"))
        print_fn(_row("2", "Lessons"))
        print_fn(_row("3", "Progression"))
        print_fn(f"  [{KEY_BACK}] Back   [{KEY_QUIT}] Quit")
        detail_key = reader.readkey("")
        if detail_key == KEY_BACK:
            return
        if detail_key == KEY_QUIT:
            raise QuitApp()
        if detail_key == "1":
            references = service.list_module_command_references(module.id)
            print_fn(f"\nCommands in {module.title}:")
            for reference in references:
                flags_text = ", ".join(reference.tested_flags) if reference.tested_flags else "none"
                print_fn(f"- {reference.command}: {flags_text}")
        elif detail_key == "2":
            _module_lessons_flow(service, module, print_fn)
        elif detail_key == "3":
            _module_progression_flow(service, profile_id, module, print_fn)


# ── Admin flow ─────────────────────────────────────────────────────────────────


def _admin_flow(service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn) -> None:
    """Admin menu for reference and progression management."""
    while True:
        print_fn("\n=== Admin ===")
        print_fn(_row("1", "Module details"))
        print_fn(_row("2", "View schedule queue"))
        print_fn(_row("3", "Force unlock module (+ dependencies)"))
        print_fn(_row("4", "Export current profile"))
        print_fn(f"  [{KEY_BACK}] Back   [{KEY_QUIT}] Quit")
        choice = reader.readkey("")
        if choice == KEY_BACK:
            return
        if choice == KEY_QUIT:
            raise QuitApp()
        if choice == "1":
            _module_details_flow(service, profile_id, reader, print_fn)
        elif choice == "2":
            _queue_flow(service, profile_id, print_fn)
        elif choice == "3":
            _force_unlock_flow(service, profile_id, reader, print_fn)
        elif choice == "4":
            _export_profile_flow(service, profile_id, reader, print_fn)


def _force_unlock_flow(service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn) -> None:
    """Force-complete selected module and all prerequisites."""
    modules = sorted(service.modules.values(), key=lambda item: item.id)
    print_fn("\n=== Force Unlock ===")
    selected = _paginated_select(
        modules,
        reader,
        print_fn,
        format_fn=lambda m: f"{m.id} - {m.title}",
    )
    if selected is None:
        return
    unlocked = service.force_unlock_module_with_dependencies(profile_id, selected.id)
    print_fn("Force unlocked modules:")
    for module_id in unlocked:
        print_fn(f"- {module_id}")


def _queue_flow(service: LearnService, profile_id: int, print_fn: PrintFn) -> None:
    """Show current practice scheduling queue."""
    queue = service.practice_queue(profile_id, limit=30)
    print_fn("\n=== Practice Queue ===")
    if not queue:
        print_fn("No queued cards yet. Start or complete a module first.")
        return
    due_width = 16
    streak_width = 6
    score_width = 7
    interval_width = 10
    header = (
        f"{'Due (local)':<{due_width}} "
        f"{'Streak':>{streak_width}} "
        f"{'Score':>{score_width}} "
        f"{'Interval':>{interval_width}} "
        "Command"
    )
    print_fn(header)
    print_fn("-" * len(header))
    for item in queue:
        local_due = _format_local_due(item.due_at)
        interval_label = _format_interval(item.interval_minutes)
        print_fn(
            f"{local_due:<{due_width}} "
            f"{item.streak:>{streak_width}} "
            f"{item.spacing_score:>{score_width}.2f} "
            f"{interval_label:>{interval_width}} "
            f"{item.command}"
        )


def _export_profile_flow(service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn) -> None:
    """Export current profile progress to a JSON file."""
    print_fn("\n=== Export Profile ===")
    path_text = reader.readline("Export file path: ").strip()
    if not path_text:
        print_fn("File path is required.")
        return
    try:
        summary = service.export_profile(profile_id, path_text)
    except Exception as exc:
        print_fn(f"Export failed: {exc}")
        return
    print_fn(f"Exported profile '{summary.profile_name}' to {path_text}")
    print_fn(f"- module rows: {summary.module_rows}")
    print_fn(f"- card rows: {summary.card_rows}")
    print_fn(f"- attempt rows: {summary.attempt_rows}")


def _import_profile_flow(service: LearnService, reader: InputReader, print_fn: PrintFn) -> None:
    """Import profile progress from a JSON file as a new profile."""
    print_fn("\n=== Import Profile ===")
    path_text = reader.readline("Import file path: ").strip()
    if not path_text:
        print_fn("File path is required.")
        return
    name_text = reader.readline("Imported profile name (blank = file value): ").strip()
    target_name = name_text if name_text else None
    try:
        summary = service.import_profile(path_text, target_name)
    except Exception as exc:
        print_fn(f"Import failed: {exc}")
        return
    print_fn(f"Imported profile '{summary.profile_name}'.")
    print_fn(f"- module rows: {summary.module_rows}")
    print_fn(f"- card rows: {summary.card_rows}")
    print_fn(f"- attempt rows: {summary.attempt_rows}")


# ── Formatting helpers ─────────────────────────────────────────────────────────


def _format_interval(minutes: int) -> str:
    """Format an interval in minutes as a human-readable string using appropriate units."""
    if minutes <= 0:
        return "-"
    if minutes < 2 * 60:
        return f"{minutes}m"
    if minutes < 2 * 1440:
        hours = minutes / 60
        return f"{hours:.1f}h"
    days = minutes / 1440
    return f"{days:.1f}d"


def _format_local_due(due_at: str) -> str:
    """Convert ISO due timestamp to local human-readable datetime."""
    try:
        dt = datetime.fromisoformat(due_at)
    except ValueError:
        return due_at
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


# ── Card practice flows ────────────────────────────────────────────────────────


def _run_guided_module(
    service: LearnService,
    profile_id: int,
    module: Module,
    reader: InputReader,
    print_fn: PrintFn,
    *,
    restart: bool = False,
) -> bool:
    """Guide through all cards by showing answers first, then requiring input."""
    print_fn(f"\nStarting module: {module.title}")
    print_fn(module.description)
    print_fn("Type :b or :q to exit module.")
    correct_card_ids: set[str] = set()
    if not restart:
        correct_card_ids = service.correct_card_ids_for_module(profile_id, module.id)
    skipped = 0
    for lesson in module.lessons:
        print_fn(f"\nLesson {lesson.order}: {lesson.title}")
        for card in lesson.cards:
            if not restart and card.id in correct_card_ids:
                skipped += 1
                continue
            should_continue = _run_guided_card(service, profile_id, card, reader, print_fn)
            if not should_continue:
                print_fn("Leaving module. Progress saved.")
                return False
            correct_card_ids.add(card.id)
    if skipped > 0 and not restart:
        print_fn(f"Skipped {skipped} previously mastered card(s).")

    completed = service.complete_module_if_mastered(profile_id, module)
    if completed:
        print_fn("Module completed for the first time.")
    else:
        print_fn("Module progress saved.")
    return True


def _run_guided_card(
    service: LearnService,
    profile_id: int,
    card: Card,
    reader: InputReader,
    print_fn: PrintFn,
) -> bool:
    """Run one guided card until answer is correct."""
    print_fn(f"\nPrompt: {card.prompt}")
    print_fn(f"Answer: {card.answers[0]}")
    if len(card.answers) > 1:
        print_fn("Also accepted:")
        for alt in card.answers[1:]:
            print_fn(f"- {alt}")
    if card.explanation:
        print_fn(f"Note: {card.explanation}")

    while True:
        user_input = reader.readline("Type command: ").strip()
        lowered = user_input.lower()
        if lowered in CARD_EXIT_COMMANDS:
            return False
        correct = service.record_answer(profile_id, card, user_input)
        if correct:
            print_fn("Correct.")
            return True
        print_fn("Not quite. Try again.")


def _general_practice_flow(service: LearnService, profile_id: int, reader: InputReader, print_fn: PrintFn) -> None:
    """Run randomized spaced-repetition practice."""
    cards = service.due_cards(profile_id, limit=10)
    if not cards:
        print_fn("No cards available. Start a module first.")
        return

    while True:
        print_fn("\n=== General Practice ===")
        print_fn(f"Cards this round: {len(cards)}")
        print_fn("Type :b or :q to exit practice.")
        correct_count = 0
        attempted_count = 0
        for card in cards:
            print_fn(f"\nPrompt: {card.prompt}")
            user_input = reader.readline("Type command (or :show): ").strip()
            lowered = user_input.lower()
            if lowered in CARD_EXIT_COMMANDS:
                print_fn(f"\nRound ended early: {correct_count}/{attempted_count} correct")
                return
            if lowered == ":show":
                print_fn(f"Answer: {card.answers[0]}")
                user_input = reader.readline("Now type command: ").strip()
                lowered = user_input.lower()
                if lowered in CARD_EXIT_COMMANDS:
                    print_fn(f"\nRound ended early: {correct_count}/{attempted_count} correct")
                    return

            correct = service.record_answer(profile_id, card, user_input)
            attempted_count += 1
            if correct:
                correct_count += 1
                print_fn("Correct.")
            else:
                print_fn(f"Incorrect. Expected e.g.: {card.answers[0]}")

        print_fn(f"\nRound complete: {correct_count}/{len(cards)} correct")

        due_count = service.count_due_cards(profile_id)
        if due_count > 0:
            print_fn(f"\n{due_count} more card{'s' if due_count != 1 else ''} due")
        else:
            next_cards = service.due_cards(profile_id, limit=1)
            if not next_cards:
                return
            print_fn("\nNo more cards due — practice ahead?")
        print_fn(_row("Enter", "Continue") + "   " + _row(KEY_BACK, "Back") + "   " + _row(KEY_QUIT, "Quit"))
        key = reader.readkey("")
        if key in (KEY_BACK, KEY_QUIT):
            return

        cards = service.due_cards(profile_id, limit=10)


# ── App entry ──────────────────────────────────────────────────────────────────


def main_entry() -> None:
    """Console script entrypoint."""
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main_entry()
