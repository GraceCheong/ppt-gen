"""악보 드라이브 서비스 — 업로드/검색/다운로드/삭제/복구."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from server.app.config import SHEET_DRIVE_DIR, SHEET_THUMB_DIR, SUPER_USERS
from server.app.services.db import history_db_path


# ── 헬퍼 ────────────────────────────────────────────────────────────────────────

def is_super(user_id: str) -> bool:
    return user_id in SUPER_USERS


def _generate_pdf_thumb(file_id: str, storage_path: str) -> None:
    try:
        import fitz  # pymupdf
        os.makedirs(SHEET_THUMB_DIR, exist_ok=True)
        doc = fitz.open(storage_path)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        pix.save(os.path.join(SHEET_THUMB_DIR, f"{file_id}.jpg"))
        doc.close()
    except Exception:
        pass


def get_thumb_path(file_id: str) -> str | None:
    path = os.path.join(SHEET_THUMB_DIR, f"{file_id}.jpg")
    return path if os.path.exists(path) else None


def format_key(key_root: str, key_mode: str) -> str:
    """major → 루트만, minor → 루트+'m'."""
    if key_mode == "minor":
        return key_root + "m"
    return key_root


def normalize_title(title: str) -> str:
    """NFC 정규화, strip, 연속공백 축약, 소문자."""
    normalized = unicodedata.normalize("NFC", title)
    normalized = normalized.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── 곡 DB 자동 연동 ────────────────────────────────────────────────────────────

def ensure_song_exists(conn: sqlite3.Connection, display_title: str) -> str:
    """lyrics_catalog에서 title_key를 찾거나 없으면 새 행을 INSERT. title_key 반환."""
    title_key = normalize_title(display_title)
    row = conn.execute(
        "SELECT title_key FROM lyrics_catalog WHERE title_key=?", (title_key,)
    ).fetchone()
    if row:
        return row[0]
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO lyrics_catalog
            (title_key, display_title, english_title, sequence, lyrics, source,
             created_at_utc, updated_at_utc)
        VALUES (?, ?, '', '', '', 'sheet_upload', ?, ?)
        """,
        (title_key, display_title, now, now),
    )
    return title_key


# ── 핵심 서비스 함수 ─────────────────────────────────────────────────────────────

def search_sheets(
    q: str = "",
    key_root: str | None = None,
    key_mode: str | None = None,
    folder_id: str | None = None,
    extension: str | None = None,
    is_event_only: bool | None = None,
    has_key: bool | None = None,
    uploaded_by: str | None = None,
    sort_by: str = "uploaded_at",
    sort_dir: str = "desc",
    status: str = "active",
) -> list[dict]:
    params: list = []
    clauses: list[str] = ["sf.status = ?"]
    params.append(status)

    if q:
        norm_q = normalize_title(q)
        clauses.append(
            "(sf.normalized_title LIKE ? OR sf.display_title LIKE ? OR sf.original_filename LIKE ?)"
        )
        like = f"%{norm_q}%"
        params.extend([like, f"%{q}%", f"%{q}%"])

    if key_root is not None:
        clauses.append("sf.key_root = ?")
        params.append(key_root)

    if key_mode is not None:
        clauses.append("sf.key_mode = ?")
        params.append(key_mode)

    if folder_id is not None:
        clauses.append("sf.folder_id = ?")
        params.append(folder_id)

    if extension is not None:
        clauses.append("LOWER(sf.extension) = ?")
        params.append(extension.lower().lstrip("."))

    if is_event_only is not None:
        clauses.append("sf.is_event_only = ?")
        params.append(1 if is_event_only else 0)

    if has_key is True:
        clauses.append("sf.key_root != ''")
    elif has_key is False:
        clauses.append("sf.key_root = ''")

    if uploaded_by is not None:
        clauses.append("sf.uploaded_by = ?")
        params.append(uploaded_by)

    allowed_sorts = {
        "display_title", "key_root", "page_number", "version",
        "extension", "uploaded_at", "uploaded_by",
    }
    col = sort_by if sort_by in allowed_sorts else "uploaded_at"
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    where = " AND ".join(clauses)
    sql = f"SELECT * FROM sheet_files sf WHERE {where} ORDER BY sf.{col} {direction}"

    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [_sheet_row_to_dict(r) for r in rows]


def _renumber_versions(conn: sqlite3.Connection, normalized_title: str, key_root: str, key_mode: str, page_number: int) -> None:
    """같은 normalized_title+key+page의 active 파일 버전을 1부터 연속 재번호."""
    rows = conn.execute(
        "SELECT id FROM sheet_files WHERE normalized_title=? AND key_root=? AND key_mode=? AND page_number=? AND status='active' ORDER BY version",
        (normalized_title, key_root, key_mode, page_number),
    ).fetchall()
    for new_ver, row in enumerate(rows, 1):
        conn.execute("UPDATE sheet_files SET version=? WHERE id=?", (new_ver, row[0]))


