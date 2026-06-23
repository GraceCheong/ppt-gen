"""주간 레파토리 이력 서비스."""
from __future__ import annotations

import datetime
import json
import sqlite3

from server.app.services.db import history_db_path
from server.app.services.lyrics_service import normalize_sequence, normalize_lyrics_title


def week_end_saturday(source_date: datetime.date) -> datetime.date:
    """해당 날짜가 속한 주의 토요일을 반환한다 (월=0 … 토=5)."""
    days_until_saturday = (5 - source_date.weekday()) % 7
    return source_date + datetime.timedelta(days=days_until_saturday)


# ── 이력 저장 (쓰기) ──────────────────────────────────────────────────────────

def save_weekly_repertoire_snapshot(
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
    max_lines_per_slide: int,
    max_chars_per_line: int,
    lyrics_font_size,
    church: str = "서울중앙",
) -> str:
    today = datetime.date.today()
    week_end = week_end_saturday(today)
    week_start = week_end - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                church, week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(church, week_end_date) DO UPDATE SET
                week_start_date=excluded.week_start_date,
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json,
                lyrics_by_title_json=excluded.lyrics_by_title_json,
                max_lines_per_slide=excluded.max_lines_per_slide,
                max_chars_per_line=excluded.max_chars_per_line,
                lyrics_font_size=excluded.lyrics_font_size
            """,
            (
                church,
                week_end.isoformat(),
                week_start.isoformat(),
                updated_at,
                json.dumps(
                    [{"title": t, "sequence": s} for t, s in sequence_entries],
                    ensure_ascii=False,
                ),
                json.dumps(lyrics_by_title, ensure_ascii=False),
                int(max_lines_per_slide),
                int(max_chars_per_line),
                "" if lyrics_font_size is None else str(lyrics_font_size),
            ),
        )
        _sync_usage_events(conn, church, week_end.isoformat(), sequence_entries)
        conn.commit()

    return week_end.isoformat()


def update_weekly_roles(
    week_end_date: str,
    worship_leader: str,
    accompanist: str,
    prayer_person: str,
    church: str = "서울중앙",
) -> None:
    """담당자(송리스트·반주자·기도자) 정보를 저장한다. 항목이 없으면 빈 셋리스트로 생성."""
    week_end = datetime.date.fromisoformat(week_end_date)
    week_start = week_end - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                church, week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size,
                worship_leader, accompanist, prayer_person
            ) VALUES (?, ?, ?, ?, '[]', '{}', 4, 18, NULL, ?, ?, ?)
            ON CONFLICT(church, week_end_date) DO UPDATE SET
                worship_leader=excluded.worship_leader,
                accompanist=excluded.accompanist,
                prayer_person=excluded.prayer_person,
                updated_at_utc=excluded.updated_at_utc
            """,
            (church, week_end_date, week_start.isoformat(), updated_at,
             worship_leader, accompanist, prayer_person),
        )
        conn.commit()


def update_weekly_entry(
    week_end_date: str,
    sequence_entries: list[tuple[str, str]],
    church: str = "서울중앙",
) -> str:
    """기존 주간 이력의 곡 목록을 수정한다."""
    week_end = datetime.date.fromisoformat(week_end_date)
    week_start = week_end - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                church, week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size
            ) VALUES (?, ?, ?, ?, ?, '{}', 4, 18, NULL)
            ON CONFLICT(church, week_end_date) DO UPDATE SET
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json
            """,
            (
                church,
                week_end_date,
                week_start.isoformat(),
                updated_at,
                json.dumps(
                    [{"title": t, "sequence": s} for t, s in sequence_entries],
                    ensure_ascii=False,
                ),
            ),
        )
        _sync_usage_events(conn, church, week_end_date, sequence_entries)
        conn.commit()
    return week_end_date


def save_weekly_entry_manual(
    week_end_date: datetime.date,
    sequence_entries: list[tuple[str, str]],
    church: str = "서울중앙",
) -> str:
    """수동 입력으로 주간 이력을 저장한다."""
    week_start = week_end_date - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    date_str = week_end_date.isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                church, week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size
            ) VALUES (?, ?, ?, ?, ?, '{}', 4, 18, NULL)
            ON CONFLICT(church, week_end_date) DO UPDATE SET
                week_start_date=excluded.week_start_date,
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json
            """,
            (
                church,
                date_str,
                week_start.isoformat(),
                updated_at,
                json.dumps(
                    [{"title": t, "sequence": s} for t, s in sequence_entries],
                    ensure_ascii=False,
                ),
            ),
        )
        _sync_usage_events(conn, church, date_str, sequence_entries)
        conn.commit()
    return date_str


# ── 이력 조회 (읽기) ──────────────────────────────────────────────────────────

