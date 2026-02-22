# Plans.md

## Vision
Build a profile-based command-learning CLI with guided first-time module learning and spaced-repetition review.

## Product Shape (High Level)
1. Persistent CLI app session.
2. Startup profile selection/create flow.
3. Two learning paths:
   - First-time module learning (answer shown + typing practice).
   - General randomized review using spaced repetition.

## Core Concepts
- Profile: User-specific progress and scheduling state.
- Module: Topic area (e.g., base linux).
- Lesson: Ordered section of related cards.
- Card: Prompt + accepted command answers.
- Validation: Command-string comparison only (no command execution).
- Schedule: Next due time for card review.

## Module Roadmap
### Core (current)
1. Base Linux / Core shell commands
2. `apt`
3. `git`
4. `ssh`
5. `docker`
6. `docker compose`
7. `docker network`
8. `docker image`
9. `docker volume`
10. `docker context`
11. `file-tools`

### Added now
1. `network-basics`
2. `http-clients`
3. `tmux`
4. `process-tools`
5. `archive-tools`

## Dependency Graph
- base-linux -> apt
- base-linux -> git
- base-linux -> ssh
- base-linux -> docker
- docker -> docker compose
- docker + ssh -> docker context
- base-linux -> file-tools
- base-linux -> docker network
- base-linux -> docker image
- base-linux -> docker volume
- base-linux -> network-basics
- network-basics -> http-clients
- base-linux -> tmux
- base-linux -> process-tools
- base-linux -> archive-tools

## Learning and Practice Model
### First-time module learning
1. Show card prompt and expected answer.
2. Learner types command.
3. Validate by accepted command forms.
4. Require correctness before moving to next card.
5. Mark module complete after all cards answered correctly for first completion.

### General practice
1. Draw due cards from completed modules.
2. If no completed modules, fallback to started modules.
3. Randomize card order among due cards.
4. Update spaced-repetition schedule based on correct/incorrect.

## Validation Rules
- Parse command using shell tokenization.
- Compare normalized commands:
  - command token must match,
  - options/flags are order-insensitive,
  - positional argument order is preserved.
- Support multiple accepted forms per card when syntax variants are meaningfully different.
- Do not execute learner commands.

## Spaced Repetition Strategy (MVP)
- Per profile+card state:
  - streak
  - spacing_score
  - interval_minutes
  - due_at
  - last_seen_at
  - last_result
- Correct:
  - increase `spacing_score` using score + streak growth,
  - derive interval by bounded exponential function of `spacing_score`,
  - schedule next due at `now + interval_minutes`.
- Incorrect:
  - streak resets to 0,
  - shrink `spacing_score`,
  - schedule due very soon (fixed 2 minutes), regardless of score.

## Data Model (SQLite)
- profiles(id, name, created_at)
- module_progress(profile_id, module_id, started_at, completed_at)
- card_progress(profile_id, card_id, streak, spacing_score, interval_minutes, due_at, last_seen_at, last_result, seen_count)
- attempts(id, profile_id, card_id, user_input, is_correct, created_at)

## MVP Scope
1. CLI session shell with profile selection.
2. Base Linux module implemented fully as cards.
3. Module prerequisites/unlock checks.
4. Guided first-time learning path.
5. General spaced-repetition review path.
6. Persistent profile progress in SQLite.
7. Command-string validation only.
8. Automated tests and >=95% coverage.

## Risks and Mitigations
- Risk: Overly strict validation causes frustration.
  - Mitigation: multiple accepted answers per card.
- Risk: Scheduling feels unfair.
  - Mitigation: simple transparent intervals in MVP.
- Risk: Content maintenance burden.
  - Mitigation: declarative JSON card files.

## Next Build Steps
1. Refactor content schema to card-based command answers.
2. Implement profile and scheduling persistence.
3. Implement command normalization and validation.
4. Implement guided module learning flow.
5. Implement spaced-repetition review flow.
6. Update docs and tests.
7. Enforce formatting/lint/type/test gates.

## Evolution Policy Decisions (Implemented)
1. Card IDs are globally unique and stable across all modules.
2. Module content is versioned with `content_version`.
3. Completion records capture `completed_content_version`.
4. Completed modules can become `outdated` when content advances.
5. DB schema upgrades are handled by startup migrations (`user_version` + `schema_migrations`).
6. Started/completed modules remain unlocked if prerequisite requirements are tightened later.
7. Admin module reference is consolidated under `Module details` with `Commands`, `Lessons`, and `Progression` views.
8. Module progression reporting uses attempts history where "correct" means at least one correct attempt for a card.
9. End-user launch path supports Python-only execution from repo root via `python cmdtrainer` and module entry via `python -m cmdtrainer`.
10. Profile backup/transfer uses a versioned JSON export format with tolerant import normalization for older payloads and explicit rejection of unsupported newer versions.
