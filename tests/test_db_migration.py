"""DB 마이그레이션 idempotency 및 스키마 검증 테스트."""
import sys
import os
import sqlite3

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    import server.app.services.db as db_mod
    monkeypatch.setattr(db_mod, "history_db_path", lambda: path)
    db_mod.init_history_db()
    return path


def _tables(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _columns(db_path: str, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


# ── 테이블 존재 ────────────────────────────────────────────────────────────────

def test_weekly_repertoire_exists(db):
    assert "weekly_repertoire" in _tables(db)


def test_lyrics_catalog_exists(db):
    assert "lyrics_catalog" in _tables(db)


def test_users_table_exists(db):
    assert "users" in _tables(db)


def test_auth_sessions_table_exists(db):
    assert "auth_sessions" in _tables(db)


def test_song_usage_events_table_exists(db):
    assert "song_usage_events" in _tables(db)


# ── 스키마 검증 ────────────────────────────────────────────────────────────────

def test_weekly_repertoire_has_church_column(db):
    assert "church" in _columns(db, "weekly_repertoire")


def test_weekly_repertoire_composite_pk(db):
    """(church, week_end_date) 복합 PK 확인."""
    with sqlite3.connect(db) as conn:
        # 같은 (church, date) 삽입 시 conflict 발생해야 함
        conn.execute("""
            INSERT INTO weekly_repertoire
            (church, week_end_date, week_start_date, updated_at_utc,
             sequence_entries_json, lyrics_by_title_json)
            VALUES ('A교회', '2025-01-04', '2024-12-29', 'now', '[]', '{}')
        """)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO weekly_repertoire
                (church, week_end_date, week_start_date, updated_at_utc,
                 sequence_entries_json, lyrics_by_title_json)
                VALUES ('A교회', '2025-01-04', '2024-12-29', 'now', '[]', '{}')
            """)


def test_different_church_same_date_allowed(db):
    """같은 날짜, 다른 교회는 허용해야 함."""
    with sqlite3.connect(db) as conn:
        conn.execute("""
            INSERT INTO weekly_repertoire
            (church, week_end_date, week_start_date, updated_at_utc,
             sequence_entries_json, lyrics_by_title_json)
            VALUES ('A교회', '2025-01-11', '2025-01-05', 'now', '[]', '{}')
        """)
        conn.execute("""
            INSERT INTO weekly_repertoire
            (church, week_end_date, week_start_date, updated_at_utc,
             sequence_entries_json, lyrics_by_title_json)
            VALUES ('B교회', '2025-01-11', '2025-01-05', 'now', '[]', '{}')
        """)


def test_users_schema(db):
    cols = _columns(db, "users")
    for required in ("id", "church", "nickname", "password_hash", "created_at", "updated_at"):
        assert required in cols, f"missing column: {required}"


def test_auth_sessions_schema(db):
    cols = _columns(db, "auth_sessions")
    for required in ("token_hash", "user_id", "created_at", "expires_at", "last_used_at"):
        assert required in cols, f"missing column: {required}"


def test_song_usage_events_schema(db):
    cols = _columns(db, "song_usage_events")
    for required in ("id", "church", "week_end_date", "song_key", "title", "used_date"):
        assert required in cols, f"missing column: {required}"


# ── Idempotency ────────────────────────────────────────────────────────────────

def test_init_twice_does_not_raise(tmp_path, monkeypatch):
    """init_history_db()를 두 번 호출해도 오류 없음."""
    path = str(tmp_path / "idem.db")
    import server.app.services.db as db_mod
    monkeypatch.setattr(db_mod, "history_db_path", lambda: path)
    db_mod.init_history_db()
    db_mod.init_history_db()


def test_init_preserves_existing_data(tmp_path, monkeypatch):
    """init_history_db() 재호출 시 기존 데이터 보존."""
    path = str(tmp_path / "preserve.db")
    import server.app.services.db as db_mod
    monkeypatch.setattr(db_mod, "history_db_path", lambda: path)
    db_mod.init_history_db()

    with sqlite3.connect(path) as conn:
        conn.execute("""
            INSERT INTO weekly_repertoire
            (church, week_end_date, week_start_date, updated_at_utc,
             sequence_entries_json, lyrics_by_title_json)
            VALUES ('서울중앙', '2025-06-07', '2025-06-01', 'now', '[]', '{}')
        """)
        conn.commit()

    db_mod.init_history_db()  # 재호출

    with sqlite3.connect(path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM weekly_repertoire").fetchone()[0]
    assert count == 1


# ── WAL 모드 ──────────────────────────────────────────────────────────────────

def test_wal_mode_enabled(db):
    with sqlite3.connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