def _sheet_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d['is_event_only'] = bool(d.get('is_event_only', 0))
    return d


def upload_sheet(
    display_title: str,
    key_root: str,
    key_mode: str,
    page_number: int,
    page_count: int | None,
    folder_id: str | None,
    file_bytes: bytes,
    original_filename: str,
    mime_type: str,
    uploaded_by: str,
    on_conflict: str = "error",
) -> dict:
    """
    저장 경로: SHEET_DRIVE_DIR / {uuid}.{ext}
    on_conflict: "error" | "replace" | "version"
    """
    os.makedirs(SHEET_DRIVE_DIR, exist_ok=True)

    ext = Path(original_filename).suffix.lstrip(".")
    if not ext:
        ext = "bin"

    sha256_val = _sha256(file_bytes)
    now = _now_iso()

    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        title_key = ensure_song_exists(conn, display_title)
        normalized = normalize_title(display_title)

        # 충돌 확인: 동일 곡/key_root/key_mode/page_number의 active 파일
        existing = conn.execute(
            """
            SELECT *
            FROM sheet_files
            WHERE song_title_key=? AND key_root=? AND key_mode=? AND page_number=? AND status='active'
            ORDER BY version DESC LIMIT 1
            """,
            (title_key, key_root, key_mode, page_number),
        ).fetchone()

        if existing:
            if on_conflict == "error":
                return {
                    "conflict": True,
                    "existing_id": existing["id"],
                    "title_key": title_key,
                    "key_root": key_root,
                    "key_mode": key_mode,
                    "page_number": page_number,
                }
            elif on_conflict == "replace":
                _soft_delete_file(conn, dict(existing), deleted_by=uploaded_by, deletion_type="replace")
                version = 1
                replaced_file_id = existing["id"]
            else:  # version
                version = existing["version"] + 1
                replaced_file_id = None
        else:
            version = 1
            replaced_file_id = None

        file_id = str(uuid4())
        stored_filename = f"{file_id}.{ext}"
        storage_path = os.path.join(SHEET_DRIVE_DIR, stored_filename)

        # 파일 저장
        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        conn.execute(
            """
            INSERT INTO sheet_files
                (id, folder_id, song_title_key, display_title, normalized_title,
                 key_root, key_mode, page_number, page_count, version,
                 original_filename, stored_filename, storage_path,
                 mime_type, extension, size_bytes, sha256,
                 status, uploaded_by, uploaded_at, updated_at,
                 deleted_by, deleted_at, replaced_file_id,
                 drive_file_id, drive_web_view_link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, NULL, NULL, ?, NULL, NULL)
            """,
            (
                file_id, folder_id, title_key, display_title, normalized,
                key_root, key_mode, page_number, page_count, version,
                original_filename, stored_filename, storage_path,
                mime_type, ext, len(file_bytes), sha256_val,
                uploaded_by, now, now,
                replaced_file_id,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM sheet_files WHERE id=?", (file_id,)
        ).fetchone()
        result = dict(row)

    # PDF 썸네일 생성 (비동기 — 실패해도 업로드 결과는 반환)
    if ext.lower() == "pdf":
        import threading
        threading.Thread(
            target=_generate_pdf_thumb,
            args=(file_id, storage_path),
            daemon=True,
        ).start()

    # Drive 동기화 (비동기 fire-and-forget — 실패해도 업로드 결과는 반환)
    from server.app.config import GDRIVE_SYNC_ENABLED
    if GDRIVE_SYNC_ENABLED:
        import threading
        from server.app.services.gdrive_sync import upload_to_drive
        threading.Thread(
            target=upload_to_drive,
            args=(file_id, storage_path, original_filename),
            daemon=True,
        ).start()

    return result


def get_sheet(file_id: str) -> dict | None:
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_files WHERE id=?", (file_id,)
        ).fetchone()
    return _sheet_row_to_dict(row) if row else None


def download_sheet(file_id: str) -> tuple[bytes, str, str]:
    """(file_bytes, original_filename, mime_type) 반환."""
    sheet = get_sheet(file_id)
    if not sheet:
        raise FileNotFoundError(f"악보를 찾을 수 없습니다: {file_id}")
    with open(sheet["storage_path"], "rb") as f:
        data = f.read()
    return data, sheet["original_filename"], sheet["mime_type"]


