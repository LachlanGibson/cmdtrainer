from itertools import permutations

from cmdtrainer.models import Card
from cmdtrainer.service import LearnService, _normalize_command, _normalize_template_whitespace


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


def test_normalize_equivalent_command_pairs() -> None:
    cases = [
        ("ls -la /tmp", "ls -al /tmp"),
        ("grep --color=auto -n TODO file.txt", "grep -n --color auto TODO file.txt"),
        ("echo 'a b'", 'echo "a b"'),
        ("cmd -- -n", "cmd -- -n"),
        ("npm run -s test -- --watch", "npm run test -s -- --watch"),
        ("npm run build -w packages/web", "npm run build --workspace packages/web"),
    ]
    for left_command, right_command in cases:
        left = _normalize_command(left_command)
        right = _normalize_command(right_command)
        assert left is not None
        assert right is not None
        assert left == right


def test_normalize_non_equivalent_command_pairs() -> None:
    cases = [
        ("ssh -p2222 ubuntu@example.com", "ssh -p 2222 ubuntu@example.com"),
        ("grep -n --color=auto pattern file.txt", "grep file.txt pattern --color=auto -n"),
        ("ssh -p2222 ubuntu@example.com", "ssh -p 2200 ubuntu@example.com"),
        ("pstree -p 1", "pstree -p 2"),
        ("cmd -- -n", "cmd -n"),
        ("cmd -v -v target", "cmd -v target"),
        ('echo "a b"', "echo a b"),
        ("ls -la /tmp", "cat -la /tmp"),
        ("npm run test -- --watch", "npm run test --watch"),
        ("npm run test --workspaces", "npm run test -ws"),
    ]
    for left_command, right_command in cases:
        left = _normalize_command(left_command)
        right = _normalize_command(right_command)
        assert left is not None
        assert right is not None
        assert left != right


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


def test_card_validation_cases() -> None:
    cases = [
        ("ls -la /tmp", "ls -al /tmp", True),
        ("grep --color=auto -n TODO file.txt", "grep -n --color auto TODO file.txt", True),
        ("grep -n --color=auto pattern file.txt", "grep file.txt pattern --color=auto -n", False),
        ("ssh -p2222 ubuntu@example.com", "ssh -p 2222 ubuntu@example.com", True),
        ("ssh -p2222 ubuntu@example.com", "ssh -p 2200 ubuntu@example.com", False),
        ("pstree -p 1", "pstree 1 -p", True),
        ("pstree -p 1", "pstree -p 2", False),
        ("cmd -- -n", "cmd -n", False),
        ('echo "a b"', "echo a b", False),
        ("npm run test -- --watch", "npm run test -- --watch", True),
        ("npm run test -- --watch", "npm run test --watch", False),
        ("npm run test --workspaces", "npm run test -ws", False),
        ("npm run build -w packages/web", "npm run build --workspace packages/web", True),
    ]
    service = LearnService(":memory:")
    for answer, user_input, expected_correct in cases:
        card = _card(answer)
        assert service.card_is_correct(card, user_input) is expected_correct


def test_normalize_template_whitespace_collapses_only_inside_braces() -> None:
    # Whitespace around the pipeline inside {{ }} is insignificant to Go templates.
    assert _normalize_template_whitespace("{{ .X }}") == "{{.X}}"
    assert _normalize_template_whitespace("{{.X}}") == "{{.X}}"
    assert _normalize_template_whitespace("{{   .X   }}") == "{{.X}}"
    assert _normalize_template_whitespace("{{ .A | html }}") == "{{.A | html}}"
    # Whitespace-trim markers keep their single separating space.
    assert _normalize_template_whitespace("{{-  .X  -}}") == "{{- .X -}}"
    # `{{-.X-}}` is arithmetic minus, not a trim marker, and must stay distinct.
    assert _normalize_template_whitespace("{{-.X-}}") == "{{-.X-}}"
    assert _normalize_template_whitespace("{{-.X-}}") != _normalize_template_whitespace("{{- .X -}}")
    # Text outside the delimiters is left untouched.
    assert _normalize_template_whitespace("--format={{ .X }}") == "--format={{.X}}"
    assert _normalize_template_whitespace("a  b") == "a  b"


def test_docker_inspect_format_whitespace_and_alias_are_equivalent() -> None:
    service = LearnService(":memory:")
    card = _card('docker inspect -f "{{ .NetworkSettings.IPAddress }}" api')
    equivalent = [
        'docker inspect -f "{{ .NetworkSettings.IPAddress }}" api',
        'docker inspect -f "{{.NetworkSettings.IPAddress}}" api',
        'docker inspect -f "{{   .NetworkSettings.IPAddress   }}" api',
        'docker inspect --format "{{ .NetworkSettings.IPAddress }}" api',
        'docker inspect --format "{{.NetworkSettings.IPAddress}}" api',
        'docker inspect --format="{{.NetworkSettings.IPAddress}}" api',
        "docker inspect -f '{{.NetworkSettings.IPAddress}}' api",
    ]
    for user_input in equivalent:
        assert service.card_is_correct(card, user_input) is True, user_input


def test_docker_inspect_format_rejects_wrong_answers() -> None:
    service = LearnService(":memory:")
    card = _card('docker inspect -f "{{ .NetworkSettings.IPAddress }}" api')
    wrong = [
        'docker inspect -f "{{ .NetworkSettings.MacAddress }}" api',  # wrong field
        'docker inspect -f "{{ .NetworkSettings.IPAddress }}" web',  # wrong target
        'docker inspect "{{ .NetworkSettings.IPAddress }}" api',  # missing -f/--format
    ]
    for user_input in wrong:
        assert service.card_is_correct(card, user_input) is False, user_input


def test_format_alias_is_scoped_to_docker_inspect() -> None:
    service = LearnService(":memory:")
    # docker inspect: -f and --format are aliases for the Go-template format.
    inspect_card = _card('docker inspect -f "{{.X}}" api')
    assert service.card_is_correct(inspect_card, 'docker inspect --format "{{.X}}" api') is True
    # docker images/ps: short -f is --filter, NOT --format -> must stay distinct.
    images_card = _card('docker images -f "{{.X}}"')
    assert service.card_is_correct(images_card, 'docker images --format "{{.X}}"') is False
    ps_card = _card("docker ps -f status=running")
    assert service.card_is_correct(ps_card, "docker ps --format status=running") is False


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
