from itertools import permutations

from cmdtrainer.models import Card
from cmdtrainer.service import LearnService, _normalize_command


def _card(answer: str) -> Card:
    return Card(
        id="c",
        module_id="m",
        lesson_id="l",
        prompt="p",
        answers=[answer],
        explanation="e",
        command="cmd",
        tested_flags=[],
    )


def test_normalize_empty_or_invalid_input() -> None:
    assert _normalize_command("   ") is None
    assert _normalize_command('"') is None


def test_short_flag_permutations_are_equivalent() -> None:
    service = LearnService(":memory:")
    answer = "ls -la /tmp"
    card = _card(answer)
    for order in permutations(["l", "a"]):
        user = f"ls -{''.join(order)} /tmp"
        assert service.card_is_correct(card, user) is True


def test_long_option_with_value_forms() -> None:
    service = LearnService(":memory:")
    card = _card("grep --color=auto -n TODO file.txt")
    assert service.card_is_correct(card, "grep -n --color=auto TODO file.txt") is True
    assert service.card_is_correct(card, "grep --color auto -n TODO file.txt") is True


def test_force_positionals_and_attached_short_value() -> None:
    left = _normalize_command("cmd -p22 -- -n")
    right = _normalize_command("cmd -p22 -- -n")
    assert left is not None
    assert right is not None
    assert left == right
    assert _normalize_command("cmd -- -n") is not None


def test_due_cards_skips_unknown_module_ids() -> None:
    service = LearnService(":memory:")
    profile = service.create_profile("p-x")
    service.progress.mark_module_started(profile.id, "unknown-module")
    assert service.due_cards(profile.id, limit=3) == []


def test_service_list_profiles_and_close() -> None:
    service = LearnService(":memory:")
    service.create_profile("p-list")
    profiles = service.list_profiles()
    assert len(profiles) == 1
    service.close()
