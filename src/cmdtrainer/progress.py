"""SQLite persistence for profiles and spaced-repetition state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Profile:
    """User profile record."""

    id: int
    name: str


@dataclass(frozen=True)
class CardSchedule:
    """Scheduling snapshot for one card."""

    card_id: str
    streak: int
    spacing_score: float
    interval_minutes: int
    due_at: str
    seen_count: int


class ProgressStore:
    """Database access layer for learner progress."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize database and schema."""
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
            target = str(db_path)
        else:
            target = db_path
        self._conn = sqlite3.connect(target)
        self._conn.row_factory = sqlite3.Row
        self._card_progress_has_interval_days = False
        self._init_db()

    def _init_db(self) -> None:
        self._apply_migrations()
        self._ensure_column("module_progress", "completed_content_version", "INTEGER")
        self._ensure_column("card_progress", "spacing_score", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("card_progress", "interval_minutes", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_attempts_schema()
        self._card_progress_has_interval_days = self._has_column("card_progress", "interval_days")

    def _apply_migrations(self) -> None:
        """Apply forward-only schema migrations to latest version."""
        current = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"Database schema version {current} is newer than supported {SCHEMA_VERSION}.")

        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """)

        for version in range(current + 1, SCHEMA_VERSION + 1):
            if version == 1:
                self._migrate_to_v1()
            with self._conn:
                self._conn.execute(f"PRAGMA user_version = {version}")
                self._conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )

    def _migrate_to_v1(self) -> None:
        """Create core tables and add module completion content-version tracking."""
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS module_progress (
                    profile_id INTEGER NOT NULL,
                    module_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    completed_content_version INTEGER,
                    PRIMARY KEY (profile_id, module_id)
                )
                """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS card_progress (
                    profile_id INTEGER NOT NULL,
                    card_id TEXT NOT NULL,
                    streak INTEGER NOT NULL,
                    spacing_score REAL NOT NULL DEFAULT 0,
                    interval_minutes INTEGER NOT NULL DEFAULT 0,
                    due_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_result INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL,
                    PRIMARY KEY (profile_id, card_id)
                )
                """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    card_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {str(row["name"]) for row in rows}
        if column in names:
            return
        with self._conn:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _has_column(self, table: str, column: str) -> bool:
        """Return whether a table currently contains a column."""
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {str(row["name"]) for row in rows}
        return column in names

    def _ensure_attempts_schema(self) -> None:
        """Repair attempts table when an older incompatible schema exists."""
        rows = self._conn.execute("PRAGMA table_info(attempts)").fetchall()
        names = {str(row["name"]) for row in rows}
        required = {"id", "profile_id", "card_id", "user_input", "is_correct", "created_at"}
        if required.issubset(names):
            return
        with self._conn:
            self._conn.execute("DROP TABLE IF EXISTS attempts")
            self._conn.execute("""
                CREATE TABLE attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    card_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)

    def list_profiles(self) -> list[Profile]:
        """Return profiles ordered by name."""
        rows = self._conn.execute("SELECT id, name FROM profiles ORDER BY name").fetchall()
        return [Profile(id=int(row["id"]), name=str(row["name"])) for row in rows]

    def create_profile(self, name: str) -> Profile:
        """Create a new profile."""
        now = datetime.now(UTC).isoformat()
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO profiles (name, created_at) VALUES (?, ?)",
                (name, now),
            )
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("Could not create profile.")
        return Profile(id=int(row_id), name=name)

    def get_profile(self, profile_id: int) -> Profile | None:
        """Get one profile by id."""
        row = self._conn.execute("SELECT id, name FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            return None
        return Profile(id=int(row["id"]), name=str(row["name"]))

    def delete_profile(self, profile_id: int) -> bool:
        """Delete profile and all associated progress data."""
        with self._conn:
            self._conn.execute("DELETE FROM attempts WHERE profile_id = ?", (profile_id,))
            self._conn.execute("DELETE FROM card_progress WHERE profile_id = ?", (profile_id,))
            self._conn.execute("DELETE FROM module_progress WHERE profile_id = ?", (profile_id,))
            cursor = self._conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return cursor.rowcount > 0

    def mark_module_started(self, profile_id: int, module_id: str) -> None:
        """Set module started timestamp if absent."""
        now = datetime.now(UTC).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO module_progress (
                    profile_id,
                    module_id,
                    started_at,
                    completed_at,
                    completed_content_version
                )
                VALUES (?, ?, ?, NULL, NULL)
                """,
                (profile_id, module_id, now),
            )

    def mark_module_completed(self, profile_id: int, module_id: str, content_version: int | None = None) -> None:
        """Set module completed timestamp."""
        now = datetime.now(UTC).isoformat()
        self.mark_module_started(profile_id, module_id)
        if content_version is None:
            content_version = 1
        with self._conn:
            self._conn.execute(
                """
                UPDATE module_progress
                SET completed_at = ?, completed_content_version = ?
                WHERE profile_id = ? AND module_id = ?
                """,
                (now, content_version, profile_id, module_id),
            )

    def module_state(self, profile_id: int, module_id: str) -> tuple[bool, bool, int | None]:
        """Return (started, completed, completed_content_version) state for a module."""
        row = self._conn.execute(
            """
            SELECT started_at, completed_at, completed_content_version
            FROM module_progress
            WHERE profile_id = ? AND module_id = ?
            """,
            (profile_id, module_id),
        ).fetchone()
        if row is None:
            return (False, False, None)
        return (
            True,
            row["completed_at"] is not None,
            int(row["completed_content_version"]) if row["completed_content_version"] is not None else None,
        )

    def completed_module_ids(self, profile_id: int) -> set[str]:
        """Return completed module ids."""
        rows = self._conn.execute(
            "SELECT module_id FROM module_progress WHERE profile_id = ? AND completed_at IS NOT NULL",
            (profile_id,),
        ).fetchall()
        return {str(row["module_id"]) for row in rows}

    def started_module_ids(self, profile_id: int) -> set[str]:
        """Return started module ids."""
        rows = self._conn.execute(
            "SELECT module_id FROM module_progress WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
        return {str(row["module_id"]) for row in rows}

    def attempted_card_ids(self, profile_id: int, card_ids: list[str]) -> set[str]:
        """Return card ids with at least one attempt for the profile."""
        if not card_ids:
            return set()
        placeholders = ", ".join("?" for _ in card_ids)
        rows = self._conn.execute(
            f"""
            SELECT DISTINCT card_id
            FROM attempts
            WHERE profile_id = ? AND card_id IN ({placeholders})
            """,
            (profile_id, *card_ids),
        ).fetchall()
        return {str(row["card_id"]) for row in rows}

    def correct_card_ids(self, profile_id: int, card_ids: list[str]) -> set[str]:
        """Return card ids with at least one correct attempt for the profile."""
        if not card_ids:
            return set()
        placeholders = ", ".join("?" for _ in card_ids)
        rows = self._conn.execute(
            f"""
            SELECT DISTINCT card_id
            FROM attempts
            WHERE profile_id = ? AND is_correct = 1 AND card_id IN ({placeholders})
            """,
            (profile_id, *card_ids),
        ).fetchall()
        return {str(row["card_id"]) for row in rows}

    def get_card_schedule(self, profile_id: int, card_id: str) -> CardSchedule | None:
        """Return current schedule for card if present."""
        row = self._conn.execute(
            """
            SELECT card_id, streak, spacing_score, interval_minutes, due_at, seen_count
            FROM card_progress
            WHERE profile_id = ? AND card_id = ?
            """,
            (profile_id, card_id),
        ).fetchone()
        if row is None:
            return None
        return CardSchedule(
            card_id=str(row["card_id"]),
            streak=int(row["streak"]),
            spacing_score=float(row["spacing_score"]),
            interval_minutes=int(row["interval_minutes"]),
            due_at=str(row["due_at"]),
            seen_count=int(row["seen_count"]),
        )

    def list_card_schedules(self, profile_id: int) -> list[CardSchedule]:
        """Return all card schedules for a profile ordered by due time."""
        rows = self._conn.execute(
            """
            SELECT card_id, streak, spacing_score, interval_minutes, due_at, seen_count
            FROM card_progress
            WHERE profile_id = ?
            ORDER BY due_at ASC
            """,
            (profile_id,),
        ).fetchall()
        return [
            CardSchedule(
                card_id=str(row["card_id"]),
                streak=int(row["streak"]),
                spacing_score=float(row["spacing_score"]),
                interval_minutes=int(row["interval_minutes"]),
                due_at=str(row["due_at"]),
                seen_count=int(row["seen_count"]),
            )
            for row in rows
        ]

    def record_attempt(self, profile_id: int, card_id: str, user_input: str, is_correct: bool) -> None:
        """Record one card attempt and update spacing schedule.

        Model:
        - `spacing_score` grows on correct answers and shrinks on incorrect answers.
        - next interval (minutes) is exponential in `spacing_score`.
        - incorrect answers are always scheduled very soon (2 minutes), regardless of score.
        """
        now = datetime.now(UTC)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO attempts (profile_id, card_id, user_input, is_correct, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (profile_id, card_id, user_input, int(is_correct), now.isoformat()),
            )

        previous = self.get_card_schedule(profile_id, card_id)
        if previous is None:
            prev_score = 0.0
            prev_streak = 0
            seen_count = 1
        else:
            prev_score = previous.spacing_score
            prev_streak = previous.streak
            seen_count = previous.seen_count + 1

        if is_correct:
            streak = prev_streak + 1
            spacing_score = max(0.0, prev_score + 1.0 + (0.15 * prev_streak))
            interval_minutes = _interval_from_score(spacing_score)
            due = now + timedelta(minutes=interval_minutes)
        else:
            streak = 0
            spacing_score = max(0.0, (prev_score * 0.6) - 0.5)
            interval_minutes = 2
            due = now + timedelta(minutes=2)

        with self._conn:
            if self._card_progress_has_interval_days:
                interval_days = max(0, interval_minutes // (60 * 24))
                self._conn.execute(
                    """
                    INSERT INTO card_progress (
                        profile_id,
                        card_id,
                        streak,
                        interval_days,
                        spacing_score,
                        interval_minutes,
                        due_at,
                        last_seen_at,
                        last_result,
                        seen_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(profile_id, card_id) DO UPDATE SET
                        streak = excluded.streak,
                        interval_days = excluded.interval_days,
                        spacing_score = excluded.spacing_score,
                        interval_minutes = excluded.interval_minutes,
                        due_at = excluded.due_at,
                        last_seen_at = excluded.last_seen_at,
                        last_result = excluded.last_result,
                        seen_count = excluded.seen_count
                    """,
                    (
                        profile_id,
                        card_id,
                        streak,
                        interval_days,
                        spacing_score,
                        interval_minutes,
                        due.isoformat(),
                        now.isoformat(),
                        int(is_correct),
                        seen_count,
                    ),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO card_progress (
                        profile_id,
                        card_id,
                        streak,
                        spacing_score,
                        interval_minutes,
                        due_at,
                        last_seen_at,
                        last_result,
                        seen_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(profile_id, card_id) DO UPDATE SET
                        streak = excluded.streak,
                        spacing_score = excluded.spacing_score,
                        interval_minutes = excluded.interval_minutes,
                        due_at = excluded.due_at,
                        last_seen_at = excluded.last_seen_at,
                        last_result = excluded.last_result,
                        seen_count = excluded.seen_count
                    """,
                    (
                        profile_id,
                        card_id,
                        streak,
                        spacing_score,
                        interval_minutes,
                        due.isoformat(),
                        now.isoformat(),
                        int(is_correct),
                        seen_count,
                    ),
                )

    def close(self) -> None:
        """Close db connection."""
        self._conn.close()

    def __del__(self) -> None:  # pragma: no cover
        """Best-effort connection cleanup."""
        try:
            self.close()
        except Exception:
            pass


def _interval_from_score(score: float) -> int:
    """Convert spacing score to interval minutes using bounded exponential growth."""
    minutes = int(round(10 * (1.7**score)))
    return max(2, min(minutes, 60 * 24 * 30))
