"""CLI entrypoint for command flashcard learning app."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .models import Card, Module
from .service import LearnService

InputFn = Callable[[str], str]
PrintFn = Callable[[str], None]
BACK_COMMANDS = {":back", ":b", "back"}
MENU_QUIT_COMMANDS = {"q"}
FLOW_EXIT_COMMANDS = {":quit", ":exit", ":q"}
MENU_BACK_COMMANDS = {"b"}


class QuitApp(Exception):
    """Signal immediate app exit from nested menu flows."""


def _service() -> LearnService:
    """Create app service with local database path."""
    db_path = Path(".cmdtrainer") / "progress.db"
    return LearnService(db_path=db_path)


def run(argv: list[str] | None = None) -> int:
    """Run the CLI application."""
    parser = argparse.ArgumentParser(prog="cmdtrainer", description="Profile-based command practice")
    parser.add_argument("command", nargs="?", default="play", choices=["play"])
    _ = parser.parse_args(argv)
    return play_shell()


def play_shell(input_fn: InputFn = input, print_fn: PrintFn = print) -> int:
    """Run persistent menu-driven shell."""
    service = _service()
    try:
        selected = _select_profile(service, input_fn, print_fn, allow_cancel=False)
        if selected is None:
            return 0
        profile_id, profile_name = selected
        try:
            while True:
                print_fn("\n=== Command Practice ===")
                print_fn(f"Profile: {profile_name}")
                print_fn("1) Learn a module")
                print_fn("2) General practice")
                print_fn("3) Status")
                print_fn("4) Admin")
                print_fn("b) Back")
                print_fn("q) Quit")
                choice = input_fn("Choose: ").strip().lower()

                if choice == "1":
                    _learn_module_flow(service, profile_id, input_fn, print_fn)
                elif choice == "2":
                    _general_practice_flow(service, profile_id, input_fn, print_fn)
                elif choice == "3":
                    _status_flow(service, profile_id, print_fn)
                elif choice == "4":
                    _admin_flow(service, profile_id, input_fn, print_fn)
                elif choice in MENU_BACK_COMMANDS:
                    switched = _select_profile(service, input_fn, print_fn, allow_cancel=True)
                    if switched is None:
                        return 0
                    profile_id, profile_name = switched
                elif choice in MENU_QUIT_COMMANDS:
                    return 0
                else:
                    print_fn("Invalid choice.")
        except QuitApp:
            return 0
    finally:
        service.close()


def _select_profile(
    service: LearnService, input_fn: InputFn, print_fn: PrintFn, *, allow_cancel: bool
) -> tuple[int, str] | None:
    """Select existing profile or create new one."""
    while True:
        profiles = service.list_profiles()
        print_fn("\n=== Profiles ===")
        if profiles:
            for idx, profile in enumerate(profiles, start=1):
                print_fn(f"{idx}) {profile.name}")
        else:
            print_fn("No profiles yet.")
        print_fn("n) New profile")
        print_fn("i) Import profile from file")
        print_fn("d) Delete profile")
        print_fn("q) Quit")

        choice = input_fn("Select profile: ").strip().lower()
        if choice in MENU_QUIT_COMMANDS:
            return None
        if choice == "n":
            name = input_fn("New profile name: ").strip()
            if not name:
                print_fn("Profile name is required.")
                continue
            try:
                created = service.create_profile(name)
            except Exception:
                print_fn("Could not create profile (name may already exist).")
                continue
            return (created.id, created.name)
        if choice == "d":
            _delete_profile_flow(service, input_fn, print_fn)
            continue
        if choice == "i":
            _import_profile_flow(service, input_fn, print_fn)
            continue

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(profiles):
                selected = profiles[index]
                return (selected.id, selected.name)

        print_fn("Invalid profile selection.")


def _delete_profile_flow(service: LearnService, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Delete a profile with explicit confirmation safeguard."""
    profiles = service.list_profiles()
    if not profiles:
        print_fn("No profiles available to delete.")
        return

    print_fn("\nDelete profile")
    for idx, profile in enumerate(profiles, start=1):
        print_fn(f"{idx}) {profile.name}")
    print_fn("b) Back")
    choice = input_fn("Choose profile to delete: ").strip().lower()
    if choice in MENU_BACK_COMMANDS:
        return
    if not choice.isdigit():
        print_fn("Invalid choice.")
        return

    index = int(choice) - 1
    if not (0 <= index < len(profiles)):
        print_fn("Invalid choice.")
        return

    target = profiles[index]
    warning = (
        f"WARNING: This permanently deletes profile '{target.name}' and all progress "
        "(attempts, schedules, module state)."
    )
    print_fn(warning)
    confirm = input_fn("Type YES to confirm deletion: ").strip()
    if confirm != "YES":
        print_fn("Deletion cancelled.")
        return
    deleted = service.delete_profile(target.id)
    if deleted:
        print_fn(f"Deleted profile '{target.name}'.")
    else:
        print_fn("Profile was not found.")


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


