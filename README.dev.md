# README.dev.md

Developer notes for `cmdtrainer`.

## Architecture
- `src/cmdtrainer/main.py`: interactive shell, user/admin menus, and CLI flows
- `src/cmdtrainer/service.py`: business logic (profiles, modules, validation, scheduling, queue, force-unlock)
- `src/cmdtrainer/progress.py`: SQLite persistence
- `src/cmdtrainer/content_loader.py`: JSON content loading and dependency/metadata validation
- `src/cmdtrainer/models.py`: domain models
- `src/cmdtrainer/content/modules/*.json`: module card content

## Dev Environment Setup
```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e .[dev]
```

## Data Model
- `profiles`
- `module_progress`
- `card_progress`
- `attempts`
- `schema_migrations`

Card content fields include:
- `prompt`
- `answers` (accepted command variants; first answer is primary display form)
- `command` (normalized command id for reporting/reference)
- `tested_flags` (explicit flags covered by the card)
- `explanation`

## Spaced Repetition (MVP)
- Correct answers increase streak and grow interval.
- Incorrect answers reset streak and schedule near-term review.
- Due cards are randomized each round.
- Queue view is available via Admin and rendered with local due time.
- Practice eligibility is limited to cards with at least one correct attempt.

## Admin Module Details
- Module details view supports three per-module slices:
  - commands + aggregated tested flags,
  - lesson metadata (`order`, `lesson_id`, card/command counts),
  - profile progression summary (attempted/correct totals + lesson breakdown).
- Progression uses attempts history: "correct" means at least one correct attempt for a card.

## Learn Resume and Outdated Groups
- Learn flow resumes by default by skipping cards that already have a correct attempt.
- When selecting a started module, users can choose restart (`r`) to re-run from the beginning.
- Learn menu includes grouped outdated-module updates to batch newly added cards.

## Profile Export/Import
- Export/import is implemented in `LearnService`:
  - `export_profile(profile_id, export_path)`
  - `import_profile(import_path, profile_name=None)`
- Menu placement:
  - export is available from Admin for the currently selected profile,
  - import is available from the Profiles menu before selecting a profile.
- Export payload is JSON with `format_version`, source metadata, profile name, and progress rows.
- Import compatibility rules:
  - reject unsupported newer `format_version`,
  - accept missing/legacy fields by applying safe defaults,
  - ignore malformed rows that cannot be normalized.

## Quality Gates
Run before finalizing:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e .[dev]

.\.venv\Scripts\black --check src tests
.\.venv\Scripts\ruff check src tests
.\.venv\Scripts\pyright
.\.venv\Scripts\python -m pytest
```

Type checking includes both `src` and `tests` using repository `pyproject.toml` settings.

## Releasing
Version is defined in `pyproject.toml` under `[project].version`.

Suggested release flow:
1. Create a branch for the release work.
2. Update `pyproject.toml` version (SemVer: `MAJOR.MINOR.PATCH`).
3. Run quality gates.
4. Merge to `main`.
5. Tag the merge commit and push tag.
6. Create a GitHub Release from the tag.

Example commands:
```powershell
# after updating pyproject.toml and passing checks
git checkout main
git pull
git tag v0.1.0
git push origin v0.1.0
```

## Coverage
- Required: >=95%
- Enforced by pytest-cov in `pyproject.toml`.

## Content Guardrails
- `tests/test_module_content_baseline.py` enforces baseline command and flag coverage per module.
- `tests/test_module_content_baseline.py` also enforces cross-module command ownership/overlap and prerequisite policy.
- Keep module prerequisites acyclic and valid; loader tests enforce this.

## Versioning and Migration
- Module JSON supports `content_version` (defaults to `1`).
- `module_progress.completed_content_version` stores which module content version a profile completed.
- Service marks a completed module as `outdated` when `completed_content_version < module.content_version`.
- Loader enforces globally unique card IDs across all modules.
- DB schema migration is versioned via SQLite `PRAGMA user_version` and tracked in `schema_migrations`.
- DB migration runs automatically at app startup when `ProgressStore` initializes.

### Developer migration checklist
1. Increase `SCHEMA_VERSION` in `src/cmdtrainer/progress.py`.
2. Add a forward-only migration step in `_apply_migrations()` for the new version.
3. Implement the migration function (for example `_migrate_to_v2`) with required SQL.
4. Add/adjust tests for:
   - fresh DB creation at latest schema
   - migration from previous schema to latest
5. Keep migrations non-destructive where possible and avoid requiring user action.

