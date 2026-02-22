from datetime import UTC, datetime, timedelta
from typing import Any

from cmdtrainer.models import Card
from cmdtrainer.service import LearnService


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

    # no completed modules yet -> fallback to started modules
    due = service.due_cards(profile.id, limit=5)
    assert len(due) > 0

    # complete module and force one card overdue
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
    second = module.lessons[0].cards[1]
    service.record_answer(profile.id, first, first.answers[0])

    items = service.practice_queue(profile.id, limit=500)
    by_id = {item.card_id: item for item in items}
    assert by_id[first.id].status in {"due", "scheduled"}
    assert by_id[second.id].status == "new"
