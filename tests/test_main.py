from typing import Any

import pytest

import cmdtrainer.main as main
from cmdtrainer.input_reader import FakeInputReader


def _reader(*responses: str) -> FakeInputReader:
    """Build a FakeInputReader from a fixed sequence of responses."""
    return FakeInputReader(iter(responses))


class DummyProfile:
    def __init__(self, profile_id: int, name: str) -> None:
        self.id = profile_id
        self.name = name


class DummyService:
    def __init__(self) -> None:
        self.profile_id = 1
        self.closed = False
        self._profiles: list[DummyProfile] = []
        self.correct_ids_by_module: dict[str, set[str]] = {}
        self._due_cards_calls = 0

    def close(self) -> None:
        self.closed = True

    def list_profiles(self) -> list[DummyProfile]:
        return sorted(self._profiles, key=lambda profile: profile.name)

    def create_profile(self, name: str) -> DummyProfile:
        profile = DummyProfile(self.profile_id, name)
        self.profile_id += 1
        self._profiles.append(profile)
        return profile

    def delete_profile(self, profile_id: int) -> bool:
        before = len(self._profiles)
        self._profiles = [profile for profile in self._profiles if profile.id != profile_id]
        return len(self._profiles) < before

    def list_module_states(self, profile_id: int) -> list[object]:
        module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
        state = type(
            "S",
            (),
            {"module": module, "unlocked": True, "started": False, "completed": False, "outdated": False},
        )()
        return [state]

    @property
    def modules(self) -> dict[str, object]:
        module = type("M", (), {"id": "base-linux", "title": "Base"})()
        return {"base-linux": module}

    def begin_module(self, profile_id: int, module_id: str) -> object:
        card = type("Card", (), {"id": "c", "prompt": "p", "answers": ["pwd"], "explanation": "e"})()
        lesson = type("Lesson", (), {"order": 1, "title": "L", "cards": [card]})()
        return type("Module", (), {"id": module_id, "title": "T", "description": "D", "lessons": [lesson]})()

    def record_answer(self, profile_id: int, card: object, user_input: str) -> bool:
        return user_input == "pwd"

    def complete_module_if_mastered(self, profile_id: int, module: object) -> bool:
        return True

    def count_due_cards(self, profile_id: int) -> int:
        return 0

    def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
        self._due_cards_calls += 1
        if self._due_cards_calls > 1:
            return []
        card = type("Card", (), {"id": "c", "prompt": "p", "answers": ["pwd"], "explanation": ""})()
        return [card]

    def list_module_command_references(self, module_id: str) -> list[object]:
        return [type("Ref", (), {"command": "pwd", "tested_flags": tuple()})()]

    def list_module_lesson_references(self, module_id: str) -> list[object]:
        return [
            type(
                "LessonRef",
                (),
                {"lesson_id": "navigation", "title": "Navigation", "order": 1, "card_count": 2, "command_count": 1},
            )()
        ]

    def get_module_progression(self, profile_id: int, module_id: str) -> object:
        lesson = type(
            "LessonProgress",
            (),
            {
                "lesson_id": "navigation",
                "title": "Navigation",
                "order": 1,
                "total_cards": 2,
                "attempted_cards": 1,
                "correct_cards": 1,
            },
        )()
        return type(
            "ModuleProgression",
            (),
            {
                "module_id": module_id,
                "module_title": "Base",
                "stage": "started",
                "total_cards": 2,
                "attempted_cards": 1,
                "correct_cards": 1,
                "lessons": (lesson,),
            },
        )()

    def practice_queue(self, profile_id: int, limit: int = 30) -> list[object]:
        return [
            type(
                "Q",
                (),
                {
                    "status": "due",
                    "module_id": "base-linux",
                    "card_id": "c",
                    "due_at": "2026-01-01T00:00:00+00:00",
                    "streak": 1,
                    "spacing_score": 1.0,
                    "interval_minutes": 10,
                    "seen_count": 1,
                    "prompt": "p",
                    "command": "pwd",
                },
            )()
        ]

    def force_unlock_module_with_dependencies(self, profile_id: int, module_id: str) -> list[str]:
        return ["base-linux", module_id]

    def export_profile(self, profile_id: int, export_path: str) -> object:
        return type(
            "TransferSummary",
            (),
            {"profile_id": profile_id, "profile_name": "alice", "module_rows": 1, "card_rows": 2, "attempt_rows": 3},
        )()

    def import_profile(self, import_path: str, profile_name: str | None) -> object:
        name = profile_name if profile_name is not None else "imported-alice"
        return type(
            "TransferSummary",
            (),
            {"profile_id": 2, "profile_name": name, "module_rows": 1, "card_rows": 2, "attempt_rows": 3},
        )()

    def correct_card_ids_for_module(self, profile_id: int, module_id: str) -> set[str]:
        return set(self.correct_ids_by_module.get(module_id, set()))


# ── play_shell tests ───────────────────────────────────────────────────────────


