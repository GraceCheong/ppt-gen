"""가사 카탈로그 CRUD 서비스."""
from __future__ import annotations

import datetime
import sqlite3

from server.app.services.db import history_db_path


def split_display_title(display_title: str) -> tuple[str, str]:
    """'한국어 제목, English Title' → (korean, english).

    영어 파트가 없으면 (original, '') 반환.
    구분 기준: ', ' 이후 ASCII 알파벳이 2자 이상인 경우.
    """
    parts = display_title.split(", ", 1)
    if len(parts) == 2:
        eng = parts[1].strip()
        if sum(1 for c in eng if c.isalpha() and ord(c) < 128) >= 2:
            return parts[0].strip(), eng
    return display_title.strip(), ""


def normalize_lyrics_title(title: str) -> str:
    """검색/중복 확인용 정규화 키 — 한국어 파트만, 소문자."""
    korean, _ = split_display_title(title)
    return korean.lower()


def normalize_sequence(seq: str) -> str:
    """시퀀스 정규화: 대소문자·구분자 무관 → 각 토큰 첫 글자 대문자 + 대시 연결.
    'i-v-c-o' → 'I-V-C-O', 'i v c o' → 'I-V-C-O', 'v1 c v2' → 'V1-C-V2'
    """
    import re
    seq = seq.strip()
    if not seq:
        return seq
    tokens = [t for t in re.split(r"[-\s]+", seq) if t]
    return "-".join(t.capitalize() for t in tokens)


def _catalog_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "title": row["display_title"],
        "english_title": row["english_title"],
        "sequence": row["sequence"],
        "lyrics": row["lyrics"],
        "source": row["source"],
        "updated_at_utc": row["updated_at_utc"],
    }


def search_lyrics_catalog(query: str, limit: int = 10) -> list[dict]:
    db_path = history_db_path()
    pattern = f"%{query.strip()}%"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT display_title, english_title, sequence, lyrics, source, updated_at_utc
            FROM lyrics_catalog
            WHERE display_title LIKE ?
               OR title_key LIKE ?
               OR english_title LIKE ?
            ORDER BY updated_at_utc DESC
            LIMIT ?
            """,
            (pattern, pattern.lower(), pattern, max(1, min(limit, 50))),
        ).fetchall()
    return [_catalog_row_to_dict(row) for row in rows]


def list_recent_lyrics_catalog(limit: int = 50) -> list[dict]:
    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT display_title, english_title, sequence, lyrics, source, updated_at_utc
            FROM lyrics_catalog
            ORDER BY updated_at_utc DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
    return [_catalog_row_to_dict(row) for row in rows]


def lookup_lyrics_by_title(title: str) -> dict | None:
    """한국어 제목 또는 영어 제목으로 검색."""
    title_key = normalize_lyrics_title(title)
    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT display_title, english_title, sequence, lyrics, source, updated_at_utc
            FROM lyrics_catalog WHERE title_key = ?
            """,
            (title_key,),
        ).fetchone()
        if row is None:
            row = conn.execute(
                """
                SELECT display_title, english_title, sequence, lyrics, source, updated_at_utc
                FROM lyrics_catalog WHERE LOWER(english_title) = ?
                """,
                (title.strip().lower(),),
            ).fetchone()
    return _catalog_row_to_dict(row) if row is not None else None


def upsert_lyrics_catalog(
    display_title: str,
    lyrics: str,
    source: str,
    sequence: str = "",
    english_title: str = "",
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    korean, extracted_eng = split_display_title(display_title)
    title_key = normalize_lyrics_title(korean)
    sequence = normalize_sequence(sequence)
    effective_english = english_title.strip() or extracted_eng

    db_path = history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO lyrics_catalog (
                title_key, display_title, english_title, sequence, lyrics, source,
                created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(title_key) DO UPDATE SET
                display_title = excluded.display_title,
                english_title = CASE
                    WHEN excluded.english_title != '' THEN excluded.english_title
                    ELSE lyrics_catalog.english_title
                END,
                sequence = CASE
                    WHEN excluded.sequence != '' THEN excluded.sequence
                    ELSE lyrics_catalog.sequence
                END,
                lyrics = CASE WHEN excluded.lyrics != '' THEN excluded.lyrics ELSE lyrics_catalog.lyrics END,
                source = CASE
                    WHEN lyrics_catalog.source = 'manual' THEN 'manual'
                    ELSE excluded.source
                END,
                updated_at_utc = excluded.updated_at_utc
            """,
            (title_key, korean, effective_english, sequence, lyrics, source, now, now),
        )
        conn.commit()
