"""DB 경로 헬퍼 및 스키마 초기화."""
from __future__ import annotations

import os
import sqlite3

from server.app.config import ROOT_DIR


def history_db_path() -> str:
    history_dir = os.path.join(ROOT_DIR, "out", "history")
    os.makedirs(history_dir, exist_ok=True)
    return os.path.join(history_dir, "weekly_repertoire.db")


def init_history_db() -> None:
    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_repertoire (
                week_end_date TEXT PRIMARY KEY,
                week_start_date TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                sequence_entries_json TEXT NOT NULL,
                lyrics_by_title_json TEXT NOT NULL,
                max_lines_per_slide INTEGER,
                max_chars_per_line INTEGER,
                lyrics_font_size TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lyrics_catalog (
                title_key TEXT PRIMARY KEY,
                display_title TEXT NOT NULL,
                english_title TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                lyrics TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lyrics_catalog_display ON lyrics_catalog(display_title)"
        )

        # 기존 sequence 데이터 정규화
        from server.app.services.lyrics_service import normalize_sequence
        rows = conn.execute(
            "SELECT title_key, sequence FROM lyrics_catalog WHERE sequence != ''"
        ).fetchall()
        for title_key, seq in rows:
            normalized = normalize_sequence(seq)
            if normalized != seq:
                conn.execute(
                    "UPDATE lyrics_catalog SET sequence=? WHERE title_key=?",
                    (normalized, title_key),
                )

        _migrate_add_english_title(conn)
        _migrate_add_roles(conn)
        conn.commit()


def _migrate_add_roles(conn: sqlite3.Connection) -> None:
    """weekly_repertoire 에 담당자 컬럼 추가."""
    for col in ("worship_leader", "accompanist", "prayer_person"):
        try:
            conn.execute(
                f"ALTER TABLE weekly_repertoire ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass  # 이미 존재


_SOURCE_PRIORITY = {"manual": 0, "history": 1, "bugs": 2}


def _merge_source(a: str, b: str) -> str:
    """두 source 값 중 우선순위가 높은 것을 반환. manual > history > bugs."""
    return a if _SOURCE_PRIORITY.get(a, 99) <= _SOURCE_PRIORITY.get(b, 99) else b


def _migrate_add_english_title(conn: sqlite3.Connection) -> None:
    """english_title 컬럼 추가 + 영어 부제 분리 + 중복 항목 병합.

    컬럼이 이미 존재하면 마이그레이션이 완료된 것으로 보고 조기 반환한다.
    """
    from server.app.services.lyrics_service import split_display_title

    column_added = False
    try:
        conn.execute("ALTER TABLE lyrics_catalog ADD COLUMN english_title TEXT NOT NULL DEFAULT ''")
        column_added = True
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 있음 — 마이그레이션 완료

    if not column_added:
        return

    rows = conn.execute(
        "SELECT title_key, display_title, english_title, sequence, lyrics, source, "
        "created_at_utc, updated_at_utc FROM lyrics_catalog"
    ).fetchall()

    # 전체 행을 dict로 선행 로드 — 중복 병합 시 O(1) 조회
    row_by_key: dict[str, tuple] = {r[0]: r for r in rows}

    for (title_key, display_title, english_title,
         sequence, lyrics, source, created_at, updated_at) in rows:

        korean, english = split_display_title(display_title)
        new_key = korean.lower()  # split_display_title이 이미 strip() 적용
        effective_english = english or english_title

        if new_key == title_key:
            if effective_english != english_title or korean != display_title:
                conn.execute(
                    "UPDATE lyrics_catalog SET display_title=?, english_title=? WHERE title_key=?",
                    (korean, effective_english, title_key),
                )
            continue

        existing = row_by_key.get(new_key)
        if existing:
            _, _, ex_eng, ex_seq, ex_lyrics, ex_source, _, _ = existing
            merged_lyrics = lyrics if len(lyrics) >= len(ex_lyrics) else ex_lyrics
            merged_seq = sequence or ex_seq
            merged_eng = effective_english or ex_eng
            merged_source = _merge_source(source, ex_source)
            conn.execute(
                "UPDATE lyrics_catalog "
                "SET display_title=?, english_title=?, sequence=?, lyrics=?, source=? "
                "WHERE title_key=?",
                (korean, merged_eng, merged_seq, merged_lyrics, merged_source, new_key),
            )
            conn.execute("DELETE FROM lyrics_catalog WHERE title_key=?", (title_key,))
        else:
            conn.execute(
                "UPDATE lyrics_catalog "
                "SET title_key=?, display_title=?, english_title=? WHERE title_key=?",
                (new_key, korean, effective_english, title_key),
            )
            row_by_key[new_key] = row_by_key.pop(title_key)