def update_sheet_meta(
    file_id: str,
    display_title: str | None = None,
    key_root: str | None = None,
    key_mode: str | None = None,
    page_number: int | None = None,
    page_count: int | None = None,
    is_event_only: bool | None = None,
) -> dict:
    sheet = get_sheet(file_id)
    if not sheet:
        raise FileNotFoundError(f"악보를 찾을 수 없습니다: {file_id}")
    updates: list[str] = []
    params: list = []
    if display_title is not None:
        updates.append("display_title = ?")
        params.append(display_title.strip())
        updates.append("normalized_title = ?")
        params.append(normalize_title(display_title))
    if key_root is not None:
        updates.append("key_root = ?")
        params.append(key_root)
    if key_mode is not None:
        updates.append("key_mode = ?")
        params.append(key_mode)
    if page_number is not None:
        updates.append("page_number = ?")
        params.append(int(page_number))
    if page_count is not None:
        updates.append("page_count = ?")
        params.append(int(page_count))
    if is_event_only is not None:
        updates.append("is_event_only = ?")
        params.append(1 if is_event_only else 0)
    if not updates:
        return sheet
    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(file_id)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            f"UPDATE sheet_files SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

    updated = get_sheet(file_id)

    # 제목 또는 key가 바뀌었고 Drive와 연결된 경우 → Drive 파일 이름도 변경
    drive_file_id = sheet.get("drive_file_id")
    name_changed = (display_title is not None and display_title.strip() != sheet.get("display_title")) or \
                   (key_root is not None and key_root != sheet.get("key_root")) or \
                   (key_mode is not None and key_mode != sheet.get("key_mode"))
    if drive_file_id and name_changed:
        try:
            from server.app.config import GDRIVE_SYNC_ENABLED
            if GDRIVE_SYNC_ENABLED:
                import threading
                from server.app.services.gdrive_sync import rename_drive_file
                threading.Thread(
                    target=rename_drive_file,
                    args=(
                        drive_file_id,
                        updated.get("display_title", ""),
                        updated.get("key_root", "C"),
                        updated.get("key_mode", "major"),
                        updated.get("extension", ""),
                    ),
                    daemon=True,
                ).start()
        except Exception:
            pass  # Drive rename 실패해도 DB 수정은 이미 완료

    return updated


def _soft_delete_file(
    conn: sqlite3.Connection,
    sheet: dict,
    deleted_by: str,
    deletion_type: str,
) -> None:
    now = _now_iso()
    conn.execute(
        "UPDATE sheet_files SET status='deleted', deleted_by=?, deleted_at=?, updated_at=? WHERE id=?",
        (deleted_by, now, now, sheet["id"]),
    )
    conn.execute(
        """
        INSERT INTO sheet_file_deletions
            (file_id, filename_snapshot, title_snapshot, key_root_snapshot,
             key_mode_snapshot, page_number_snapshot, version_snapshot,
             storage_path_snapshot, deleted_by, deleted_at, deletion_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sheet["id"],
            sheet["original_filename"],
            sheet["display_title"],
            sheet["key_root"],
            sheet["key_mode"],
            sheet["page_number"],
            sheet["version"],
            sheet["storage_path"],
            deleted_by,
            now,
            deletion_type,
        ),
    )


def delete_sheet(file_id: str, deleted_by: str) -> None:
    """status='deleted', 이력 기록."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_files WHERE id=?", (file_id,)
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"악보를 찾을 수 없습니다: {file_id}")
        sheet = dict(row)
        _soft_delete_file(conn, sheet, deleted_by=deleted_by, deletion_type="trash")
        _renumber_versions(conn, sheet["normalized_title"], sheet["key_root"], sheet["key_mode"], sheet["page_number"])
        conn.commit()