def test_run_enters_play_shell(monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "play_shell", lambda: 0)
    assert main.run([]) == 0


def test_play_shell_basic_flow(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    outputs: list[str] = []

    # c=create profile, "alice"=readline name, q=quit main menu
    code = main.play_shell(reader=_reader("c", "alice", "q"), print_fn=outputs.append)
    assert code == 0
    assert service.closed is True


def test_play_shell_invalid_key_ignored_then_quit(monkeypatch: Any) -> None:
    """An unrecognised key on the main menu is silently ignored."""
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    outputs: list[str] = []
    # c=create profile, "alice"=name, "9"=invalid key (ignored), q=quit
    code = main.play_shell(reader=_reader("c", "alice", "9", "q"), print_fn=outputs.append)
    assert code == 0
    # No "Invalid choice." message should appear
    assert not any("Invalid choice." in line for line in outputs)


def test_play_shell_switch_profile(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    outputs: list[str] = []
    code = main.play_shell(reader=_reader("c", "alice", "b", "c", "bob", "q"), print_fn=outputs.append)
    assert code == 0
    assert any("Profile: bob" in line for line in outputs)


def test_play_shell_calls_menu_handlers(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    called = {"learn": 0, "practice": 0, "status": 0, "admin": 0}
    monkeypatch.setattr(main, "_learn_module_flow", lambda *args, **kwargs: called.__setitem__("learn", 1))
    monkeypatch.setattr(main, "_general_practice_flow", lambda *args, **kwargs: called.__setitem__("practice", 1))
    monkeypatch.setattr(main, "_status_flow", lambda *args, **kwargs: called.__setitem__("status", 1))
    monkeypatch.setattr(main, "_admin_flow", lambda *args, **kwargs: called.__setitem__("admin", 1))

    code = main.play_shell(reader=_reader("c", "alice", "1", "2", "3", "4", "q"), print_fn=lambda _: None)
    assert code == 0
    assert called == {"learn": 1, "practice": 1, "status": 1, "admin": 1}


def test_play_shell_quit_at_profile_selection(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    outputs: list[str] = []
    code = main.play_shell(reader=_reader("q"), print_fn=outputs.append)
    assert code == 0
    assert service.closed is True


# ── Learn module flow tests ────────────────────────────────────────────────────


def test_learn_module_flow(monkeypatch: Any) -> None:
    service = DummyService()
    outputs: list[str] = []
    # 1=select module, "bad"=wrong card answer, "pwd"=correct
    main._learn_module_flow(service, 1, _reader("1", "bad", "pwd"), outputs.append)
    assert any("Module completed" in line for line in outputs)


def test_learn_module_flow_invalid_key_ignored() -> None:
    """An invalid key on the module list is silently ignored; back exits cleanly."""
    service = DummyService()
    outputs: list[str] = []
    # "x" is invalid (ignored), "b" exits
    main._learn_module_flow(service, 1, _reader("x", "b"), outputs.append)
    assert any("=== Learn Module ===" in line for line in outputs)
    assert not any("Invalid choice." in line for line in outputs)


def test_learn_module_flow_out_of_range_key_ignored() -> None:
    """A digit that exceeds the list length is silently ignored; back exits cleanly."""
    service = DummyService()
    outputs: list[str] = []
    # "9" out of range (1 module), "b" exits
    main._learn_module_flow(service, 1, _reader("9", "b"), outputs.append)
    assert any("=== Learn Module ===" in line for line in outputs)
    assert not any("Invalid choice." in line for line in outputs)


def test_learn_module_flow_back_from_menu() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._learn_module_flow(service, 1, _reader("b"), outputs.append)
    assert any("=== Learn Module ===" in line for line in outputs)


def test_learn_module_flow_back_during_card() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._learn_module_flow(service, 1, _reader("1", ":back"), outputs.append)
    assert any("Leaving module. Progress saved." in line for line in outputs)


def test_learn_module_flow_quit_during_card() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._learn_module_flow(service, 1, _reader("1", ":exit"), outputs.append)
    assert any("Leaving module. Progress saved." in line for line in outputs)


def test_learn_module_flow_no_unlocked() -> None:
    class LockedService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            module = type("M", (), {"id": "m", "title": "M", "prerequisites": ["base-linux"]})()
            state = type(
                "S",
                (),
                {"module": module, "unlocked": False, "started": False, "completed": False, "outdated": False},
            )()
            return [state]

    service = LockedService()
    outputs: list[str] = []
    main._learn_module_flow(service, 1, _reader(), outputs.append)
    assert any("No unlocked modules" in line for line in outputs)


def test_learn_module_flow_shows_locked_and_back_from_module_select() -> None:
    class MixedService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            unlocked_module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
            locked_module = type("M", (), {"id": "apt", "title": "APT", "prerequisites": ["base-linux"]})()
            unlocked = type(
                "S",
                (),
                {"module": unlocked_module, "unlocked": True, "started": False, "completed": False, "outdated": False},
            )()
            locked = type(
                "S",
                (),
                {"module": locked_module, "unlocked": False, "started": False, "completed": False, "outdated": False},
            )()
            return [unlocked, locked]

    outputs: list[str] = []
    main._learn_module_flow(MixedService(), 1, _reader("b"), outputs.append)
    assert any("Locked Modules" in line for line in outputs)
    assert any("apt" in line for line in outputs)


def test_learn_module_flow_quit_from_module_select() -> None:
    service = DummyService()
    outputs: list[str] = []
    try:
        main._learn_module_flow(service, 1, _reader("q"), outputs.append)
        raise AssertionError("Expected QuitApp.")
    except main.QuitApp:
        pass


def test_learn_module_flow_started_module_restart_option() -> None:
    class StartedService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
            state = type(
                "S",
                (),
                {"module": module, "unlocked": True, "started": True, "completed": False, "outdated": False},
            )()
            return [state]

    service = StartedService()
    outputs: list[str] = []
    # 1=select module, r=restart, pwd=correct answer
    main._learn_module_flow(service, 1, _reader("1", "r", "pwd"), outputs.append)
    assert any("Module completed" in line for line in outputs)


def test_learn_module_flow_pagination() -> None:
    """Next/prev page navigation works correctly for large module lists."""

    class ManyModulesService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            states = []
            for i in range(11):
                module = type("M", (), {"id": f"mod-{i:02d}", "title": f"Module {i}", "prerequisites": []})()
                state = type(
                    "S",
                    (),
                    {"module": module, "unlocked": True, "started": False, "completed": False, "outdated": False},
                )()
                states.append(state)
            return states

        def begin_module(self, profile_id: int, module_id: str) -> object:
            card = type("Card", (), {"id": "c", "prompt": "p", "answers": ["pwd"], "explanation": ""})()
            lesson = type("Lesson", (), {"order": 1, "title": "L", "cards": [card]})()
            return type("Module", (), {"id": module_id, "title": "T", "description": "D", "lessons": [lesson]})()

    outputs: list[str] = []
    # "n"=next page, "2"=select item 2 on page 2 (mod-10), "pwd"=card answer
    main._learn_module_flow(ManyModulesService(), 1, _reader("n", "2", "pwd"), outputs.append)
    assert any("Page 1/2" in line for line in outputs)
    assert any("Page 2/2" in line for line in outputs)
    # Page 2 rows must be numbered per-page (1, 2) to match the 1-9 keys the
    # user presses — not a continuing global count (10, 11).
    assert any(line.lstrip().startswith("1 mod-09") for line in outputs)
    assert any(line.lstrip().startswith("2 mod-10") for line in outputs)
    assert not any(line.lstrip().startswith("10 mod-09") for line in outputs)
    assert any("Module completed" in line for line in outputs)


# ── Outdated module flow tests ─────────────────────────────────────────────────


def test_general_practice_flow_show_answer() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._general_practice_flow(service, 1, _reader(":show", "pwd"), outputs.append)
    assert any("Round complete" in line for line in outputs)


def test_general_practice_flow_back_early() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._general_practice_flow(service, 1, _reader(":back"), outputs.append)
    assert any("Round ended early" in line for line in outputs)


def test_general_practice_flow_quit_early_alias() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._general_practice_flow(service, 1, _reader(":q"), outputs.append)
    assert any("Round ended early" in line for line in outputs)


def test_general_practice_bare_back_is_not_exit_command() -> None:
    """'back' without a colon must be treated as an incorrect answer, not an exit command."""
    outputs: list[str] = []
    main._general_practice_flow(DummyService(), 1, _reader("back"), outputs.append)
    assert any("Incorrect" in line for line in outputs)
    assert not any("Round ended early" in line for line in outputs)


def test_general_practice_no_cards() -> None:
    class EmptyService(DummyService):
        def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
            return []

    outputs: list[str] = []
    service = EmptyService()
    main._general_practice_flow(service, 1, _reader(), outputs.append)
    assert any("No cards available" in line for line in outputs)


def test_module_details_flow_commands() -> None:
    service = DummyService()
    outputs: list[str] = []
    # 1=select module, 1=commands detail, b=back from detail loop
    main._module_details_flow(service, 1, _reader("1", "1", "b"), outputs.append)
    assert any("Module Details" in line for line in outputs)
    assert any("Commands in Base" in line for line in outputs)
    assert any("pwd: none" in line for line in outputs)


def test_queue_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._queue_flow(service, 1, outputs.append)
    assert any("Practice Queue" in line for line in outputs)
    assert any("Due (local)" in line for line in outputs)
    assert any("Command" in line for line in outputs)
    assert any("pwd" in line for line in outputs)


def test_admin_flow_routes_subcommands() -> None:
    service = DummyService()
    outputs: list[str] = []
    # 1=module details, 1=select module, b=back from detail loop
    # 2=queue, 3=force unlock, 1=select module
    # 4=export, "backup.json"=path, b=back from admin
    main._admin_flow(service, 1, _reader("1", "1", "b", "2", "3", "1", "4", "backup.json", "b"), outputs.append)
    assert any("Admin" in line for line in outputs)
    assert any("Force Unlock" in line for line in outputs)
    assert any("Module Details" in line for line in outputs)
    assert any("Exported profile" in line for line in outputs)


def test_force_unlock_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._force_unlock_flow(service, 1, _reader("1"), outputs.append)
    assert any("Force unlocked modules" in line for line in outputs)
    assert any("- base-linux" in line for line in outputs)


def test_force_unlock_flow_invalid_key_ignored() -> None:
    """An invalid key is silently ignored; back exits the flow."""
    service = DummyService()
    outputs: list[str] = []
    main._force_unlock_flow(service, 1, _reader("x", "b"), outputs.append)
    assert any("Force Unlock" in line for line in outputs)
    assert not any("Invalid choice." in line for line in outputs)


def test_force_unlock_flow_back() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._force_unlock_flow(service, 1, _reader("b"), outputs.append)
    assert any("Force Unlock" in line for line in outputs)


def test_queue_flow_empty() -> None:
    class EmptyQueueService(DummyService):
        def practice_queue(self, profile_id: int, limit: int = 30) -> list[object]:
            return []

    outputs: list[str] = []
    main._queue_flow(EmptyQueueService(), 1, outputs.append)
    assert any("No queued cards yet" in line for line in outputs)


def test_status_flow_prints_module_state() -> None:
    service = DummyService()
    outputs: list[str] = []

    main._status_flow(service, 1, outputs.append)
    assert any("Module" in line and "Prerequisites" in line and "Missing" not in line for line in outputs)
    assert any("base-linux" in line for line in outputs)
    assert any("none" in line for line in outputs)


def test_status_flow_prints_missing_prerequisites() -> None:
    class DependencyService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            base_module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
            compose_module = type("M", (), {"id": "docker-compose", "title": "Compose", "prerequisites": ["docker"]})()
            base_state = type(
                "S",
                (),
                {"module": base_module, "unlocked": True, "started": False, "completed": False, "outdated": False},
            )()
            compose_state = type(
                "S",
                (),
                {"module": compose_module, "unlocked": False, "started": False, "completed": False, "outdated": False},
            )()
            return [base_state, compose_state]

    outputs: list[str] = []
    main._status_flow(DependencyService(), 1, outputs.append)
    assert any("*docker" in line and "locked" in line for line in outputs)


# ── Profile selection tests ────────────────────────────────────────────────────


def test_select_profile_invalid_then_create(monkeypatch: Any) -> None:
    service = DummyService()
    outputs: list[str] = []
    # "x" is ignored, "c"=create, "alice"=name
    selected = main._select_profile(service, _reader("x", "c", "alice"), outputs.append, allow_cancel=False)
    assert selected is not None
    profile_id, name = selected
    assert profile_id == 1
    assert name == "alice"


def test_select_profile_existing() -> None:
    class ExistingService(DummyService):
        def list_profiles(self) -> list[object]:
            return [type("Profile", (), {"id": 11, "name": "eve"})()]

    service = ExistingService()
    selected = main._select_profile(service, _reader("1"), lambda _: None, allow_cancel=False)
    assert selected is not None
    profile_id, name = selected
    assert profile_id == 11
    assert name == "eve"


def test_select_profile_cancel_returns_none() -> None:
    service = DummyService()
    selected = main._select_profile(service, _reader("q"), lambda _: None, allow_cancel=True)
    assert selected is None


def test_select_profile_empty_name_and_create_error() -> None:
    class FailingCreateService(DummyService):
        def create_profile(self, name: str) -> object:
            raise RuntimeError("boom")

    outputs: list[str] = []
    service = FailingCreateService()
    # c=create, ""=empty name (rejected), c=create again, "alice"=name (create fails), q=quit
    selected = main._select_profile(service, _reader("c", "", "c", "alice", "q"), outputs.append, allow_cancel=False)
    assert selected is None
    assert any("Profile name is required." in line for line in outputs)
    assert any("Could not create profile" in line for line in outputs)


def test_select_profile_delete_confirmed() -> None:
    service = DummyService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    # d=delete, 1=select alice, "YES"=confirm, q=quit
    selected = main._select_profile(service, _reader("d", "1", "YES", "q"), outputs.append, allow_cancel=False)
    assert selected is None
    assert any("Deleted profile 'alice'." in line for line in outputs)


def test_select_profile_delete_cancelled() -> None:
    service = DummyService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    # d=delete, 1=select alice, "nope"=not YES (cancelled), 1=select alice for login
    selected = main._select_profile(service, _reader("d", "1", "nope", "1"), outputs.append, allow_cancel=False)
    assert selected is not None
    assert any("Deletion cancelled." in line for line in outputs)


def test_select_profile_delete_invalid_key_ignored() -> None:
    """An invalid key in the delete sub-menu is silently ignored."""
    service = DummyService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    # d=delete, "x"=invalid key (ignored), b=back from delete, 1=select alice
    selected = main._select_profile(service, _reader("d", "x", "b", "1"), outputs.append, allow_cancel=False)
    assert selected is not None
    assert not any("Invalid choice." in line for line in outputs)


def test_select_profile_import_option() -> None:
    service = DummyService()
    outputs: list[str] = []
    # i=import, "backup.json"=path, "imported"=name, q=quit
    selected = main._select_profile(
        service, _reader("i", "backup.json", "imported", "q"), outputs.append, allow_cancel=False
    )
    assert selected is None
    assert any("Imported profile 'imported'" in line for line in outputs)


def test_select_profile_pagination() -> None:
    """Profile list pages correctly with > and < keys."""

    class ManyProfilesService(DummyService):
        def list_profiles(self) -> list[object]:
            return [type("Profile", (), {"id": i, "name": f"user-{i:02d}"})() for i in range(1, 12)]

    outputs: list[str] = []
    # "n"=next page, "1"=select first item on page 2 (user-10)
    selected = main._select_profile(ManyProfilesService(), _reader("n", "1"), outputs.append, allow_cancel=False)
    assert selected is not None
    assert selected[1] == "user-10"
    assert any("Page 1/2" in line for line in outputs)
    assert any("Page 2/2" in line for line in outputs)


# ── Module details tests ───────────────────────────────────────────────────────


def test_module_details_flow_lessons() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._module_details_flow(service, 1, _reader("1", "2", "b"), outputs.append)
    assert any("Module Details" in line for line in outputs)
    assert any("Lessons in Base" in line for line in outputs)
    assert any("navigation" in line for line in outputs)


def test_module_details_flow_progression() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._module_details_flow(service, 1, _reader("1", "3", "b"), outputs.append)
    assert any("Progression in Base" in line for line in outputs)
    assert any("Stage: started" in line for line in outputs)
    assert any("By lesson" in line for line in outputs)


def test_module_details_flow_invalid_key_at_module_list_ignored() -> None:
    """Invalid key on the module-selection list is silently ignored."""
    service = DummyService()
    outputs: list[str] = []
    # "x"=invalid (ignored), "b"=back from module list
    main._module_details_flow(service, 1, _reader("x", "b"), outputs.append)
    assert not any("Invalid choice." in line for line in outputs)


def test_module_details_flow_invalid_key_at_detail_menu_ignored() -> None:
    """Invalid key inside the detail sub-menu is silently ignored."""
    service = DummyService()
    outputs: list[str] = []
    # "1"=select module, "9"=invalid in detail menu (ignored), "b"=back
    main._module_details_flow(service, 1, _reader("1", "9", "b"), outputs.append)
    assert any("Module Details" in line for line in outputs)
    assert not any("Invalid choice." in line for line in outputs)


# ── Export / import tests ──────────────────────────────────────────────────────


def test_export_profile_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._export_profile_flow(service, 1, _reader("backup.json"), outputs.append)
    assert any("Exported profile 'alice'" in line for line in outputs)
    assert any("module rows: 1" in line for line in outputs)


def test_import_profile_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._import_profile_flow(service, _reader("backup.json", "new-name"), outputs.append)
    assert any("Imported profile 'new-name'" in line for line in outputs)


def test_import_export_flow_empty_path_validation() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._export_profile_flow(service, 1, _reader(""), outputs.append)
    assert any("File path is required." in line for line in outputs)
    outputs = []
    main._import_profile_flow(service, _reader(""), outputs.append)
    assert any("File path is required." in line for line in outputs)


# ── Grouped outdated module tests ──────────────────────────────────────────────


def test_learn_module_flow_grouped_outdated_modules() -> None:
    class OutdatedService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
            state = type(
                "S",
                (),
                {"module": module, "unlocked": True, "started": True, "completed": True, "outdated": True},
            )()
            return [state]

    service = OutdatedService()
    outputs: list[str] = []
    # g=grouped outdated, ""=any key to start updates, "pwd"=card answer
    main._learn_module_flow(service, 1, _reader("g", "", "pwd"), outputs.append)
    assert any("Grouped Outdated Modules" in line for line in outputs)
    assert any("Outdated module update complete" in line for line in outputs)


def test_learn_outdated_modules_flow_none_and_cancel_and_quit() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._learn_outdated_modules_flow(service, 1, _reader(), outputs.append)
    assert any("No outdated modules" in line for line in outputs)

    class OutdatedService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
            state = type(
                "S",
                (),
                {"module": module, "unlocked": True, "started": True, "completed": True, "outdated": True},
            )()
            return [state]

    outputs = []
    main._learn_outdated_modules_flow(OutdatedService(), 1, _reader("b"), outputs.append)
    assert any("Grouped Outdated Modules" in line for line in outputs)

    outputs = []
    try:
        main._learn_outdated_modules_flow(OutdatedService(), 1, _reader("q"), outputs.append)
        raise AssertionError("Expected QuitApp.")
    except main.QuitApp:
        pass


def test_learn_outdated_modules_flow_stops_early() -> None:
    class OutdatedService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            module = type("M", (), {"id": "base-linux", "title": "Base", "prerequisites": []})()
            state = type(
                "S",
                (),
                {"module": module, "unlocked": True, "started": True, "completed": True, "outdated": True},
            )()
            return [state]

    outputs: list[str] = []
    # ""=any key to start, then :back during card
    main._learn_outdated_modules_flow(OutdatedService(), 1, _reader("", ":back"), outputs.append)
    assert any("Stopped early after updating 0 module(s)." in line for line in outputs)


# ── Guided module / card tests ─────────────────────────────────────────────────


def test_run_guided_module_skips_mastered_cards() -> None:
    service = DummyService()
    service.correct_ids_by_module["base-linux"] = {"c"}
    outputs: list[str] = []
    module = service.begin_module(1, "base-linux")
    main._run_guided_module(service, 1, module, _reader("pwd"), outputs.append)
    assert any("Skipped 1 previously mastered card" in line for line in outputs)


def test_run_guided_module_restart_does_not_skip_mastered() -> None:
    service = DummyService()
    service.correct_ids_by_module["base-linux"] = {"c"}
    outputs: list[str] = []
    module = service.begin_module(1, "base-linux")
    main._run_guided_module(service, 1, module, _reader("pwd"), outputs.append, restart=True)
    assert not any("Skipped 1 previously mastered card" in line for line in outputs)


def test_run_guided_module_progress_saved_branch() -> None:
    class NoCompleteService(DummyService):
        def complete_module_if_mastered(self, profile_id: int, module: object) -> bool:
            return False

    outputs: list[str] = []
    service = NoCompleteService()
    module = service.begin_module(1, "base-linux")
    main._run_guided_module(service, 1, module, _reader("pwd"), outputs.append)
    assert any("Module progress saved." in line for line in outputs)


def test_run_guided_card_with_alternatives() -> None:
    outputs: list[str] = []
    service = DummyService()
    card = type("Card", (), {"id": "c", "prompt": "p", "answers": ["pwd", "pwd -L"], "explanation": "e"})()
    result = main._run_guided_card(service, 1, card, _reader("pwd"), outputs.append)
    assert result is True
    assert any("Also accepted:" in line for line in outputs)
    assert any("- pwd -L" in line for line in outputs)


# ── General practice continue-prompt tests ────────────────────────────────────


def test_general_practice_incorrect_and_show_exit() -> None:
    class WrongService(DummyService):
        def record_answer(self, profile_id: int, card: object, user_input: str) -> bool:
            return False

    outputs: list[str] = []
    main._general_practice_flow(WrongService(), 1, _reader("bad"), outputs.append)
    assert any("Incorrect. Expected e.g." in line for line in outputs)

    outputs = []
    main._general_practice_flow(DummyService(), 1, _reader(":show", ":exit"), outputs.append)
    assert any("Round ended early" in line for line in outputs)


def test_general_practice_shows_due_count_at_start() -> None:
    """The total due count is shown at the start, before the first round."""

    class StartService(DummyService):
        def count_due_cards(self, profile_id: int) -> int:
            return 3

    outputs: list[str] = []
    # pwd=answer round 1, q=stop at the continue prompt
    main._general_practice_flow(StartService(), 1, _reader("pwd", "q"), outputs.append)
    start_index = next(i for i, line in enumerate(outputs) if "Cards due: 3" in line)
    round_index = next(i for i, line in enumerate(outputs) if "Round complete" in line)
    assert start_index < round_index
    # The start count must not be duplicated on later rounds (post-batch already shows remaining).
    assert sum(1 for line in outputs if "Cards due: 3" in line) == 1


def test_general_practice_shows_practicing_ahead_at_start() -> None:
    """When nothing is currently due, the start banner says practicing ahead."""
    outputs: list[str] = []
    # DummyService.count_due_cards returns 0 with a single practice-ahead card.
    main._general_practice_flow(DummyService(), 1, _reader("pwd"), outputs.append)
    assert any("practising ahead" in line.lower() for line in outputs)


def test_general_practice_continue_prompt_due_cards() -> None:
    """Continue prompt shows due count; Enter continues, q stops."""

    class MultiRoundService(DummyService):
        def __init__(self) -> None:
            super().__init__()
            self._round = 0

        def count_due_cards(self, profile_id: int) -> int:
            return 3

        def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
            self._round += 1
            card = type("Card", (), {"id": f"c{self._round}", "prompt": "p", "answers": ["pwd"], "explanation": ""})()
            return [card]

    outputs: list[str] = []
    # pwd=answer round 1, ""=any key continues, pwd=answer round 2, q=stop
    main._general_practice_flow(MultiRoundService(), 1, _reader("pwd", "", "pwd", "q"), outputs.append)
    assert any("3 more cards due" in line for line in outputs)
    assert sum(1 for line in outputs if "Round complete" in line) == 2


def test_general_practice_continue_prompt_future_only() -> None:
    """Continue prompt shows 'no more due' when only future cards remain."""

    class FutureService(DummyService):
        def __init__(self) -> None:
            super().__init__()
            self._round = 0

        def count_due_cards(self, profile_id: int) -> int:
            return 0

        def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
            self._round += 1
            if self._round > 2:
                return []
            card = type("Card", (), {"id": f"c{self._round}", "prompt": "p", "answers": ["pwd"], "explanation": ""})()
            return [card]

    outputs: list[str] = []
    # pwd=answer, b=stop at continue prompt
    main._general_practice_flow(FutureService(), 1, _reader("pwd", "b"), outputs.append)
    assert any("No more cards due" in line for line in outputs)


@pytest.mark.parametrize(  # type: ignore[misc]
    "stop_key",
    ["b", "q"],
)
def test_general_practice_continue_stop_keys(stop_key: str) -> None:
    """b and q must stop practice at the continue prompt."""

    class InfiniteService(DummyService):
        def __init__(self) -> None:
            super().__init__()
            self._round = 0

        def count_due_cards(self, profile_id: int) -> int:
            return 1

        def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
            self._round += 1
            card = type("Card", (), {"id": f"c{self._round}", "prompt": "p", "answers": ["pwd"], "explanation": ""})()
            return [card]

    outputs: list[str] = []
    main._general_practice_flow(InfiniteService(), 1, _reader("pwd", stop_key), outputs.append)
    assert sum(1 for line in outputs if "Round complete" in line) == 1


def test_general_practice_no_continue_prompt_when_queue_empty() -> None:
    """No continue prompt when the queue is exhausted after a round."""
    outputs: list[str] = []
    main._general_practice_flow(DummyService(), 1, _reader("pwd"), outputs.append)
    assert any("Round complete" in line for line in outputs)
    assert not any("[Enter] Continue" in line for line in outputs)


# ── Formatting utility tests ───────────────────────────────────────────────────


def test_format_interval_boundaries() -> None:
    assert main._format_interval(0) == "-"
    assert main._format_interval(-5) == "-"
    assert main._format_interval(1) == "1m"
    assert main._format_interval(119) == "119m"
    assert main._format_interval(120) == "2.0h"
    assert main._format_interval(90) == "90m"
    assert main._format_interval(1440) == "24.0h"
    assert main._format_interval(2879) == "48.0h"
    assert main._format_interval(2880) == "2.0d"


def test_main_entry_exits(monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "run", lambda argv=None: 0)
    try:
        main.main_entry()
    except SystemExit as exc:
        assert exc.code == 0


# ── Paginated select direct tests ─────────────────────────────────────────────


def test_paginated_select_next_prev_and_quit() -> None:
    """paginated_select navigates pages and raises QuitApp on q."""
    items = list(range(11))  # 11 items → 2 pages (9 + 2)
    outputs: list[str] = []

    # "n"=next page, "p"=prev page, "q"=quit
    try:
        main._paginated_select(items, _reader("n", "p", "q"), outputs.append, format_fn=str)
        raise AssertionError("Expected QuitApp.")
    except main.QuitApp:
        pass

    assert any("Page 1/2" in line for line in outputs)
    assert any("Page 2/2" in line for line in outputs)
    # Verify prev-page footer appeared (page > 0)
    assert any("[p] Prev" in line for line in outputs)


def test_paginated_select_select_from_page_2() -> None:
    """Selection on page 2 returns the correct item."""
    items = [f"item-{i}" for i in range(11)]  # 11 items
    outputs: list[str] = []

    # "n"=next page, "2"=select item 2 on page 2 (index 10 → "item-10")
    result = main._paginated_select(items, _reader("n", "2"), outputs.append, format_fn=str)
    assert result == "item-10"


# ── play_shell QuitApp and switch-profile-quit tests ──────────────────────────


def test_play_shell_quitapp_from_submenu(monkeypatch: Any) -> None:
    """QuitApp raised inside a submenu is caught by play_shell."""
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)

    def raise_quit(*args: object, **kwargs: object) -> None:
        raise main.QuitApp()

    monkeypatch.setattr(main, "_learn_module_flow", raise_quit)
    code = main.play_shell(reader=_reader("c", "alice", "1"), print_fn=lambda _: None)
    assert code == 0


def test_play_shell_switch_profile_returns_none(monkeypatch: Any) -> None:
    """Quitting at the switch-profile screen exits the app."""
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    # c=create, "alice"=name, b=switch profile screen, q=quit at profile screen
    code = main.play_shell(reader=_reader("c", "alice", "b", "q"), print_fn=lambda _: None)
    assert code == 0


# ── Admin / module-details QuitApp tests ──────────────────────────────────────


def test_admin_flow_quit_propagates() -> None:
    """q in the admin menu raises QuitApp."""
    service = DummyService()
    outputs: list[str] = []
    try:
        main._admin_flow(service, 1, _reader("q"), outputs.append)
        raise AssertionError("Expected QuitApp.")
    except main.QuitApp:
        pass


def test_module_details_flow_quit_in_detail_menu() -> None:
    """q in the detail sub-menu raises QuitApp."""
    service = DummyService()
    outputs: list[str] = []
    try:
        main._module_details_flow(service, 1, _reader("1", "q"), outputs.append)
        raise AssertionError("Expected QuitApp.")
    except main.QuitApp:
        pass


# ── Export / import error-path tests ──────────────────────────────────────────


def test_export_profile_flow_error() -> None:
    class FailExportService(DummyService):
        def export_profile(self, profile_id: int, export_path: str) -> object:
            raise OSError("disk full")

    outputs: list[str] = []
    main._export_profile_flow(FailExportService(), 1, _reader("out.json"), outputs.append)
    assert any("Export failed" in line for line in outputs)


def test_import_profile_flow_error() -> None:
    class FailImportService(DummyService):
        def import_profile(self, import_path: str, profile_name: str | None) -> object:
            raise OSError("not found")

    outputs: list[str] = []
    main._import_profile_flow(FailImportService(), _reader("in.json", "name"), outputs.append)
    assert any("Import failed" in line for line in outputs)


# ── Misc edge-case tests ───────────────────────────────────────────────────────


def test_delete_profile_flow_no_profiles() -> None:
    """Delete flow shows a message when no profiles exist."""
    service = DummyService()  # no profiles created
    outputs: list[str] = []
    main._delete_profile_flow(service, _reader(), outputs.append)
    assert any("No profiles available to delete." in line for line in outputs)


def test_delete_profile_flow_profile_not_found() -> None:
    """Delete flow handles the case where the profile vanishes between list and delete."""

    class GhostDeleteService(DummyService):
        def delete_profile(self, profile_id: int) -> bool:
            return False  # simulates already-deleted profile

    service = GhostDeleteService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    main._delete_profile_flow(service, _reader("1", "YES"), outputs.append)
    assert any("Profile was not found." in line for line in outputs)


def test_module_lessons_flow_no_lessons() -> None:
    """Lessons view handles a module with no lessons."""

    class NoLessonsService(DummyService):
        def list_module_lesson_references(self, module_id: str) -> list[object]:
            return []

    outputs: list[str] = []
    module = type("M", (), {"id": "base-linux", "title": "Base"})()
    main._module_lessons_flow(NoLessonsService(), module, outputs.append)  # type: ignore[arg-type]
    assert any("No lessons defined." in line for line in outputs)


def test_module_progression_flow_no_lessons() -> None:
    """Progression view handles a module with no lesson breakdown."""

    class NoLessonProgressionService(DummyService):
        def get_module_progression(self, profile_id: int, module_id: str) -> object:
            return type(
                "P",
                (),
                {
                    "stage": "new",
                    "total_cards": 0,
                    "attempted_cards": 0,
                    "correct_cards": 0,
                    "lessons": [],
                },
            )()

    outputs: list[str] = []
    module = type("M", (), {"id": "base-linux", "title": "Base"})()
    main._module_progression_flow(NoLessonProgressionService(), 1, module, outputs.append)  # type: ignore[arg-type]
    assert any("Progression in Base" in line for line in outputs)
    assert not any("By lesson" in line for line in outputs)


def test_format_local_due_invalid_returns_raw() -> None:
    """_format_local_due returns the raw string when it cannot be parsed."""
    assert main._format_local_due("not-a-date") == "not-a-date"


def test_learn_module_flow_prev_page() -> None:
    """Prev-page navigation works in the learn module list."""

    class ManyModulesService(DummyService):
        def list_module_states(self, profile_id: int) -> list[object]:
            states = []
            for i in range(11):
                module = type("M", (), {"id": f"mod-{i:02d}", "title": f"Module {i}", "prerequisites": []})()
                state = type(
                    "S",
                    (),
                    {"module": module, "unlocked": True, "started": False, "completed": False, "outdated": False},
                )()
                states.append(state)
            return states

        def begin_module(self, profile_id: int, module_id: str) -> object:
            card = type("Card", (), {"id": "c", "prompt": "p", "answers": ["pwd"], "explanation": ""})()
            lesson = type("Lesson", (), {"order": 1, "title": "L", "cards": [card]})()
            return type("Module", (), {"id": module_id, "title": "T", "description": "D", "lessons": [lesson]})()

    outputs: list[str] = []
    # n=next page, p=prev page (back to page 1), 1=select first item, pwd=answer
    main._learn_module_flow(ManyModulesService(), 1, _reader("n", "p", "1", "pwd"), outputs.append)
    assert any("Page 1/2" in line for line in outputs)
    assert any("Module completed" in line for line in outputs)
