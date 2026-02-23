import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cmdtrainer.models import Card
from cmdtrainer.service import LearnService, _coerce_float, _coerce_int


def test_module_states_unlocking() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p1")

    states = {state.module.id: state for state in service.list_module_states(profile.id)}
    assert states["base-linux"].unlocked is True
    assert states["apt"].unlocked is False
    assert states["docker-context"].unlocked is False
    assert states["base-linux"].outdated is False


def test_delete_profile_via_service() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("to-delete")
    service.progress.mark_module_started(profile.id, "base-linux")
    service.progress.record_attempt(profile.id, "card-delete", "pwd", True)

    assert service.delete_profile(profile.id) is True
    assert service.list_profiles() == []
    assert service.delete_profile(profile.id) is False


def test_multi_prereq_unlock_after_both_completed() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-multi-dep")
    store = service.progress
    store.mark_module_completed(profile.id, "docker")
    states = {state.module.id: state for state in service.list_module_states(profile.id)}
    assert states["docker-context"].unlocked is False
    store.mark_module_completed(profile.id, "ssh")
    states = {state.module.id: state for state in service.list_module_states(profile.id)}
    assert states["docker-context"].unlocked is True


def test_started_module_stays_unlocked_if_prereqs_not_met() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-grandfather")
    service.progress.mark_module_started(profile.id, "apt")
    states = {state.module.id: state for state in service.list_module_states(profile.id)}
    assert states["apt"].started is True
    assert states["apt"].unlocked is True


def test_completed_module_outdated_when_content_version_increases() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-outdated")
    service.progress.mark_module_completed(profile.id, "base-linux", 1)
    module = service.modules["base-linux"]
    service.modules["base-linux"] = module.__class__(
        id=module.id,
        title=module.title,
        description=module.description,
        content_version=2,
        prerequisites=module.prerequisites,
        lessons=module.lessons,
    )
    states = {state.module.id: state for state in service.list_module_states(profile.id)}
    assert states["base-linux"].completed is True
    assert states["base-linux"].outdated is True


def test_force_unlock_module_with_dependencies() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-force")
    unlocked = service.force_unlock_module_with_dependencies(profile.id, "docker-context")
    assert unlocked[-1] == "docker-context"
    assert "docker" in unlocked
    assert "ssh" in unlocked
    states = {state.module.id: state for state in service.list_module_states(profile.id)}
    assert states["docker"].completed is True
    assert states["ssh"].completed is True
    assert states["docker-context"].completed is True


def test_get_module_missing() -> None:
    service = LearnService(":memory:")
    assert service.get_module("missing") is None


def test_correct_card_ids_for_module() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("correct-ids")
    module = service.begin_module(profile.id, "base-linux")
    first = module.lessons[0].cards[0]
    service.record_answer(profile.id, first, first.answers[0])
    assert first.id in service.correct_card_ids_for_module(profile.id, "base-linux")


def test_force_unlock_missing_module_raises_key_error() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("force-missing")
    try:
        service.force_unlock_module_with_dependencies(profile.id, "missing")
        raise AssertionError("Expected KeyError.")
    except KeyError:
        pass


def test_card_validation_token_matching() -> None:
    service = LearnService(":memory:")
    card = Card(
        id="c1",
        module_id="m",
        lesson_id="l",
        prompt="p",
        answers=["ls -la"],
        explanation="e",
        command="ls",
        tested_flags=["-l", "-a"],
    )

    assert service.card_is_correct(card, "ls -al") is True
    assert service.card_is_correct(card, "ls -la") is True
    assert service.card_is_correct(card, "ls") is False
    assert service.card_is_correct(card, '"') is False


def test_card_validation_allows_option_reordering() -> None:
    service = LearnService(":memory:")
    card = Card(
        id="c2",
        module_id="m",
        lesson_id="l",
        prompt="p",
        answers=["grep -n --color=auto pattern file.txt"],
        explanation="e",
        command="grep",
        tested_flags=["-n", "--color"],
    )

    assert service.card_is_correct(card, "grep --color=auto -n pattern file.txt") is True
    assert service.card_is_correct(card, "grep file.txt pattern --color=auto -n") is False


def test_module_completion_after_all_cards_correct() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p2")

    module = service.begin_module(profile.id, "base-linux")
    for lesson in module.lessons:
        for card in lesson.cards:
            assert service.record_answer(profile.id, card, card.answers[0]) is True

    assert service.complete_module_if_mastered(profile.id, module) is True


def test_module_completion_false_when_missing_cards() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p2b")
    module = service.begin_module(profile.id, "base-linux")
    assert service.complete_module_if_mastered(profile.id, module) is False


