# Spaced Repetition Algorithm

This document defines the current scheduling behavior used by `cmdtrainer`.

Implementation source of truth:
- `src/cmdtrainer/progress.py` (`ProgressStore.record_attempt`, `_interval_from_score`)

## Per-card State

Each card schedule stores:
- `streak`: consecutive correct answers
- `spacing_score`: floating-point mastery score
- `interval_minutes`: last computed interval
- `due_at`: next review timestamp (UTC ISO string)
- `seen_count`: total attempts

## Update Rules

When an attempt is recorded:

1. Attempt history row is saved to `attempts`.
2. Existing schedule is loaded (if absent, defaults are `score=0`, `streak=0`, `seen_count=0`).
3. New schedule is computed:

### Correct Answer

- `streak = prev_streak + 1`
- `spacing_score = max(0.0, prev_score + 1.0 + (0.15 * prev_streak))`
- `interval_minutes = interval_from_score(spacing_score)`
- `due_at = now + interval_minutes`

### Incorrect Answer

- `streak = 0`
- `spacing_score = max(0.0, (prev_score * 0.6) - 0.5)`
- `interval_minutes = 2`
- `due_at = now + 2 minutes`

Incorrect answers are intentionally scheduled very soon, regardless of previous score.

## Interval Function

`interval_from_score(score)`:

- `minutes = round(10 * (1.7 ** score))`
- bounded to `[2, 43200]` minutes
  - minimum: 2 minutes
  - maximum: 30 days

## Queue Selection (Practice)

Practice queue logic in `src/cmdtrainer/service.py`:
- Use completed modules first; if none, fall back to started modules.
- Cards with no schedule are treated as `new` and effectively due now.
- `due_at <= now` => status `due`; otherwise `scheduled`.
- Results sorted by due time.
- A repeat-avoid rule tries not to show the same card first twice in a row when alternatives exist.

