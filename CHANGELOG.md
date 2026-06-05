# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Changed

- The Docker Base "list local images" card now accepts both `docker images` and the equivalent `docker image ls`. The redundant standalone `docker image ls` card was removed from the Docker Image Management module (its `docker image` command and flag coverage remain via the dangling-filter and prune cards).

### Fixed

- Learn module list now numbers each page's rows from 1 again. Previously, rows on page 2 and beyond continued the global count (10, 11, …) even though the menu only accepts keys 1-9, so the displayed numbers did not match the keys needed to select those modules.

## [1.5.0] - 2026-04-12

### Changed

- All navigation menus now respond to a single keypress without requiring Enter. Options are displayed as `[key] Label` to make the expected input mode immediately clear.
- Dynamic module and profile lists paginate at 9 items per page. `[n]`/`[p]` navigate next/previous pages consistently across all lists. Creating a new profile uses `[c]` (create) to free up `[n]` for pagination.
- Confirmation and continue prompts (resume/restart, grouped-outdated start, practice-round continue) now also use single-keypress. Any key except `[b]` or `[q]` proceeds; there is no longer an Enter requirement.
- Exit commands during card answer typing now require a colon prefix (`:b`, `:back`, `:q`, `:quit`, `:exit`). Plain words like `back` or `quit` are treated as incorrect answers, consistent with the existing v1.4.0 policy.
- Invalid keypresses on navigation menus are silently ignored and the menu re-renders, replacing the previous "Invalid choice." message.

## [1.4.1] - 2026-04-12

### Changed

- Practice schedule queue (Admin menu) now displays intervals in human-readable units: minutes below 2 hours, hours below 2 days, days otherwise.

### Fixed

- General practice now includes cards from started-but-not-completed modules even when another module has been fully completed. Previously, once any module was completed, in-progress modules were excluded from the practice queue entirely.
- Force-unlocking a module via the Admin menu now seeds all its cards into the practice queue. Previously, force-unlocked modules were marked complete but had no attempts recorded, so none of their cards ever appeared in general practice.

## [1.4.0] - 2026-03-25

### Changed

- General practice no longer stops at a hard limit of 10 cards. After each 10-card round, if more cards are due the user is prompted with the remaining due count and can continue or stop (b/q). If no cards are due but the queue has future cards, the user is offered the option to practice ahead of schedule.
- Bare `back` (without a leading colon) is no longer accepted as an exit command during practice; a colon prefix (`:b`, `:back`, `:q`, `:quit`) is required to distinguish control commands from typed answers.
- Incorrect answers now schedule cards as immediately due (interval 0) instead of after a 2-minute delay, so they always reappear in the next practice batch.

### Fixed

- Resuming a started module and completing it no longer leaves the module stuck in "started" state. Previously, if a card's spaced-repetition streak was reset to 0 by a wrong answer during general practice between sessions, the module would never be marked as completed even after all cards were answered correctly on resume.

## [1.3.0] - 2026-03-01

### Added

- New Node.js runtime module (`node`) covering execution, diagnostics, watch mode, env-file usage, and built-in test runner flags.
- New npm fundamentals module (`npm`) covering init, dependency workflows, scripts/exec, audit/security, config, and publishing basics.
- New npm workspaces module (`npm-workspaces`) for workspace-targeted install/run/exec/list/pkg workflows.
- New Node release capstone module (`node-release`) covering preflight checks, packaging, versioning, tagging, publishing, and dist-tag operations.

### Changed

- Module baseline ownership/overlap policy now includes npm/git command ownership used by the new capstone/workspace modules.
- Command normalization tests now include npm script passthrough and workspace short-flag ordering cases.

## [1.2.1] - 2026-02-25

### Fixed

- Command-answer normalization now treats attached and split numeric short-option values as equivalent (for example `-p2222` and `-p 2222`) to avoid false negatives during grading.

## [1.2.0] - 2026-02-23

### Added

- Learn menu now includes grouped outdated-module updates.

### Changed

- Learn flow now resumes by default by skipping already-mastered cards, with an explicit restart option for started modules.
- Practice eligibility now requires at least one prior correct attempt for a card.

## [1.1.0] - 2026-02-22

### Added

- Profile export/import to JSON (`Export current profile` in Admin, `Import profile from file` in Profiles menu).
- Versioned export format with import compatibility handling:
  - safe defaults for missing legacy fields,
  - malformed-row tolerance,
  - explicit rejection of unsupported newer export versions.

### Changed

- Package version now resolves from project metadata (single source of truth in `pyproject.toml`) with source-run fallback.

## [1.0.0] - 2026-02-22

First public release.