def test_due_cards_from_completed_then_started_fallback() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p3")

    module = service.begin_module(profile.id, "base-linux")
    first_card = module.lessons[0].cards[0]
    service.record_answer(profile.id, first_card, first_card.answers[0])

    due = service.due_cards(profile.id, limit=5)
    assert len(due) > 0

    for lesson in module.lessons:
        for card in lesson.cards:
            service.record_answer(profile.id, card, card.answers[0])
    service.complete_module_if_mastered(profile.id, module)

    store = service.progress
    overdue = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with store._conn:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "UPDATE card_progress SET due_at = ? WHERE profile_id = ? AND card_id = ?",
            (overdue, profile.id, first_card.id),
        )

    due = service.due_cards(profile.id, limit=5)
    assert any(card.id == first_card.id for card in due)


def test_due_cards_empty_without_started_modules() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p4")
    assert service.due_cards(profile.id, limit=5) == []


def test_due_cards_future_fallback_when_none_due() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p5")
    module = service.begin_module(profile.id, "base-linux")
    for lesson in module.lessons:
        for card in lesson.cards:
            service.record_answer(profile.id, card, card.answers[0])
    service.complete_module_if_mastered(profile.id, module)

    cards = service.due_cards(profile.id, limit=2)
    assert len(cards) == 2


def test_due_cards_avoids_immediate_repeat_when_multiple_due(monkeypatch: Any) -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p6")
    module = service.begin_module(profile.id, "base-linux")
    first_id = module.lessons[0].cards[0].id
    second_card = module.lessons[0].cards[1]
    first_card = module.lessons[0].cards[0]
    service.record_answer(profile.id, first_card, first_card.answers[0])
    service.record_answer(profile.id, second_card, second_card.answers[0])
    service._last_presented_card_id[profile.id] = first_id  # noqa: SLF001

    monkeypatch.setattr("cmdtrainer.service.random.shuffle", lambda cards: None)
    cards = service.due_cards(profile.id, limit=1)
    assert len(cards) == 1
    assert cards[0].id != first_id


def test_list_module_command_references() -> None:
    service = LearnService(":memory:")
    references = service.list_module_command_references("git")
    commands = {item.command for item in references}
    assert "git status" in commands
    assert "git add" in commands
    add_ref = next(item for item in references if item.command == "git add")
    assert "-p" in add_ref.tested_flags


def test_list_module_lesson_references() -> None:
    service = LearnService(":memory:")
    lessons = service.list_module_lesson_references("base-linux")
    assert len(lessons) > 0
    assert lessons[0].order == 1
    assert lessons[0].card_count > 0
    assert lessons[0].command_count > 0


def test_get_module_progression_counts_attempted_and_correct() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-progress")
    module = service.begin_module(profile.id, "base-linux")
    first = module.lessons[0].cards[0]
    second = module.lessons[0].cards[1]

    service.record_answer(profile.id, first, first.answers[0])
    service.record_answer(profile.id, second, "wrong")

    progression = service.get_module_progression(profile.id, "base-linux")
    assert progression.stage == "started"
    assert progression.total_cards > 1
    assert progression.attempted_cards >= 2
    assert progression.correct_cards >= 1
    assert any(item.attempted_cards > 0 for item in progression.lessons)


def test_get_module_progression_stage_outdated() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-outdated-progress")
    service.progress.mark_module_started(profile.id, "base-linux")
    service.progress.mark_module_completed(profile.id, "base-linux", 1)

    module = service.modules["base-linux"]
    service.modules["base-linux"] = module.__class__(
        id=module.id,
        title=module.title,
        description=module.description,
        content_version=module.content_version + 1,
        prerequisites=module.prerequisites,
        lessons=module.lessons,
    )
    progression = service.get_module_progression(profile.id, "base-linux")
    assert progression.stage == "outdated"


def test_practice_queue_empty_without_eligible_modules() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("queue-empty")
    assert service.practice_queue(profile.id) == []


def test_practice_queue_contains_new_due_and_scheduled() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("queue-mix")
    module = service.begin_module(profile.id, "base-linux")
    first = module.lessons[0].cards[0]
    service.record_answer(profile.id, first, first.answers[0])

    items = service.practice_queue(profile.id, limit=500)
    by_id = {item.card_id: item for item in items}
    assert by_id[first.id].status in {"due", "scheduled"}
    assert len(items) == 1


def test_practice_queue_new_status_from_attempts_without_schedule() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("queue-new-status")
    module = service.begin_module(profile.id, "base-linux")
    card = module.lessons[0].cards[0]
    now = datetime.now(UTC).isoformat()
    with service.progress._conn:  # noqa: SLF001
        service.progress._conn.execute(  # noqa: SLF001
            "INSERT INTO attempts (profile_id, card_id, user_input, is_correct, created_at) VALUES (?, ?, ?, ?, ?)",
            (profile.id, card.id, card.answers[0], 1, now),
        )
    items = service.practice_queue(profile.id, limit=50)
    assert any(item.card_id == card.id and item.status == "new" for item in items)


