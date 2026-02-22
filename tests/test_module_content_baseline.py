from cmdtrainer.content_loader import load_modules

HOME_MODULE_BY_COMMAND: dict[str, str] = {
    "cat": "base-linux",
    "docker image": "docker",
    "docker network": "docker",
    "docker run": "docker",
    "docker volume": "docker",
    "grep": "base-linux",
    "wc": "base-linux",
}

CONTEXTUAL_OVERLAP_ALLOWLIST: set[tuple[str, str]] = {
    ("cat", "file-tools"),
    ("docker image", "docker-image"),
    ("docker network", "docker-network"),
    ("docker volume", "docker-volume"),
}


def test_module_required_command_baseline() -> None:
    modules = load_modules()
    required: dict[str, set[str]] = {
        "base-linux": {
            "pwd",
            "ls",
            "cd",
            "mkdir",
            "cp",
            "mv",
            "rm",
            "cat",
            "grep",
            "tail",
            "chmod",
            "ps",
            "kill",
            "df",
            "tar",
            "ln",
        },
        "apt": {
            "apt update",
            "apt upgrade",
            "apt install",
            "apt remove",
            "apt purge",
            "apt search",
            "apt show",
            "apt autoremove",
            "apt list",
            "apt policy",
            "apt-mark hold",
        },
        "archive-tools": {
            "gzip",
            "gunzip",
            "xz",
            "zip",
            "unzip",
        },
        "http-clients": {
            "curl",
            "wget",
        },
        "git": {
            "git status",
            "git add",
            "git commit",
            "git diff",
            "git log",
            "git show",
            "git branch",
            "git switch",
            "git pull",
            "git push",
            "git fetch",
            "git remote",
            "git rebase",
            "git merge",
            "git stash",
            "git reset",
            "git revert",
            "git cherry-pick",
            "git reflog",
            "git clean",
            "git tag",
        },
        "ssh": {
            "ssh",
            "scp",
            "ssh-keygen",
            "ssh-add",
            "ssh-copy-id",
            "ssh-agent",
        },
        "docker": {
            "docker version",
            "docker ps",
            "docker images",
            "docker pull",
            "docker run",
            "docker start",
            "docker stop",
            "docker restart",
            "docker rm",
            "docker logs",
            "docker exec",
            "docker inspect",
            "docker build",
            "docker tag",
            "docker push",
            "docker login",
            "docker logout",
            "docker network",
            "docker volume",
            "docker container",
        },
        "docker-compose": {
            "docker compose up",
            "docker compose down",
            "docker compose stop",
            "docker compose restart",
            "docker compose ps",
            "docker compose logs",
            "docker compose exec",
            "docker compose run",
            "docker compose config",
            "docker compose pull",
            "docker compose build",
            "docker compose images",
        },
        "docker-network": {
            "docker network",
            "docker network inspect",
            "docker network create",
            "docker network connect",
            "docker network disconnect",
            "docker network rm",
            "docker network prune",
        },
        "docker-image": {
            "docker image",
            "docker image history",
            "docker image tag",
            "docker image pull",
            "docker image push",
            "docker image rm",
        },
        "docker-volume": {
            "docker volume",
            "docker volume inspect",
            "docker volume create",
            "docker volume rm",
            "docker volume prune",
            "docker run",
        },
        "docker-context": {
            "docker context",
            "docker context show",
            "docker context inspect",
            "docker context create",
            "docker context use",
            "docker context export",
            "docker context import",
            "docker context rm",
        },
        "file-tools": {
            "find",
            "grep",
            "sort",
            "uniq",
            "cut",
            "wc",
            "xargs",
            "sed",
            "awk",
            "jq",
        },
        "network-basics": {
            "ip addr",
            "ip route",
            "ss",
            "ping",
            "traceroute",
            "dig",
            "nslookup",
            "host",
        },
        "process-tools": {
            "pgrep",
            "pkill",
            "pstree",
            "nohup",
            "nice",
            "renice",
            "watch",
            "time",
            "/usr/bin/time",
        },
        "tmux": {
            "tmux new",
            "tmux ls",
            "tmux attach",
            "tmux new-window",
            "tmux rename-window",
            "tmux kill-session",
            "tmux split-window",
            "tmux select-window",
            "tmux send-keys",
            "tmux set-option",
            "tmux list-keys",
        },
    }

    for module_id, expected_commands in required.items():
        module = modules[module_id]
        actual_commands = {card.command for lesson in module.lessons for card in lesson.cards}
        missing = expected_commands - actual_commands
        assert not missing, f"{module_id} missing commands: {sorted(missing)}"