def restore_sheet(file_id: str) -> dict:
    """status='active'로 복원. 충돌 시 {"conflict": True} 반환."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_files WHERE id=?", (file_id,)
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"악보를 찾을 수 없습니다: {file_id}")
        sheet = dict(row)

        # 충돌 확인
        conflict = conn.execute(
            """
            SELECT id FROM sheet_files
            WHERE song_title_key=? AND key_root=? AND key_mode=? AND page_number=?
              AND status='active' AND id != ?
            """,
            (sheet["song_title_key"], sheet["key_root"], sheet["key_mode"],
             sheet["page_number"], file_id),
        ).fetchone()

        if conflict:
            return {"conflict": True, "conflicting_id": conflict["id"]}

        now = _now_iso()
        conn.execute(
            "UPDATE sheet_files SET status='active', deleted_by=NULL, deleted_at=NULL, updated_at=? WHERE id=?",
            (now, file_id),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM sheet_files WHERE id=?", (file_id,)).fetchone()
        return _sheet_row_to_dict(row)


def permanent_delete_sheet(file_id: str, by_user: str) -> None:
    """super 전용. 실제 파일 삭제 후 DB 행 제거. 이력은 남김."""
    if not is_super(by_user):
        raise PermissionError("super 계정만 완전 삭제할 수 있습니다.")

    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_files WHERE id=?", (file_id,)
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"악보를 찾을 수 없습니다: {file_id}")
        sheet = dict(row)

        # 삭제 이력 남기기
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO sheet_file_deletions
                (file_id, filename_snapshot, title_snapshot, key_root_snapshot,
                 key_mode_snapshot, page_number_snapshot, version_snapshot,
                 storage_path_snapshot, deleted_by, deleted_at, deletion_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'purge')
            """,
            (
                sheet["id"],
                sheet["original_filename"],
                sheet["display_title"],
                sheet["key_root"],
                sheet["key_mode"],
                sheet["page_number"],
                sheet["version"],
                sheet["storage_path"],
                by_user,
                now,
            ),
        )

        # 실제 파일 삭제
        try:
            os.remove(sheet["storage_path"])
        except OSError:
            pass

        # DB 행 삭제
        conn.execute("DELETE FROM sheet_files WHERE id=?", (file_id,))
        _renumber_versions(conn, sheet["normalized_title"], sheet["key_root"], sheet["key_mode"], sheet["page_number"])
        conn.commit()


def list_trash(q: str = "") -> list[dict]:
    params: list = ["deleted"]
    clauses: list[str] = ["status = ?"]
    if q:
        norm_q = normalize_title(q)
        clauses.append(
            "(normalized_title LIKE ? OR display_title LIKE ?)"
        )
        like = f"%{norm_q}%"
        params.extend([like, f"%{q}%"])

    where = " AND ".join(clauses)
    sql = f"SELECT * FROM sheet_files WHERE {where} ORDER BY deleted_at DESC"

    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def list_folders(parent_id: str | None) -> list[dict]:
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        if parent_id is None:
            rows = conn.execute(
                "SELECT * FROM sheet_folders WHERE parent_id IS NULL AND status='active' ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sheet_folders WHERE parent_id=? AND status='active' ORDER BY name",
                (parent_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def create_folder(name: str, parent_id: str | None, created_by: str) -> dict:
    folder_id = str(uuid4())
    now = _now_iso()

    # path 계산
    if parent_id:
        with sqlite3.connect(history_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            parent = conn.execute(
                "SELECT path FROM sheet_folders WHERE id=?", (parent_id,)
            ).fetchone()
            parent_path = parent["path"] if parent else ""
    else:
        parent_path = ""

    path = f"{parent_path}/{name}".lstrip("/")

    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO sheet_folders
                (id, parent_id, name, path, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (folder_id, parent_id, name, path, created_by, now, now),
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_folders WHERE id=?", (folder_id,)
        ).fetchone()
    return dict(row)


def rename_folder(folder_id: str, name: str) -> dict:
    now = _now_iso()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "UPDATE sheet_folders SET name=?, updated_at=? WHERE id=?",
            (name, now, folder_id),
        )
        conn.commit()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_folders WHERE id=?", (folder_id,)
        ).fetchone()
    if not row:
        raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder_id}")
    return dict(row)


def _delete_folder_recursive(conn: sqlite3.Connection, folder_id: str, deleted_by: str) -> None:
    now = _now_iso()

    # 하위 파일 삭제
    files = conn.execute(
        "SELECT * FROM sheet_files WHERE folder_id=? AND status='active'",
        (folder_id,),
    ).fetchall()
    conn.row_factory = sqlite3.Row
    for file_row in files:
        conn.row_factory = sqlite3.Row
        fr = conn.execute("SELECT * FROM sheet_files WHERE id=?", (file_row[0],)).fetchone()
        if fr:
            _soft_delete_file(conn, dict(fr), deleted_by=deleted_by, deletion_type="trash")

    # 하위 폴더 재귀 삭제
    sub_folders = conn.execute(
        "SELECT id FROM sheet_folders WHERE parent_id=? AND status='active'",
        (folder_id,),
    ).fetchall()
    for (sub_id,) in sub_folders:
        _delete_folder_recursive(conn, sub_id, deleted_by)

    conn.execute(
        "UPDATE sheet_folders SET status='deleted', deleted_by=?, deleted_at=?, updated_at=? WHERE id=?",
        (deleted_by, now, now, folder_id),
    )