def test_export_import_profile_round_trip(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    source = service.create_profile("export-source")
    module = service.begin_module(source.id, "base-linux")
    card = module.lessons[0].cards[0]
    service.record_answer(source.id, card, card.answers[0])
    service.progress.mark_module_completed(source.id, "base-linux", module.content_version)

    export_path = tmp_path / "profile-export.json"
    export_summary = service.export_profile(source.id, export_path)
    assert export_summary.profile_name == "export-source"
    assert export_summary.module_rows >= 1
    assert export_summary.card_rows >= 1
    assert export_summary.attempt_rows >= 1

    import_summary = service.import_profile(export_path, "imported-copy")
    assert import_summary.profile_name == "imported-copy"
    imported_id = import_summary.profile_id
    assert service.progress.module_state(imported_id, "base-linux")[1] is True
    assert service.progress.get_card_schedule(imported_id, card.id) is not None


def test_import_profile_rejects_newer_format_version(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    payload = {
        "format_version": 999,
        "profile": {"name": "future-profile"},
        "module_progress": [],
        "card_progress": [],
        "attempts": [],
    }
    path = tmp_path / "future.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        service.import_profile(path)
        raise AssertionError("Expected ValueError for newer format version.")
    except ValueError as exc:
        assert "newer than supported" in str(exc)


def test_import_profile_legacy_payload_without_version(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    payload = {
        "profile": {"name": "legacy-profile"},
        "module_progress": [{"module_id": "base-linux"}],
        "card_progress": [{"card_id": "base-linux-pwd"}],
        "attempts": [{"card_id": "base-linux-pwd", "user_input": "pwd", "is_correct": 1}],
    }
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    summary = service.import_profile(path)
    assert summary.profile_name == "legacy-profile"
    assert summary.module_rows == 1
    assert summary.card_rows == 1
    assert summary.attempt_rows == 1


def test_export_profile_missing_raises_key_error(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    path = tmp_path / "missing.json"
    try:
        service.export_profile(999, path)
        raise AssertionError("Expected KeyError for missing profile.")
    except KeyError:
        pass


def test_import_profile_invalid_root_object(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    path = tmp_path / "bad-root.json"
    path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
    try:
        service.import_profile(path)
        raise AssertionError("Expected ValueError for non-object root.")
    except ValueError as exc:
        assert "JSON object" in str(exc)


def test_import_profile_invalid_format_version_type(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    path = tmp_path / "bad-version.json"
    path.write_text(json.dumps({"format_version": {"x": 1}, "profile": {"name": "n"}}), encoding="utf-8")
    try:
        service.import_profile(path)
        raise AssertionError("Expected ValueError for invalid format_version.")
    except ValueError as exc:
        assert "invalid format_version" in str(exc)


def test_import_profile_missing_name_raises(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    path = tmp_path / "no-name.json"
    path.write_text(json.dumps({"format_version": 1, "profile": {}, "module_progress": []}), encoding="utf-8")
    try:
        service.import_profile(path)
        raise AssertionError("Expected ValueError for missing profile name.")
    except ValueError as exc:
        assert "determine profile name" in str(exc)


def test_import_profile_ignores_malformed_rows(tmp_path: Path) -> None:
    service = LearnService(":memory:")
    payload = {
        "format_version": 1,
        "profile": {"name": "malformed"},
        "module_progress": [{"module_id": ""}, {"not_module": True}],
        "card_progress": [{"card_id": ""}, {"streak": "x"}],
        "attempts": [{"card_id": ""}, {"is_correct": 1}],
    }
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    summary = service.import_profile(path)
    assert summary.profile_name == "malformed"
    assert summary.module_rows == 0
    assert summary.card_rows == 0
    assert summary.attempt_rows == 0


def test_numeric_coercion_helpers() -> None:
    assert _coerce_int("3") == 3
    assert _coerce_int("bad", default=7) == 7
    assert _coerce_int(object(), default=None) is None
    assert _coerce_float("2.5") == 2.5
    assert _coerce_float("bad", default=1.25) == 1.25
    assert _coerce_float(object(), default=None) is None


def test_import_profile_fixture_from_v1_0_0() -> None:
    service = LearnService(":memory:")
    fixture_path = Path(__file__).parent / "fixtures" / "profile_export_v1_0_0.json"

    summary = service.import_profile(fixture_path, "fixture-imported")
    assert summary.profile_name == "fixture-imported"
    assert summary.module_rows == 2
    assert summary.card_rows == 2
    assert summary.attempt_rows == 3

    imported_id = summary.profile_id
    base_started, base_completed, base_version = service.progress.module_state(imported_id, "base-linux")
    git_started, git_completed, _ = service.progress.module_state(imported_id, "git")
    assert base_started is True
    assert base_completed is True
    assert base_version == 1
    assert git_started is True
    assert git_completed is False

    pwd_schedule = service.progress.get_card_schedule(imported_id, "base-linux-pwd")
    ls_schedule = service.progress.get_card_schedule(imported_id, "base-linux-ls-long-all")
    assert pwd_schedule is not None
    assert pwd_schedule.streak == 2
    assert pwd_schedule.seen_count == 3
    assert ls_schedule is not None
    assert ls_schedule.streak == 0
    assert ls_schedule.seen_count == 1
