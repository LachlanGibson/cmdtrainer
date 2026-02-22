# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

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
