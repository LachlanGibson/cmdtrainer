import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cmdtrainer.progress import ProgressStore


def test_profiles_and_module_state() -> None:
    store = ProgressStore(":memory:")
    profile = store.create_profile("alice")
    assert store.list_profiles()[0].name == "alice"

    store.mark_module_started(profile.id, "base-linux")
    started, completed, completed_version = store.module_state(profile.id, "base-linux")
    assert started is True
    assert completed is False
    assert completed_version is None

    store.mark_module_completed(profile.id, "base-linux", 3)
    _, completed, completed_version = store.module_state(profile.id, "base-linux")
    assert completed is True
    assert completed_version == 3


def test_delete_profile_removes_related_progress() -> None:
    store = ProgressStore(":memory:")
    profile = store.create_profile("remove-me")
    store.mark_module_started(profile.id, "base-linux")
    store.mark_module_completed(profile.id, "base-linux")
    store.record_attempt(profile.id, "card-x", "pwd", True)

    deleted = store.delete_profile(profile.id)
    assert deleted is True
    assert store.get_profile(profile.id) is None
    assert store.module_state(profile.id, "base-linux") == (False, False, None)
    assert store.get_card_schedule(profile.id, "card-x") is None


def test_delete_profile_missing_returns_false() -> None:
    store = ProgressStore(":memory:")
    assert store.delete_profile(9999) is False


def test_migration_sets_user_version_and_schema_history() -> None:
    store = ProgressStore(":memory:")
    version = int(store._conn.execute("PRAGMA user_version").fetchone()[0])  # noqa: SLF001
    assert version == 1
    rows = store._conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()  # noqa: SLF001
    assert [int(row["version"]) for row in rows] == [1]


def test_card_progress_scheduling() -> None:
    store = ProgressStore(":memory:")
    profile = store.create_profile("bob")

    store.record_attempt(profile.id, "card-1", "pwd", True)
    schedule = store.get_card_schedule(profile.id, "card-1")
    assert schedule is not None
    assert schedule.streak == 1
    assert schedule.spacing_score > 0
    assert schedule.interval_minutes >= 2

    store.record_attempt(profile.id, "card-1", "bad", False)
    schedule = store.get_card_schedule(profile.id, "card-1")
    assert schedule is not None
    assert schedule.streak == 0
    assert schedule.spacing_score >= 0
    assert schedule.interval_minutes == 2
    assert schedule.seen_count == 2
    assert datetime.fromisoformat(schedule.due_at) >= datetime.now(UTC).replace(microsecond=0)


def test_wrong_answer_is_due_soon_even_after_growth() -> None:
    store = ProgressStore(":memory:")
    profile = store.create_profile("dana")

    for _ in range(3):
        store.record_attempt(profile.id, "card-a", "ok", True)

    grown = store.get_card_schedule(profile.id, "card-a")
    assert grown is not None
    assert grown.spacing_score > 1.0
    assert grown.interval_minutes > 2

    store.record_attempt(profile.id, "card-a", "bad", False)
    shrunk = store.get_card_schedule(profile.id, "card-a")
    assert shrunk is not None
    assert shrunk.interval_minutes == 2
    assert shrunk.spacing_score < grown.spacing_score


def test_path_database_creation(tmp_path: Path) -> None:
    db_path = tmp_path / "progress.db"

    store = ProgressStore(db_path)
    profile = store.create_profile("charlie")
    assert profile.name == "charlie"
    assert db_path.exists()


def test_list_card_schedules_returns_ordered_rows() -> None:
    store = ProgressStore(":memory:")
    profile = store.create_profile("sched")
    store.record_attempt(profile.id, "card-1", "ok", True)
    store.record_attempt(profile.id, "card-2", "ok", False)
    rows = store.list_card_schedules(profile.id)
    assert len(rows) == 2
    assert rows[0].due_at <= rows[1].due_at


def test_migrates_legacy_attempts_table_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "progress-legacy.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_id TEXT NOT NULL,
                passed INTEGER NOT NULL,
                score REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
        conn.commit()
    finally:
        conn.close()

    store = ProgressStore(db_path)
    profile = store.create_profile("legacy-user")
    store.record_attempt(profile.id, "card-legacy", "pwd", True)
    schedule = store.get_card_schedule(profile.id, "card-legacy")
    assert schedule is not None


def test_supports_legacy_card_progress_interval_days_not_null(tmp_path: Path) -> None:
    db_path = tmp_path / "progress-legacy-card.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE module_progress (
                profile_id INTEGER NOT NULL,
                module_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (profile_id, module_id)
            )
            """)
        conn.execute("""
            CREATE TABLE card_progress (
                profile_id INTEGER NOT NULL,
                card_id TEXT NOT NULL,
                streak INTEGER NOT NULL,
                interval_days INTEGER NOT NULL,
                due_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_result INTEGER NOT NULL,
                seen_count INTEGER NOT NULL,
                PRIMARY KEY (profile_id, card_id)
            )
            """)
        conn.execute("""
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                card_id TEXT NOT NULL,
                user_input TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
        conn.commit()
    finally:
        conn.close()

    store = ProgressStore(db_path)
    profile = store.create_profile("legacy-card-user")
    store.record_attempt(profile.id, "card-legacy-2", "pwd", True)
    schedule = store.get_card_schedule(profile.id, "card-legacy-2")
    assert schedule is not None


def test_migrates_legacy_module_progress_without_completed_content_version(tmp_path: Path) -> None:
    db_path = tmp_path / "progress-legacy-module.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE module_progress (
                profile_id INTEGER NOT NULL,
                module_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (profile_id, module_id)
            )
            """)
        conn.execute("""
            CREATE TABLE card_progress (
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
        conn.execute("""
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                card_id TEXT NOT NULL,
                user_input TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
        conn.commit()
    finally:
        conn.close()

    store = ProgressStore(db_path)
    profile = store.create_profile("legacy-module-user")
    store.mark_module_completed(profile.id, "base-linux", 2)
    started, completed, completed_version = store.module_state(profile.id, "base-linux")
    assert started is True
    assert completed is True
    assert completed_version == 2


def test_replace_profile_data_supports_interval_days_branch() -> None:
    store = ProgressStore(":memory:")
    profile = store.create_profile("replace-legacy")
    store._ensure_column("card_progress", "interval_days", "INTEGER NOT NULL DEFAULT 0")  # noqa: SLF001
    store._card_progress_has_interval_days = True  # noqa: SLF001
    store.replace_profile_data(
        profile.id,
        module_rows=[
            {
                "module_id": "base-linux",
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
                "completed_content_version": None,
            }
        ],
        card_rows=[
            {
                "card_id": "base-linux-pwd",
                "streak": 1,
                "spacing_score": 1.0,
                "interval_minutes": "15",
                "due_at": datetime.now(UTC).isoformat(),
                "last_seen_at": datetime.now(UTC).isoformat(),
                "last_result": 1,
                "seen_count": 1,
            }
        ],
        attempt_rows=[
            {
                "card_id": "base-linux-pwd",
                "user_input": "pwd",
                "is_correct": 1,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ],
    )
    assert store.module_state(profile.id, "base-linux")[0] is True
    assert store.get_card_schedule(profile.id, "base-linux-pwd") is not None
