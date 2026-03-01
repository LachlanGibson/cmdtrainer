# cmdtrainer

Profile-based command practice CLI for software developers.

This app does **not execute learner commands**. It validates typed command strings against accepted answers.

## Features

- Startup profile selection/creation.
- Guided first-time module learning:
  - Prompt + answer shown.
  - You type until correct.
- Learn menu supports grouped outdated-module updates.
- General randomized practice with spaced repetition.
- Module prerequisites and progress tracking.
- Module details reference:
  - command and tested flag listing,
  - lesson listing (order, IDs, card/command counts),
  - per-module progression summary with lesson breakdown.
- Practice queue view in table format (local due time, streak, score, interval, command).
- Admin force unlock for a module and all prerequisite modules.
- Profile export/import to JSON for backup and transfer.
- Expanded modules for networking, HTTP clients, tmux, process tooling, and archives/compression.
- Added Node.js and npm learning tracks, including workspace and release-capstone modules.
- Content/version-aware progression:
  - module completion records content version,
  - modules can show as outdated after content updates,
  - started/completed modules stay unlocked if prerequisites are tightened later.

## Quick Start

```powershell
python cmdtrainer
```

Alternative launch modes:

```powershell
python -m cmdtrainer

# after install:
cmdtrainer
```

## How It Works

1. Choose a profile.
2. Use the main menu:
   - `1) Learn a module`
   - `2) General practice`
   - `3) Status`
   - `4) Admin`
   - `b) Back (switch profile)`
   - `q) Quit`
3. After first completion of a module, its cards appear in spaced-repetition review.
4. Use `General practice` for mixed random due cards.
5. Learn flow resumes by default by skipping already-mastered cards; use restart to re-run from the beginning.

## Admin Menu

- `1) Module details`
- `2) View schedule queue`
- `3) Force unlock module (+ dependencies)`
- `4) Export current profile`

Force unlock marks selected module and all prerequisites as completed for the current profile.

Profile menu includes:
- `i) Import profile from file`

Export/import notes:
- Export includes profile progress, card scheduling state, and attempts history.
- Import uses a versioned JSON format and rejects unsupported newer export versions with a clear error.
- Missing optional fields in older export files are defaulted when importing.

Practice notes:
- Practice includes only cards with at least one prior correct attempt.

## Validation

- Validation compares tokenized command input to accepted answer variants.
- Example: `ls -la` and `ls -al` can both be accepted for the same card.
- No command execution or system side effects.

## Module Set

- `base-linux`
- `apt`
- `git`
- `ssh`
- `docker` (Docker Base)
- `docker-compose`
- `docker-network`
- `docker-image`
- `docker-volume`
- `docker-context`
- `file-tools`
- `network-basics`
- `http-clients`
- `tmux`
- `process-tools`
- `archive-tools`
- `node`
- `npm`
- `npm-workspaces`
- `node-release`

## Notes

- Progress is stored in `.cmdtrainer/progress.db`.
- If no completed modules exist, general practice falls back to started modules.
- The app runs SQLite migrations automatically at startup.
