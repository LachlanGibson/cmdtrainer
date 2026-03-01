# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

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
