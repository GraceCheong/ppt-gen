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


def save_weekly_repertoire_snapshot(
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
    max_lines_per_slide: int,
    max_chars_per_line: int,
    lyrics_font_size,
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
                week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(week_end_date) DO UPDATE SET
                week_start_date=excluded.week_start_date,
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json,
                lyrics_by_title_json=excluded.lyrics_by_title_json,
                max_lines_per_slide=excluded.max_lines_per_slide,
                max_chars_per_line=excluded.max_chars_per_line,
                lyrics_font_size=excluded.lyrics_font_size
            """,
            (
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
        conn.commit()

    return week_end.isoformat()


def update_weekly_roles(
    week_end_date: str,
    worship_leader: str,
    accompanist: str,
    prayer_person: str,
) -> None:
    """담당자(송리스트·반주자·기도자) 정보를 저장한다. 항목이 없으면 빈 셋리스트로 생성."""
    week_end = datetime.date.fromisoformat(week_end_date)
    week_start = week_end - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size,
                worship_leader, accompanist, prayer_person
            ) VALUES (?, ?, ?, '[]', '{}', 4, 18, NULL, ?, ?, ?)
            ON CONFLICT(week_end_date) DO UPDATE SET
                worship_leader=excluded.worship_leader,
                accompanist=excluded.accompanist,
                prayer_person=excluded.prayer_person,
                updated_at_utc=excluded.updated_at_utc
            """,
            (week_end_date, week_start.isoformat(), updated_at,
             worship_leader, accompanist, prayer_person),
        )
        conn.commit()


def update_weekly_entry(
    week_end_date: str,
    sequence_entries: list[tuple[str, str]],
) -> str:
    """기존 주간 이력의 곡 목록을 수정한다 (날짜는 변경하지 않음)."""
    week_end = datetime.date.fromisoformat(week_end_date)
    week_start = week_end - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size
            ) VALUES (?, ?, ?, ?, '{}', 4, 18, NULL)
            ON CONFLICT(week_end_date) DO UPDATE SET
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json
            """,
            (
                week_end_date,
                week_start.isoformat(),
                updated_at,
                json.dumps(
                    [{"title": t, "sequence": s} for t, s in sequence_entries],
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
    return week_end_date


def save_weekly_entry_manual(
    week_end_date: datetime.date,
    sequence_entries: list[tuple[str, str]],
) -> str:
    """수동 입력으로 주간 이력을 저장한다."""
    week_start = week_end_date - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                week_end_date, week_start_date, updated_at_utc,
                sequence_entries_json, lyrics_by_title_json,
                max_lines_per_slide, max_chars_per_line, lyrics_font_size
            ) VALUES (?, ?, ?, ?, '{}', 4, 18, NULL)
            ON CONFLICT(week_end_date) DO UPDATE SET
                week_start_date=excluded.week_start_date,
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json
            """,
            (
                week_end_date.isoformat(),
                week_start.isoformat(),
                updated_at,
                json.dumps(
                    [{"title": t, "sequence": s} for t, s in sequence_entries],
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
    return week_end_date.isoformat()


def index_lyrics_from_snapshot(
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
) -> None:
    """주간 스냅샷 저장 시 lyrics_catalog에 가사를 자동 색인한다."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sequence_map = {title: seq for title, seq in sequence_entries}

    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
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


def list_weekly_repertoire(year_from: int = 2026) -> list[dict]:
    db_path = history_db_path()
    min_date = datetime.date(year_from, 1, 1).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT week_end_date, week_start_date, updated_at_utc,
                   sequence_entries_json, lyrics_by_title_json,
                   max_lines_per_slide, max_chars_per_line, lyrics_font_size,
                   worship_leader, accompanist, prayer_person
            FROM weekly_repertoire
            WHERE week_end_date >= ?
            ORDER BY week_end_date DESC
            """,
            (min_date,),
        ).fetchall()

    return [
        {
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
        for row in rows
    ]
