from typing import Any

import cmdtrainer.main as main


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

    def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
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


def test_run_enters_play_shell(monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "play_shell", lambda: 0)
    assert main.run([]) == 0


def test_play_shell_basic_flow(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)

    inputs = iter(["n", "alice", "q"])
    outputs: list[str] = []

    code = main.play_shell(input_fn=lambda _: next(inputs), print_fn=outputs.append)
    assert code == 0
    assert service.closed is True


def test_play_shell_invalid_choice_then_quit(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    inputs = iter(["n", "alice", "9", "q"])
    outputs: list[str] = []
    code = main.play_shell(input_fn=lambda _: next(inputs), print_fn=outputs.append)
    assert code == 0
    assert any("Invalid choice." in line for line in outputs)


def test_play_shell_switch_profile(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    inputs = iter(["n", "alice", "b", "n", "bob", "q"])
    outputs: list[str] = []
    code = main.play_shell(input_fn=lambda _: next(inputs), print_fn=outputs.append)
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

    inputs = iter(["n", "alice", "1", "2", "3", "4", "q"])
    code = main.play_shell(input_fn=lambda _: next(inputs), print_fn=lambda _: None)
    assert code == 0
    assert called == {"learn": 1, "practice": 1, "status": 1, "admin": 1}


def test_play_shell_quit_at_profile_selection(monkeypatch: Any) -> None:
    service = DummyService()
    monkeypatch.setattr(main, "_service", lambda: service)
    outputs: list[str] = []
    code = main.play_shell(input_fn=lambda _: "q", print_fn=outputs.append)
    assert code == 0
    assert service.closed is True


def test_learn_module_flow(monkeypatch: Any) -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["1", "bad", "pwd"])

    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Module completed" in line for line in outputs)


def test_learn_module_flow_invalid_choice_not_digit() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["x"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Invalid choice." in line for line in outputs)


def test_learn_module_flow_invalid_choice_range() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["999"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Invalid choice." in line for line in outputs)


def test_learn_module_flow_back_from_menu() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["b"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("=== Learn Module ===" in line for line in outputs)


def test_learn_module_flow_back_during_card() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["1", ":back"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Leaving module. Progress saved." in line for line in outputs)


def test_learn_module_flow_quit_during_card() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["1", ":exit"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
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
    main._learn_module_flow(service, 1, lambda _: "", outputs.append)
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
    inputs = iter(["b"])
    main._learn_module_flow(MixedService(), 1, lambda _: next(inputs), outputs.append)
    assert any("Locked Modules" in line for line in outputs)
    assert any("apt" in line for line in outputs)


def test_learn_module_flow_quit_from_module_select() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["q"])
    try:
        main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
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
    inputs = iter(["1", "r", "pwd"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Module completed" in line for line in outputs)


def test_general_practice_flow_show_answer() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter([":show", "pwd"])

    main._general_practice_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Round complete" in line for line in outputs)


def test_general_practice_flow_back_early() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._general_practice_flow(service, 1, lambda _: ":back", outputs.append)
    assert any("Round ended early" in line for line in outputs)


def test_general_practice_flow_quit_early_alias() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._general_practice_flow(service, 1, lambda _: ":q", outputs.append)
    assert any("Round ended early" in line for line in outputs)


def test_general_practice_no_cards() -> None:
    class EmptyService(DummyService):
        def due_cards(self, profile_id: int, limit: int = 10) -> list[object]:
            return []

    outputs: list[str] = []
    service = EmptyService()
    main._general_practice_flow(service, 1, lambda _: "", outputs.append)
    assert any("No cards available" in line for line in outputs)


def test_module_details_flow_commands() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["1", "1", "b"])
    main._module_details_flow(service, 1, lambda _: next(inputs), outputs.append)
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
    inputs = iter(["1", "1", "b", "2", "3", "1", "4", "backup.json", "b"])
    main._admin_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Admin" in line for line in outputs)
    assert any("Force Unlock" in line for line in outputs)
    assert any("Module Details" in line for line in outputs)
    assert any("Exported profile" in line for line in outputs)


def test_force_unlock_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._force_unlock_flow(service, 1, lambda _: "1", outputs.append)
    assert any("Force unlocked modules" in line for line in outputs)
    assert any("- base-linux" in line for line in outputs)


def test_force_unlock_flow_invalid_choice() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._force_unlock_flow(service, 1, lambda _: "x", outputs.append)
    assert any("Invalid choice." in line for line in outputs)


def test_force_unlock_flow_back() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._force_unlock_flow(service, 1, lambda _: "b", outputs.append)
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


def test_select_profile_invalid_then_create(monkeypatch: Any) -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["x", "n", "alice"])

    selected = main._select_profile(service, lambda _: next(inputs), outputs.append, allow_cancel=False)
    assert selected is not None
    profile_id, name = selected
    assert profile_id == 1
    assert name == "alice"


def test_select_profile_existing() -> None:
    class ExistingService(DummyService):
        def list_profiles(self) -> list[object]:
            return [type("Profile", (), {"id": 11, "name": "eve"})()]

    service = ExistingService()
    selected = main._select_profile(service, lambda _: "1", lambda _: None, allow_cancel=False)
    assert selected is not None
    profile_id, name = selected
    assert profile_id == 11
    assert name == "eve"


def test_select_profile_cancel_returns_none() -> None:
    service = DummyService()
    selected = main._select_profile(service, lambda _: "q", lambda _: None, allow_cancel=True)
    assert selected is None


def test_select_profile_empty_name_and_create_error() -> None:
    class FailingCreateService(DummyService):
        def create_profile(self, name: str) -> object:
            raise RuntimeError("boom")

    outputs: list[str] = []
    service = FailingCreateService()
    inputs = iter(["n", "", "n", "alice", "q"])
    selected = main._select_profile(service, lambda _: next(inputs), outputs.append, allow_cancel=False)
    assert selected is None
    assert any("Profile name is required." in line for line in outputs)
    assert any("Could not create profile" in line for line in outputs)


def test_select_profile_delete_confirmed() -> None:
    service = DummyService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    inputs = iter(["d", "1", "YES", "q"])
    selected = main._select_profile(service, lambda _: next(inputs), outputs.append, allow_cancel=False)
    assert selected is None
    assert any("Deleted profile 'alice'." in line for line in outputs)


def test_select_profile_delete_cancelled() -> None:
    service = DummyService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    inputs = iter(["d", "1", "nope", "1"])
    selected = main._select_profile(service, lambda _: next(inputs), outputs.append, allow_cancel=False)
    assert selected is not None
    assert any("Deletion cancelled." in line for line in outputs)


def test_select_profile_delete_invalid_choice() -> None:
    service = DummyService()
    _ = service.create_profile("alice")
    outputs: list[str] = []
    inputs = iter(["d", "x", "1"])
    selected = main._select_profile(service, lambda _: next(inputs), outputs.append, allow_cancel=False)
    assert selected is not None
    assert any("Invalid choice." in line for line in outputs)


def test_select_profile_import_option() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["i", "backup.json", "imported", "q"])
    selected = main._select_profile(service, lambda _: next(inputs), outputs.append, allow_cancel=False)
    assert selected is None
    assert any("Imported profile 'imported'" in line for line in outputs)


def test_module_details_flow_lessons() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["1", "2", "b"])
    main._module_details_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Module Details" in line for line in outputs)
    assert any("Lessons in Base" in line for line in outputs)
    assert any("navigation" in line for line in outputs)


def test_module_details_flow_progression() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["1", "3", "b"])
    main._module_details_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Progression in Base" in line for line in outputs)
    assert any("Stage: started" in line for line in outputs)
    assert any("By lesson" in line for line in outputs)


def test_module_details_flow_invalid_choices() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._module_details_flow(service, 1, lambda _: "x", outputs.append)
    assert any("Invalid choice." in line for line in outputs)

    outputs = []
    main._module_details_flow(service, 1, lambda _: "9", outputs.append)
    assert any("Invalid choice." in line for line in outputs)


def test_export_profile_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._export_profile_flow(service, 1, lambda _: "backup.json", outputs.append)
    assert any("Exported profile 'alice'" in line for line in outputs)
    assert any("module rows: 1" in line for line in outputs)


def test_import_profile_flow() -> None:
    service = DummyService()
    outputs: list[str] = []
    inputs = iter(["backup.json", "new-name"])
    main._import_profile_flow(service, lambda _: next(inputs), outputs.append)
    assert any("Imported profile 'new-name'" in line for line in outputs)


def test_import_export_flow_empty_path_validation() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._export_profile_flow(service, 1, lambda _: "", outputs.append)
    assert any("File path is required." in line for line in outputs)
    outputs = []
    main._import_profile_flow(service, lambda _: "", outputs.append)
    assert any("File path is required." in line for line in outputs)


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
    inputs = iter(["g", "", "pwd"])
    main._learn_module_flow(service, 1, lambda _: next(inputs), outputs.append)
    assert any("Grouped Outdated Modules" in line for line in outputs)
    assert any("Outdated module update complete" in line for line in outputs)


def test_learn_outdated_modules_flow_none_and_cancel_and_quit() -> None:
    service = DummyService()
    outputs: list[str] = []
    main._learn_outdated_modules_flow(service, 1, lambda _: "", outputs.append)
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
    main._learn_outdated_modules_flow(OutdatedService(), 1, lambda _: "b", outputs.append)
    assert any("Grouped Outdated Modules" in line for line in outputs)

    outputs = []
    try:
        main._learn_outdated_modules_flow(OutdatedService(), 1, lambda _: "q", outputs.append)
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
    inputs = iter(["", ":back"])
    main._learn_outdated_modules_flow(OutdatedService(), 1, lambda _: next(inputs), outputs.append)
    assert any("Stopped early after updating 0 module(s)." in line for line in outputs)


def test_run_guided_module_skips_mastered_cards() -> None:
    service = DummyService()
    service.correct_ids_by_module["base-linux"] = {"c"}
    outputs: list[str] = []
    module = service.begin_module(1, "base-linux")
    main._run_guided_module(service, 1, module, lambda _: "pwd", outputs.append)
    assert any("Skipped 1 previously mastered card" in line for line in outputs)


def test_run_guided_module_restart_does_not_skip_mastered() -> None:
    service = DummyService()
    service.correct_ids_by_module["base-linux"] = {"c"}
    outputs: list[str] = []
    module = service.begin_module(1, "base-linux")
    main._run_guided_module(service, 1, module, lambda _: "pwd", outputs.append, restart=True)
    assert not any("Skipped 1 previously mastered card" in line for line in outputs)


def test_run_guided_module_progress_saved_branch() -> None:
    class NoCompleteService(DummyService):
        def complete_module_if_mastered(self, profile_id: int, module: object) -> bool:
            return False

    outputs: list[str] = []
    service = NoCompleteService()
    module = service.begin_module(1, "base-linux")
    main._run_guided_module(service, 1, module, lambda _: "pwd", outputs.append)
    assert any("Module progress saved." in line for line in outputs)


def test_run_guided_card_with_alternatives() -> None:
    outputs: list[str] = []
    service = DummyService()
    card = type("Card", (), {"id": "c", "prompt": "p", "answers": ["pwd", "pwd -L"], "explanation": "e"})()
    result = main._run_guided_card(service, 1, card, lambda _: "pwd", outputs.append)
    assert result is True
    assert any("Also accepted:" in line for line in outputs)
    assert any("- pwd -L" in line for line in outputs)


def test_general_practice_incorrect_and_show_exit() -> None:
    class WrongService(DummyService):
        def record_answer(self, profile_id: int, card: object, user_input: str) -> bool:
            return False

    outputs: list[str] = []
    main._general_practice_flow(WrongService(), 1, lambda _: "bad", outputs.append)
    assert any("Incorrect. Expected e.g." in line for line in outputs)

    outputs = []
    inputs = iter([":show", ":exit"])
    main._general_practice_flow(DummyService(), 1, lambda _: next(inputs), outputs.append)
    assert any("Round ended early" in line for line in outputs)


def test_main_entry_exits(monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "run", lambda argv=None: 0)
    try:
        main.main_entry()
    except SystemExit as exc:
        assert exc.code == 0
