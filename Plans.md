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

## Module Roadmap (all implemented)
1. `base-linux` — core shell commands
2. `apt`
3. `git`
4. `ssh`
5. `docker`
6. `docker-compose`
7. `docker-network`
8. `docker-image`
9. `docker-volume`
10. `docker-context`
11. `file-tools`
12. `network-basics`
13. `http-clients`
14. `tmux`
15. `process-tools`
16. `archive-tools`
17. `node`
18. `npm`
19. `npm-workspaces`
20. `node-release`

## Dependency Graph
- base-linux → apt
- base-linux → git
- base-linux → ssh
- base-linux → docker
- docker → docker-compose
- docker + ssh → docker-context
- base-linux → file-tools
- base-linux → docker-network
- base-linux → docker-image
- base-linux → docker-volume
- base-linux → network-basics
- network-basics → http-clients
- base-linux → tmux
- base-linux → process-tools
- base-linux → archive-tools
- base-linux → node
- node → npm
- npm → npm-workspaces
- git + npm → node-release

## Learning and Practice Model
### First-time module learning
1. Show card prompt and expected answer.
2. Learner types command.
3. Validate by accepted command forms.
4. Require correctness before moving to next card.
5. Mark module complete after all cards answered correctly for first completion.

### General practice
1. Draw due cards from completed or started modules.
2. Randomize card order among due cards.
3. Update spaced-repetition schedule based on correct/incorrect.
4. After each round, if more cards are due prompt the user to continue or stop; if no cards are due offer to practice ahead.

## Validation Rules
- Parse command using shell tokenization.
- Compare normalized commands:
  - command token must match,
  - options/flags are order-insensitive,
  - positional argument order is preserved,
  - whitespace inside Go template `{{ ... }}` actions is insignificant (matches Go text/template; trim markers `{{-`/`-}}` preserved),
  - known command-specific option aliases are unified (e.g. `--format` ≡ `-f` for `docker inspect` only; `--workspace` ≡ `-w` for `npm`).
- Support multiple accepted forms per card when syntax variants are meaningfully different.
- Do not execute learner commands.

## Spaced Repetition Strategy
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
  - schedule due immediately (interval 0) so the card reappears in the next practice batch.

## Data Model (SQLite)
- profiles(id, name, created_at)
- module_progress(profile_id, module_id, started_at, completed_at)
- card_progress(profile_id, card_id, streak, spacing_score, interval_minutes, due_at, last_seen_at, last_result, seen_count)
- attempts(id, profile_id, card_id, user_input, is_correct, created_at)

## Risks and Mitigations
- Risk: Overly strict validation causes frustration.
  - Mitigation: multiple accepted answers per card.
- Risk: Scheduling feels unfair.
  - Mitigation: simple transparent intervals.
- Risk: Content maintenance burden.
  - Mitigation: declarative JSON card files.

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
11. Learn flow resumes by default using existing correctness data (skip mastered cards) and offers explicit restart; grouped outdated-module updates are available under Learn.
12. Practice queue/cards are restricted to cards with at least one prior correct attempt; force-unlocking a module seeds its cards into the queue.
13. General practice includes cards from started-but-not-completed modules even when completed modules also have due cards.
14. Schedule intervals display in human-readable units: minutes below 2 hours, hours below 2 days, days otherwise.
15. Control commands during practice require a colon prefix (`:b`, `:back`, `:q`, `:quit`) to distinguish them from typed command answers.

## Next: Navigation Overhaul (planned)

**Goal:** Replace Enter-required menu navigation with single-keypress where appropriate, add pagination for dynamic lists, and provide clear visual signaling of expected input mode.

### Design decisions
- **Two input modes:** instant-key (`readkey`) for all navigation; line input (`readline`) for card answers, file paths, profile names, and `YES` confirmations.
- **Visual signaling:** instant-key menus render options as `[key] Label` (brackets universally understood as single-keypress). Line-input prompts use conventional `Label: ` style.
- **Consistent bindings:** `b`=Back, `q`=Quit, `1`–`9`=Select, `n`=Next page, `p`=Prev page, `Enter`=Confirm/continue. Never vary.
- **Pagination:** page size 9 (maps cleanly to `1`–`9`). Page controls shown only when multiple pages exist.
- **No new dependencies:** getch implemented via standard library (`msvcrt` on Windows, `tty`/`termios` on Unix).
- **Testability:** replace `input_fn: Callable` injection with a single `InputReader` object (`readline` + `readkey` methods). `FakeInputReader` pops from the same flat iterator for both — existing test sequences reusable with minimal wrapping changes.

### Steps

**Step 1 — `InputReader` protocol + implementations**
New file `src/cmdtrainer/input_reader.py`:
- `InputReader` (Protocol): `.readline(prompt) -> str`, `.readkey(prompt) -> str`
- `TerminalInputReader`: real implementation using `input()` and platform getch
- `FakeInputReader(responses: Iterator[str])`: pops from single iterator for both methods
- Update all function signatures from `input_fn: InputFn` to `reader: InputReader`

**Step 2 — Prompt formatting helpers**
- `_nav_options(options, print_fn)`: renders `[key] Label` lines
- `_nav_footer(*pairs, print_fn)`: compact footer for back/quit
- Instant-key menus: print bracketed options, then `reader.readkey("")` (cursor waits silently)

**Step 3 — Consistent key constants, simplify command sets**
- Centralise `KEY_BACK = "b"`, `KEY_QUIT = "q"`, `KEY_NEXT_PAGE = "n"`, `KEY_PREV_PAGE = "p"`
- Remove bloated `CONTINUE_STOP_COMMANDS` and the various `BACK_COMMANDS`/`FLOW_EXIT_COMMANDS` sets
- Colon-prefix commands (`:b`, `:q`, etc.) remain valid for readline (in-practice) mode only

**Step 4 — `paginated_select` helper**
- `_paginated_select(items, reader, print_fn, *, format_fn, page_size=9) -> T | None`
- Returns selected item, `None` (back), or raises `QuitApp` (quit)
- Page header `(Page N/M)` shown only when multiple pages exist
- Invalid key re-renders without an error message

**Step 5 — Convert fixed navigation menus**
Main menu, Admin menu, Module details sub-menu → `readkey` + `_nav_options` display.

**Step 6 — Convert dynamic list menus**
`_learn_module_flow`, `_force_unlock_flow`, `_module_details_flow`, `_select_profile`, `_delete_profile_flow` → `paginated_select`.

**Step 7 — Convert confirmation/continue prompts**
- "Resume or restart" → `[Enter] Resume  [r] Restart`
- "Start grouped updates or cancel" → `[Enter] Start  [b] Cancel`
- "Continue practice or stop" → `[Enter] Continue  [b] Back  [q] Quit`

**Step 8 — Update tests**
- Replace `input_fn=lambda _: next(inputs)` with `reader=FakeInputReader(iter([...]))` throughout `test_main.py`
- Add pagination tests: next/prev page, cross-page selection
- Mark platform-specific getch lines `# pragma: no cover`
