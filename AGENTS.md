# AGENTS.md

## Purpose

This repository builds a command-line learning and practice tool for software developers.
The tool should teach commands, assess understanding, and provide hands-on drills without executing learner commands.
The product form is a CLI tool.

## Working Principles

- Start simple and ship an MVP first.
- Keep learning paths modular (module -> lesson -> card).
- Use explicit prerequisites and unlock rules.
- Separate content from engine logic.
- Use command-string validation only; learner commands are not executed.
- Keep card metadata explicit (`command`, `tested_flags`) for module reference and reporting features.
- Maintain command ownership for overlapping commands:
  - Every overlapping command must declare one home module.
  - Cross-module overlap is allowed only when it adds depth (new tested flags) or is explicitly allowlisted as contextual overlap.
  - If a module uses a command whose home is another module, the home module must be a direct prerequisite.
- Treat profile-based progress tracking and spaced repetition as core product requirements.
- Include and maintain automated tests as part of all implementation work.
- Target at least 95% automated test coverage.

## Collaboration Rules

- Record architecture and milestone decisions in `Plans.md`.
- Spaced repetition algorithm reference is documented in `docs/spaced-repetition.md` and should be kept in sync with `src/cmdtrainer/progress.py`.
- Keep `README.md` (user-facing) and `README.dev.md` (developer-facing) up to date when behavior, menus, modules, setup, or quality gates change.
- Keep `CHANGELOG.md` up to date for user-visible behavior changes, features, fixes, and breaking changes.
- Keep user-facing copy concise and practical.
- Add tests for progression rules and exercise validation logic.
- Keep overlap/dependency policy tests up to date in `tests/test_module_content_baseline.py`:
  - `test_overlapping_commands_follow_ownership_and_depth_rules`
  - `test_cross_module_command_requires_home_module_prerequisite`
- Treat database schema changes as migration work:
  - update `SCHEMA_VERSION` and add a forward-only migration in `src/cmdtrainer/progress.py`,
  - add/maintain migration tests for fresh DB creation and upgrades from older schema versions,
  - keep startup auto-migration behavior working for existing user databases.
- For significant DB or export-format updates, add a new versioned profile export fixture and a pytest compatibility case that verifies old exported profiles still import correctly.
- Keep the learning engine execution-free: validate command text, never run learner commands.
- Require tests for new features and critical bug fixes before considering work complete.
- When relevant to user-facing behavior, manually run the CLI (`cmdtrainer`) to verify end-to-end flows in addition to automated pytest coverage.
- `AGENTS.md` is locked after this baseline; do not change it without explicit user approval.
- Run quality checks before finalizing changes:
  - `.\.venv\Scripts\black --check src tests`
  - `.\.venv\Scripts\ruff check src tests`
  - `.\.venv\Scripts\pyright`
  - `.\.venv\Scripts\python -m pytest`
  - Type checks include both `src` and `tests` using repository pyright settings.

## Success Criteria

- Users choose or create a profile at startup and progress is saved by profile.
- Users can complete modules in sequence with visible progress.
- Users can run guided first-time learning and receive immediate feedback.
- Users can run randomized spaced-repetition practice across eligible modules.
- Users can list commands covered by a module.
- Users can list tested flags for each command in a module.
- Cross-module capstones unlock from multiple prerequisite modules.
- Content can be extended without changing core code.
- Command validation is based on command syntax/content, not runtime effects.
- Test suite covers dependency/unlock logic, profile state, and spaced-repetition scheduling.
- Repository-level automated test coverage is maintained at >=95%.