def _learn_module_flow(service: LearnService, profile_id: int, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Run first-time guided learning flow for one module."""
    all_states = service.list_module_states(profile_id)
    states = [state for state in all_states if state.unlocked]
    if not states:
        print_fn("No unlocked modules available yet.")
        return

    print_fn("\n=== Learn Module ===")
    id_width = max(9, max(len(state.module.id) for state in all_states))
    status_width = 9
    prereq_width = max(
        12,
        max(
            len(", ".join(state.module.prerequisites) if state.module.prerequisites else "none") for state in all_states
        ),
    )
    header = f"{'#':>2} {'Module':<{id_width}} {'Status':<{status_width}} {'Prerequisites':<{prereq_width}} Title"
    print_fn(header)
    print_fn("-" * len(header))
    completed_ids = {state.module.id for state in all_states if state.completed}
    for idx, state in enumerate(states, start=1):
        status = (
            "outdated"
            if state.outdated
            else ("completed" if state.completed else ("started" if state.started else "new"))
        )
        prerequisites = ", ".join(state.module.prerequisites) if state.module.prerequisites else "none"
        row = (
            f"{idx:>2} "
            f"{state.module.id:<{id_width}} "
            f"{status:<{status_width}} "
            f"{prerequisites:<{prereq_width}} "
            f"{state.module.title}"
        )
        print_fn(row)

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

    print_fn("b) Back")
    print_fn("q) Quit")
    choice = input_fn("Choose module: ").strip().lower()
    if choice in MENU_BACK_COMMANDS:
        return
    if choice in MENU_QUIT_COMMANDS:
        raise QuitApp()
    if not choice.isdigit():
        print_fn("Invalid choice.")
        return

    index = int(choice) - 1
    if not (0 <= index < len(states)):
        print_fn("Invalid choice.")
        return

    module = service.begin_module(profile_id, states[index].module.id)
    _run_guided_module(service, profile_id, module, input_fn, print_fn)


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


def _module_details_flow(service: LearnService, profile_id: int, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Show command, lesson, and progression details for one selected module."""
    modules = sorted(service.modules.values(), key=lambda item: item.id)
    print_fn("\n=== Module Details ===")
    for idx, module in enumerate(modules, start=1):
        print_fn(f"{idx}) {module.id} - {module.title}")
    print_fn("b) Back")
    print_fn("q) Quit")
    choice = input_fn("Choose module: ").strip().lower()
    if choice in MENU_BACK_COMMANDS:
        return
    if choice in MENU_QUIT_COMMANDS:
        raise QuitApp()
    if not choice.isdigit():
        print_fn("Invalid choice.")
        return
    index = int(choice) - 1
    if not (0 <= index < len(modules)):
        print_fn("Invalid choice.")
        return
    module = modules[index]

    while True:
        print_fn(f"\n=== Module Details: {module.id} ===")
        print_fn("1) Commands")
        print_fn("2) Lessons")
        print_fn("3) Progression")
        print_fn("b) Back")
        print_fn("q) Quit")
        detail_choice = input_fn("Choose detail: ").strip().lower()
        if detail_choice in MENU_BACK_COMMANDS:
            return
        if detail_choice in MENU_QUIT_COMMANDS:
            raise QuitApp()
        if detail_choice == "1":
            references = service.list_module_command_references(module.id)
            print_fn(f"\nCommands in {module.title}:")
            for reference in references:
                flags_text = ", ".join(reference.tested_flags) if reference.tested_flags else "none"
                print_fn(f"- {reference.command}: {flags_text}")
        elif detail_choice == "2":
            _module_lessons_flow(service, module, print_fn)
        elif detail_choice == "3":
            _module_progression_flow(service, profile_id, module, print_fn)
        else:
            print_fn("Invalid choice.")


def _admin_flow(service: LearnService, profile_id: int, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Admin menu for reference and progression management."""
    while True:
        print_fn("\n=== Admin ===")
        print_fn("1) Module details")
        print_fn("2) View schedule queue")
        print_fn("3) Force unlock module (+ dependencies)")
        print_fn("4) Export current profile")
        print_fn("b) Back")
        print_fn("q) Quit")
        choice = input_fn("Choose admin option: ").strip().lower()
        if choice in MENU_BACK_COMMANDS:
            return
        if choice in MENU_QUIT_COMMANDS:
            raise QuitApp()
        if choice == "1":
            _module_details_flow(service, profile_id, input_fn, print_fn)
        elif choice == "2":
            _queue_flow(service, profile_id, print_fn)
        elif choice == "3":
            _force_unlock_flow(service, profile_id, input_fn, print_fn)
        elif choice == "4":
            _export_profile_flow(service, profile_id, input_fn, print_fn)
        else:
            print_fn("Invalid choice.")


def _force_unlock_flow(service: LearnService, profile_id: int, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Force-complete selected module and all prerequisites."""
    modules = sorted(service.modules.values(), key=lambda item: item.id)
    print_fn("\n=== Force Unlock ===")
    for idx, module in enumerate(modules, start=1):
        print_fn(f"{idx}) {module.id} - {module.title}")
    print_fn("b) Back")
    print_fn("q) Quit")
    choice = input_fn("Choose module to unlock: ").strip().lower()
    if choice in MENU_BACK_COMMANDS:
        return
    if choice in MENU_QUIT_COMMANDS:
        raise QuitApp()
    if not choice.isdigit():
        print_fn("Invalid choice.")
        return
    index = int(choice) - 1
    if not (0 <= index < len(modules)):
        print_fn("Invalid choice.")
        return
    selected = modules[index]
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
        interval_label = f"{item.interval_minutes}m" if item.interval_minutes > 0 else "-"
        print_fn(
            f"{local_due:<{due_width}} "
            f"{item.streak:>{streak_width}} "
            f"{item.spacing_score:>{score_width}.2f} "
            f"{interval_label:>{interval_width}} "
            f"{item.command}"
        )


def _export_profile_flow(service: LearnService, profile_id: int, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Export current profile progress to a JSON file."""
    print_fn("\n=== Export Profile ===")
    path_text = input_fn("Export file path: ").strip()
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


def _import_profile_flow(service: LearnService, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Import profile progress from a JSON file as a new profile."""
    print_fn("\n=== Import Profile ===")
    path_text = input_fn("Import file path: ").strip()
    if not path_text:
        print_fn("File path is required.")
        return
    name_text = input_fn("Imported profile name (blank = file value): ").strip()
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


def _format_local_due(due_at: str) -> str:
    """Convert ISO due timestamp to local human-readable datetime."""
    try:
        dt = datetime.fromisoformat(due_at)
    except ValueError:
        return due_at
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _run_guided_module(
    service: LearnService,
    profile_id: int,
    module: Module,
    input_fn: InputFn,
    print_fn: PrintFn,
) -> None:
    """Guide through all cards by showing answers first, then requiring input."""
    print_fn(f"\nStarting module: {module.title}")
    print_fn(module.description)
    print_fn("Type :b or :q to exit module.")

    for lesson in module.lessons:
        print_fn(f"\nLesson {lesson.order}: {lesson.title}")
        for card in lesson.cards:
            should_continue = _run_guided_card(service, profile_id, card, input_fn, print_fn)
            if not should_continue:
                print_fn("Leaving module. Progress saved.")
                return

    completed = service.complete_module_if_mastered(profile_id, module)
    if completed:
        print_fn("Module completed for the first time.")
    else:
        print_fn("Module progress saved.")


def _run_guided_card(
    service: LearnService,
    profile_id: int,
    card: Card,
    input_fn: InputFn,
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
        user_input = input_fn("Type command: ").strip()
        lowered = user_input.lower()
        if lowered in BACK_COMMANDS or lowered in FLOW_EXIT_COMMANDS:
            return False
        correct = service.record_answer(profile_id, card, user_input)
        if correct:
            print_fn("Correct.")
            return True
        print_fn("Not quite. Try again.")


def _general_practice_flow(service: LearnService, profile_id: int, input_fn: InputFn, print_fn: PrintFn) -> None:
    """Run randomized spaced-repetition practice."""
    cards = service.due_cards(profile_id, limit=10)
    if not cards:
        print_fn("No cards available. Start a module first.")
        return

    print_fn("\n=== General Practice ===")
    print_fn(f"Cards this round: {len(cards)}")
    print_fn("Type :b or :q to exit practice.")
    correct_count = 0
    attempted_count = 0
    for card in cards:
        print_fn(f"\nPrompt: {card.prompt}")
        user_input = input_fn("Type command (or :show): ").strip()
        lowered = user_input.lower()
        if lowered in BACK_COMMANDS or lowered in FLOW_EXIT_COMMANDS:
            print_fn(f"\nRound ended early: {correct_count}/{attempted_count} correct")
            return
        if lowered == ":show":
            print_fn(f"Answer: {card.answers[0]}")
            user_input = input_fn("Now type command: ").strip()
            lowered = user_input.lower()
            if lowered in BACK_COMMANDS or lowered in FLOW_EXIT_COMMANDS:
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


def main_entry() -> None:
    """Console script entrypoint."""
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main_entry()