def test_module_required_flag_baseline() -> None:
    modules = load_modules()
    required_flags: dict[str, dict[str, set[str]]] = {
        "base-linux": {
            "ls": {"-l", "-a", "-h"},
            "rm": {"-r", "-f"},
            "tar": {"-c", "-x", "-z", "-f"},
            "grep": {"-R", "-n", "-i"},
        },
        "apt": {
            "apt install": {"-y", "--reinstall", "--no-install-recommends"},
            "apt list": {"--installed", "--upgradable"},
        },
        "archive-tools": {
            "gzip": {"-k"},
            "xz": {"-d", "-k", "-T"},
            "zip": {"-r", "-e", "-x"},
            "unzip": {"-d", "-l", "-o"},
        },
        "http-clients": {
            "curl": {"-I", "-L", "-o", "-X", "-H", "-d", "--retry", "--retry-delay"},
            "wget": {"-O", "-c", "--limit-rate"},
        },
        "git": {
            "git status": {"-s"},
            "git add": {"-p"},
            "git commit": {"-m", "--amend"},
            "git rebase": {"-i", "--continue", "--abort"},
            "git clean": {"-f", "-d"},
            "git push": {"-u", "--tags"},
        },
        "ssh": {
            "ssh": {"-p", "-i", "-v", "-J", "-L"},
            "scp": {"-r", "-P"},
            "ssh-keygen": {"-t", "-C"},
            "ssh-copy-id": {"-i"},
        },
        "docker": {
            "docker run": {"-d", "-p", "-i", "-t", "--rm", "-e"},
            "docker logs": {"-f", "--tail"},
            "docker build": {"-t", "-f"},
            "docker image": {"-a", "-f"},
        },
        "docker-compose": {
            "docker compose up": {"-d", "--build"},
            "docker compose down": {"-v", "--remove-orphans"},
            "docker compose logs": {"-f", "--tail"},
            "docker compose run": {"--rm"},
        },
        "docker-network": {
            "docker network create": {"--driver"},
            "docker network prune": {"-f"},
        },
        "docker-image": {
            "docker image": {"-a", "-f"},
            "docker image pull": {"--platform"},
            "docker image rm": {"-f"},
        },
        "docker-volume": {
            "docker run": {"-v"},
            "docker volume prune": {"-f"},
        },
        "docker-context": {
            "docker context create": {"--docker"},
        },
        "file-tools": {
            "grep": {"-R", "-i", "-n", "-w", "-v"},
            "find": {"-type", "-name", "-size"},
            "jq": {"-c", "-r"},
            "sort": {"-u", "-n", "-r"},
        },
        "network-basics": {
            "ip addr": {"-br"},
            "ss": {"-a", "-l", "-n", "-p", "-t", "-u"},
            "ping": {"-c", "-i"},
            "host": {"-t"},
        },
        "process-tools": {
            "pgrep": {"-a", "-f", "-u"},
            "pkill": {"-f", "-15", "-9"},
            "pstree": {"-p"},
            "nice": {"-n"},
            "renice": {"-n", "-p"},
            "watch": {"-n"},
            "/usr/bin/time": {"-v"},
        },
        "tmux": {
            "tmux new": {"-s"},
            "tmux attach": {"-t"},
            "tmux new-window": {"-n"},
            "tmux kill-session": {"-t"},
            "tmux split-window": {"-h", "-v"},
            "tmux select-window": {"-t"},
            "tmux send-keys": {"-t"},
            "tmux set-option": {"-g"},
        },
    }

    for module_id, command_map in required_flags.items():
        module = modules[module_id]
        flags_by_command: dict[str, set[str]] = {}
        for lesson in module.lessons:
            for card in lesson.cards:
                flags = flags_by_command.setdefault(card.command, set())
                flags.update(card.tested_flags)

        for command, expected_flags in command_map.items():
            actual_flags = flags_by_command.get(command, set())
            missing_flags = expected_flags - actual_flags
            assert not missing_flags, f"{module_id} {command} missing flags: {sorted(missing_flags)}"


def test_overlapping_commands_follow_ownership_and_depth_rules() -> None:
    """Enforce overlap policy: one home module per command + non-home adds depth.

    Depth is currently represented by introducing at least one new tested flag
    beyond the command's home module. For deliberate context-only overlap,
    command/module pairs must be explicitly allowlisted.
    """
    modules = load_modules()
    flags_by_command_by_module: dict[str, dict[str, set[str]]] = {}
    for module_id, module in modules.items():
        for lesson in module.lessons:
            for card in lesson.cards:
                flags_by_module = flags_by_command_by_module.setdefault(card.command, {})
                flags = flags_by_module.setdefault(module_id, set())
                flags.update(card.tested_flags)

    overlaps = {
        command: module_map for command, module_map in flags_by_command_by_module.items() if len(module_map) > 1
    }
    for command, module_map in overlaps.items():
        home_module = HOME_MODULE_BY_COMMAND.get(command)
        assert home_module is not None, f"Overlapping command '{command}' must define a home module."
        assert home_module in module_map, f"Home module '{home_module}' missing for command '{command}'."
        home_flags = module_map[home_module]
        for module_id, module_flags in module_map.items():
            if module_id == home_module:
                continue
            introduces_new_flags = bool(module_flags - home_flags)
            is_contextual_overlap = (command, module_id) in CONTEXTUAL_OVERLAP_ALLOWLIST
            assert (
                introduces_new_flags or is_contextual_overlap
            ), f"Overlap '{command}' in '{module_id}' must add flags or be explicitly allowlisted."


def test_cross_module_command_requires_home_module_prerequisite() -> None:
    """Require direct prerequisite on a command's home module for cross-module cards."""
    modules = load_modules()
    for module_id, module in modules.items():
        for lesson in module.lessons:
            for card in lesson.cards:
                home_module = HOME_MODULE_BY_COMMAND.get(card.command)
                if home_module is None or home_module == module_id:
                    continue
                assert (
                    home_module in module.prerequisites
                ), f"Module '{module_id}' uses '{card.command}' but does not depend on home module '{home_module}'."