def list_weekly_repertoire(year_from: int = 2026, church: str = "서울중앙") -> list[dict]:
    """church 기준으로 필터링된 이력 목록을 반환한다."""
    min_date = datetime.date(year_from, 1, 1).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT week_end_date, week_start_date, updated_at_utc,
                   sequence_entries_json, lyrics_by_title_json,
                   max_lines_per_slide, max_chars_per_line, lyrics_font_size,
                   worship_leader, accompanist, prayer_person
            FROM weekly_repertoire
            WHERE church = ? AND week_end_date >= ?
            ORDER BY week_end_date DESC
            """,
            (church, min_date),
        ).fetchall()

    return _rows_to_dicts(rows)


def list_all_weekly_repertoire(year_from: int = 2020) -> list[dict]:
    """모든 교회의 이력을 반환한다 (그래프 데이터용)."""
    min_date = datetime.date(year_from, 1, 1).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT church, week_end_date, week_start_date, updated_at_utc,
                   sequence_entries_json, lyrics_by_title_json,
                   max_lines_per_slide, max_chars_per_line, lyrics_font_size,
                   worship_leader, accompanist, prayer_person
            FROM weekly_repertoire
            WHERE week_end_date >= ?
            ORDER BY week_end_date DESC
            """,
            (min_date,),
        ).fetchall()

    result = []
    for row in rows:
        d = _row_to_dict(row)
        d["church"] = row["church"]
        result.append(d)
    return result


def delete_weekly_entry(week_end_date: str, church: str) -> None:
    """특정 날짜+교회의 이력과 관련 usage events를 삭제한다."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "DELETE FROM song_usage_events WHERE church = ? AND week_end_date = ?",
            (church, week_end_date),
        )
        conn.execute(
            "DELETE FROM weekly_repertoire WHERE church = ? AND week_end_date = ?",
            (church, week_end_date),
        )
        conn.commit()


def get_weekly_entry(week_end_date: str, church: str) -> dict | None:
    """특정 날짜+교회의 이력 항목을 반환한다."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM weekly_repertoire WHERE church = ? AND week_end_date = ?",
            (church, week_end_date),
        ).fetchone()
    return _row_to_dict(row) if row else None


# ── lyrics 색인 ───────────────────────────────────────────────────────────────

def index_lyrics_from_snapshot(
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
) -> None:
    """주간 스냅샷 저장 시 lyrics_catalog에 가사를 자동 색인한다."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sequence_map = {title: seq for title, seq in sequence_entries}

    with sqlite3.connect(history_db_path()) as conn:
        for display_title, lyrics in lyrics_by_title.items():
            if not display_title or not str(lyrics).strip():
                continue
            title_key = normalize_lyrics_title(display_title)
            sequence = normalize_sequence(sequence_map.get(display_title, ""))
            conn.execute(
                """
                INSERT INTO lyrics_catalog (
                    title_key, display_title, sequence, lyrics, source,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, 'history', ?, ?)
                ON CONFLICT(title_key) DO UPDATE SET
                    display_title = excluded.display_title,
                    sequence = CASE
                        WHEN excluded.sequence != '' THEN excluded.sequence
                        ELSE lyrics_catalog.sequence
                    END,
                    lyrics = excluded.lyrics,
                    source = CASE
                        WHEN lyrics_catalog.source = 'manual' THEN 'manual'
                        ELSE 'history'
                    END,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (title_key, display_title, sequence, str(lyrics), now, now),
            )
        conn.commit()


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _sync_usage_events(
    conn: sqlite3.Connection,
    church: str,
    week_end_date: str,
    sequence_entries: list[tuple[str, str]],
) -> None:
    """이력 저장/수정 시 song_usage_events를 동기화한다."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        "DELETE FROM song_usage_events WHERE church = ? AND week_end_date = ?",
        (church, week_end_date),
    )
    for title, _ in sequence_entries:
        title = title.strip()
        if not title:
            continue
        conn.execute(
            """
            INSERT INTO song_usage_events
                (church, week_end_date, song_key, title, used_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (church, week_end_date, title.lower(), title, week_end_date, now),
        )


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "week_end_date": row["week_end_date"],
        "week_start_date": row["week_start_date"],
        "updated_at_utc": row["updated_at_utc"],
        "sequence_entries": json.loads(row["sequence_entries_json"]),
        "lyrics_by_title": json.loads(row["lyrics_by_title_json"]),
        "max_lines_per_slide": row["max_lines_per_slide"],
        "max_chars_per_line": row["max_chars_per_line"],
        "lyrics_font_size": row["lyrics_font_size"] or None,
        "worship_leader": row["worship_leader"] or "",
        "accompanist": row["accompanist"] or "",
        "prayer_person": row["prayer_person"] or "",
    }


def _rows_to_dicts(rows) -> list[dict]:
    return [_row_to_dict(r) for r in rows]