def delete_folder(folder_id: str, deleted_by: str) -> None:
    """하위 파일/폴더도 status='deleted' 처리."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        _delete_folder_recursive(conn, folder_id, deleted_by)
        conn.commit()


def restore_folder(folder_id: str) -> None:
    """원래 부모가 deleted면 parent_id=None(루트)으로 복구."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_folders WHERE id=?", (folder_id,)
        ).fetchone()
        if not row:
            raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {folder_id}")
        folder = dict(row)

        now = _now_iso()
        new_parent_id = folder["parent_id"]

        # 부모가 삭제된 경우 루트로 복구
        if new_parent_id:
            parent = conn.execute(
                "SELECT status FROM sheet_folders WHERE id=?", (new_parent_id,)
            ).fetchone()
            if not parent or parent["status"] != "active":
                new_parent_id = None

        conn.execute(
            "UPDATE sheet_folders SET status='active', parent_id=?, deleted_by=NULL, deleted_at=NULL, updated_at=? WHERE id=?",
            (new_parent_id, now, folder_id),
        )
        conn.commit()


def permanent_delete_folder(folder_id: str, by_user: str) -> None:
    """super 전용. 하위 포함 완전 삭제."""
    if not is_super(by_user):
        raise PermissionError("super 계정만 완전 삭제할 수 있습니다.")

    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        _permanent_delete_folder_recursive(conn, folder_id, by_user)
        conn.commit()


def _permanent_delete_folder_recursive(
    conn: sqlite3.Connection, folder_id: str, by_user: str
) -> None:
    now = _now_iso()

    # 하위 파일 완전 삭제
    files = conn.execute(
        "SELECT * FROM sheet_files WHERE folder_id=?", (folder_id,)
    ).fetchall()
    conn.row_factory = sqlite3.Row
    for file_row in files:
        fr = conn.execute("SELECT * FROM sheet_files WHERE id=?", (file_row[0],)).fetchone()
        if fr:
            sheet = dict(fr)
            conn.execute(
                """
                INSERT INTO sheet_file_deletions
                    (file_id, filename_snapshot, title_snapshot, key_root_snapshot,
                     key_mode_snapshot, page_number_snapshot, version_snapshot,
                     storage_path_snapshot, deleted_by, deleted_at, deletion_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'purge')
                """,
                (
                    sheet["id"], sheet["original_filename"], sheet["display_title"],
                    sheet["key_root"], sheet["key_mode"], sheet["page_number"],
                    sheet["version"], sheet["storage_path"], by_user, now,
                ),
            )
            try:
                os.remove(sheet["storage_path"])
            except OSError:
                pass
            conn.execute("DELETE FROM sheet_files WHERE id=?", (sheet["id"],))

    # 하위 폴더 재귀 삭제
    sub_folders = conn.execute(
        "SELECT id FROM sheet_folders WHERE parent_id=?", (folder_id,)
    ).fetchall()
    for (sub_id,) in sub_folders:
        _permanent_delete_folder_recursive(conn, sub_id, by_user)

    conn.execute("DELETE FROM sheet_folders WHERE id=?", (folder_id,))


def get_sheets_by_song(title_key: str) -> list[dict]:
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM sheet_files WHERE song_title_key=? AND status='active' ORDER BY page_number, version",
            (title_key,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_sheets_by_titles(title_keys: list[str]) -> dict[str, list[dict]]:
    """{title_key: [{key_root, key_mode, key_display, page_number, ...}]}"""
    if not title_keys:
        return {}

    placeholders = ",".join("?" * len(title_keys))
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM sheet_files WHERE song_title_key IN ({placeholders}) AND status='active' ORDER BY page_number, version",
            title_keys,
        ).fetchall()

    result: dict[str, list[dict]] = {k: [] for k in title_keys}
    for row in rows:
        d = dict(row)
        d["key_display"] = format_key(d["key_root"], d["key_mode"])
        result[d["song_title_key"]].append(d)
    return result


def download_sheets_by_song_key(
    title_key: str, key_root: str, key_mode: str
) -> list[tuple[bytes, str, str]]:
    """해당 곡/key의 active 악보를 page_number 순으로 (bytes, filename, mime) 목록 반환."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM sheet_files
            WHERE song_title_key=? AND key_root=? AND key_mode=? AND status='active'
            ORDER BY page_number, version
            """,
            (title_key, key_root, key_mode),
        ).fetchall()

    result: list[tuple[bytes, str, str]] = []
    for row in rows:
        sheet = dict(row)
        with open(sheet["storage_path"], "rb") as f:
            data = f.read()
        result.append((data, sheet["original_filename"], sheet["mime_type"]))
    return result
