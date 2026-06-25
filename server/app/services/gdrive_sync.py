"""Google Drive 양방향 동기화 서비스.

동작 방식:
  - Drive → 로컬: Drive 폴더의 파일을 SHEET_DRIVE_DIR에 다운로드 후 sheet_files DB에 자동 등록.
  - 로컬 → Drive: sheet_files 중 drive_file_id가 없는 파일을 Drive에 업로드 후 DB 갱신.
  - drive_file_id, drive_web_view_link는 sheet_files 테이블에 저장 (JSON 인덱스 미사용).
"""
from __future__ import annotations

import hashlib
import io
import logging
import mimetypes
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    _GOOGLE_AVAILABLE = True
except Exception as _google_import_err:
    import logging as _log
    _log.getLogger("ppt_gen.gdrive").warning("gdrive: google 패키지 import 실패: %s", _google_import_err)
    Credentials = None  # type: ignore[assignment,misc]
    build = None  # type: ignore[assignment]
    MediaFileUpload = None  # type: ignore[assignment]
    MediaIoBaseDownload = None  # type: ignore[assignment]
    InstalledAppFlow = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    _GOOGLE_AVAILABLE = False

from server.app.config import (
    GDRIVE_AUTH_MODE,
    GDRIVE_FOLDER_ID,
    GDRIVE_OAUTH_CLIENT_JSON,
    GDRIVE_OAUTH_TOKEN_PATH,
    GDRIVE_SYNC_ENABLED,
    SHEET_DRIVE_DIR,
)
from server.app.services.db import history_db_path

logger = logging.getLogger("ppt_gen.gdrive")

SCOPES = ["https://www.googleapis.com/auth/drive"]
_SKIP_NAMES = {".gdrive_oauth_token.json"}

# Drive Google Apps 형식은 다운로드 불가 — 건너뜀
_GDRIVE_NATIVE_PREFIX = "application/vnd.google-apps"

# 파일명 파싱: 제목 ({KEY}) {n}p INFO (k)
_KEY_IN_PARENS_RE = re.compile(
    r"\((C#|Db|D#|Eb|F#|Gb|G#|Ab|A#|Bb|[CDEFGAB])m?\)",
    re.IGNORECASE,
)
_PAGE_NP_RE = re.compile(r"\b(\d+)p\b", re.IGNORECASE)
_PAGE_DASH_RE = re.compile(r"\s*-\s*(\d+)\s*$")
_VER_IN_PARENS_RE = re.compile(r"\((\d+)\)\s*$")

_KEY_CANONICAL = {
    "c": "C", "c#": "C#", "db": "Db", "d": "D", "d#": "D#", "eb": "Eb",
    "e": "E", "f": "F", "f#": "F#", "gb": "Gb", "g": "G", "g#": "G#",
    "ab": "Ab", "a": "A", "a#": "A#", "bb": "Bb", "b": "B",
}


# ── 인증 ──────────────────────────────────────────────────────────────────────

def _extract_folder_id(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if "folders/" in text:
        return text.split("folders/")[-1].split("?")[0].split("/")[0]
    if "id=" in text:
        return text.split("id=")[-1].split("&")[0]
    return text


def _build_service():
    if not _GOOGLE_AVAILABLE:
        logger.warning("gdrive: google-api 패키지가 설치되지 않았습니다.")
        return None
    client_json = GDRIVE_OAUTH_CLIENT_JSON
    if not client_json or not os.path.exists(client_json):
        logger.error("gdrive: OAuth 클라이언트 JSON 경로가 없습니다. GDRIVE_OAUTH_CLIENT_JSON을 설정하세요.")
        return None
    token_path = GDRIVE_OAUTH_TOKEN_PATH
    os.makedirs(os.path.dirname(token_path), exist_ok=True)

    creds: Optional[Credentials] = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("gdrive: 토큰 갱신 실패 — %s", e)
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(client_json, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error("gdrive: OAuth 인증 실패 — %s", e)
                return None
        try:
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            logger.warning("gdrive: 토큰 저장 실패 — %s", e)

    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ── Drive API 헬퍼 ─────────────────────────────────────────────────────────────

def _list_drive_items_recursive(service, folder_id: str) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, md5Checksum, size, parents, webViewLink)",
            pageToken=page_token,
        ).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    subfolders = [it for it in items if it.get("mimeType") == "application/vnd.google-apps.folder"]
    for folder in subfolders:
        items.extend(_list_drive_items_recursive(service, folder["id"]))
    return items


def _download_file(service, file_id: str, dest_path: str) -> None:
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(dest_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.close()


def _upload_file(service, folder_id: str, path: str, name: str) -> dict | None:
    media = MediaFileUpload(path, resumable=True)
    result = service.files().create(
        body={"name": name, "parents": [folder_id]},
        media_body=media,
        fields="id, webViewLink",
    ).execute()
    return result


def _md5(path: str) -> str | None:
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── 파일명 파싱 ────────────────────────────────────────────────────────────────

def _normalize_fname(name: str) -> str:
    return unicodedata.normalize("NFC", name)


def _parse_sheet_filename(filename: str) -> tuple[str, str | None, str | None, int, str]:
    """파일명에서 (clean_title, key_root, key_mode, page_number, info) 추출.

    포맷: 제목 ({KEY}) {n}p INFO (k)
    - KEY 없으면 key_root=None, key_mode=None
    - 콜라보 제목 (title1+title2) 는 clean_title에 그대로 보존
    """
    base = os.path.splitext(filename)[0].strip()
    base = _normalize_fname(base)

    key_match = _KEY_IN_PARENS_RE.search(base)
    if not key_match:
        return base, None, None, 1, ""

    raw_key = key_match.group(1)
    clean_title = base[: key_match.start()].strip().rstrip("(").strip()
    remainder = base[key_match.end() :].strip()

    # key_root, key_mode 정규화
    is_minor = raw_key.lower().endswith("m") and len(raw_key) > 1
    root_raw = raw_key[:-1] if is_minor else raw_key
    key_root = _KEY_CANONICAL.get(root_raw.lower(), root_raw[0].upper() + root_raw[1:].lower() if len(root_raw) > 1 else root_raw.upper())
    key_mode = "minor" if is_minor else "major"

    # 페이지 번호: Np 또는 - N
    page_number = 1
    page_match = _PAGE_NP_RE.search(remainder)
    if page_match:
        page_number = int(page_match.group(1))
        remainder = (remainder[: page_match.start()] + remainder[page_match.end() :]).strip()
    else:
        dash_match = _PAGE_DASH_RE.search(remainder)
        if dash_match:
            page_number = int(dash_match.group(1))
            remainder = remainder[: dash_match.start()].strip()

    # 버전 번호 (숫자만 있는 괄호) 제거
    ver_match = _VER_IN_PARENS_RE.search(remainder)
    if ver_match:
        remainder = remainder[: ver_match.start()].strip()

    info = remainder.strip()
    return clean_title or base, key_root, key_mode, page_number, info


# ── DB 연동 ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _register_file_in_db(
    storage_path: str,
    original_filename: str,
    mime_type: str,
    drive_file_id: str,
    drive_web_view_link: str | None,
    uploaded_by: str = "드라이브",
) -> str | None:
    """Drive에서 다운로드한 파일을 sheet_files DB에 등록. 이미 있으면 drive_file_id만 갱신. file_id 반환."""
    from server.app.services.sheet_service import ensure_song_exists, normalize_title

    if not os.path.exists(storage_path):
        return None

    with open(storage_path, "rb") as f:
        data = f.read()
    sha = _sha256(data)

    conn = sqlite3.connect(history_db_path())
    conn.row_factory = sqlite3.Row
    try:
        # 이미 drive_file_id로 등록된 경우
        existing = conn.execute(
            "SELECT id FROM sheet_files WHERE drive_file_id=?", (drive_file_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE sheet_files SET drive_web_view_link=?, updated_at=? WHERE drive_file_id=?",
                (drive_web_view_link, _now_iso(), drive_file_id),
            )
            conn.commit()
            return existing["id"]

        # sha256로 중복 확인
        existing = conn.execute(
            "SELECT id FROM sheet_files WHERE sha256=? AND status='active'", (sha,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE sheet_files SET drive_file_id=?, drive_web_view_link=?, updated_at=? WHERE id=?",
                (drive_file_id, drive_web_view_link, _now_iso(), existing["id"]),
            )
            conn.commit()
            return existing["id"]

        # 신규 등록
        clean_title, key_root, key_mode, page_number, info = _parse_sheet_filename(original_filename)
        display_title = f"{clean_title} {info}".strip() if info else clean_title
        title_key = ensure_song_exists(conn, clean_title)  # 콜라보 포함 clean_title로 song_title_key 결정
        ext = Path(original_filename).suffix.lstrip(".").lower() or "bin"
        stored_filename = os.path.basename(storage_path)
        now = _now_iso()
        file_id = str(uuid4())

        # 기존 active 중 같은 title_key/key_root/key_mode/page_number인 것의 최대 version 확인
        ver_row = conn.execute(
            "SELECT MAX(version) FROM sheet_files WHERE song_title_key=? AND key_root=? AND key_mode=? "
            "AND page_number=? AND status='active'",
            (title_key, key_root or "", key_mode or "", page_number),
        ).fetchone()
        version = (ver_row[0] or 0) + 1

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
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?,
                    'active', ?, ?, ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                file_id, title_key, display_title, normalize_title(display_title),
                key_root or "", key_mode or "", page_number, version,
                original_filename, stored_filename, storage_path,
                mime_type, ext, len(data), sha,
                uploaded_by, now, now,
                drive_file_id, drive_web_view_link,
            ),
        )
        conn.commit()
        logger.info("gdrive: DB 등록 — %s (id=%s)", original_filename, file_id)
        return file_id
    finally:
        conn.close()


def _get_unsynced_files() -> list[dict]:
    """drive_file_id가 없는 active sheet_files 목록 반환."""
    conn = sqlite3.connect(history_db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, storage_path, original_filename, mime_type "
            "FROM sheet_files WHERE status='active' AND (drive_file_id IS NULL OR drive_file_id='')"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _update_drive_id(file_id: str, drive_file_id: str, drive_web_view_link: str | None) -> None:
    conn = sqlite3.connect(history_db_path())
    try:
        conn.execute(
            "UPDATE sheet_files SET drive_file_id=?, drive_web_view_link=?, updated_at=? WHERE id=?",
            (drive_file_id, drive_web_view_link, _now_iso(), file_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── 공개 API ───────────────────────────────────────────────────────────────────

def sync_status() -> dict:
    """동기화 가능 여부 및 설정 상태 반환."""
    return {
        "enabled": GDRIVE_SYNC_ENABLED,
        "configured": bool(GDRIVE_FOLDER_ID and GDRIVE_OAUTH_CLIENT_JSON),
        "google_libs": _GOOGLE_AVAILABLE,
        "folder_id": _extract_folder_id(GDRIVE_FOLDER_ID),
    }


def rename_drive_file(drive_file_id: str, new_display_title: str, key_root: str, key_mode: str, extension: str) -> bool:
    """Drive 파일 이름을 '{제목}_{key}.{ext}' 형식으로 변경. 성공 여부 반환."""
    if not GDRIVE_SYNC_ENABLED:
        return False
    service = _build_service()
    if not service:
        return False
    key_str = (key_root + "m") if key_mode == "minor" else key_root
    ext = ("." + extension) if extension and not extension.startswith(".") else (extension or "")
    new_name = f"{new_display_title}_{key_str}{ext}"
    try:
        service.files().update(
            fileId=drive_file_id,
            body={"name": new_name},
            fields="id, name",
        ).execute()
        logger.info("gdrive: 파일 이름 변경 — %s → %s", drive_file_id, new_name)
        return True
    except Exception as e:
        logger.error("gdrive: 파일 이름 변경 실패 %s — %s", drive_file_id, e)
        return False


def upload_to_drive(file_id: str, storage_path: str, filename: str) -> dict | None:
    """단일 파일을 Drive에 업로드하고 drive_file_id를 DB에 저장. 결과 dict 반환."""
    if not GDRIVE_SYNC_ENABLED:
        return None
    folder_id = _extract_folder_id(GDRIVE_FOLDER_ID)
    if not folder_id:
        return None
    service = _build_service()
    if not service:
        return None
    try:
        mime, _ = mimetypes.guess_type(storage_path)
        result = _upload_file(service, folder_id, storage_path, filename)
        if result:
            drive_id = result.get("id")
            link = result.get("webViewLink")
            _update_drive_id(file_id, drive_id, link)
            logger.info("gdrive: 업로드 완료 — %s (drive_id=%s)", filename, drive_id)
            return result
    except Exception as e:
        logger.error("gdrive: 업로드 실패 %s — %s", filename, e)
    return None


def sync_once() -> dict:
    """Drive ↔ 로컬 양방향 동기화 1회 실행.

    반환: {"downloaded": int, "uploaded": int, "registered": int, "errors": list[str]}
    """
    result = {"downloaded": 0, "uploaded": 0, "registered": 0, "errors": []}

    if not GDRIVE_SYNC_ENABLED:
        result["errors"].append("GDRIVE_SYNC_ENABLED가 비활성화 상태입니다.")
        return result

    folder_id = _extract_folder_id(GDRIVE_FOLDER_ID)
    if not folder_id:
        result["errors"].append("GDRIVE_FOLDER_ID가 설정되지 않았습니다.")
        return result

    service = _build_service()
    if not service:
        result["errors"].append("Google Drive 인증에 실패했습니다.")
        return result

    os.makedirs(SHEET_DRIVE_DIR, exist_ok=True)

    # ── 1. Drive → 로컬 ────────────────────────────────────────────────────────
    try:
        drive_items = _list_drive_items_recursive(service, folder_id)
    except Exception as e:
        result["errors"].append(f"Drive 목록 조회 실패: {e}")
        return result

    # Drive MD5 집합 (중복 방지용)
    drive_md5_set = {it.get("md5Checksum") for it in drive_items if it.get("md5Checksum")}

    # 로컬 파일 MD5 집합
    local_md5s: dict[str, str] = {}
    for fname in os.listdir(SHEET_DRIVE_DIR):
        if fname in _SKIP_NAMES:
            continue
        fpath = os.path.join(SHEET_DRIVE_DIR, fname)
        if os.path.isfile(fpath):
            md5 = _md5(fpath)
            if md5:
                local_md5s[md5] = fpath

    for item in drive_items:
        mime = item.get("mimeType", "")
        if mime.startswith(_GDRIVE_NATIVE_PREFIX):
            continue  # Google Docs 등 변환 불필요
        drive_id = item.get("id")
        drive_name = _normalize_fname(item.get("name", ""))
        drive_md5 = item.get("md5Checksum")

        # 이미 로컬에 있는 파일인지 확인
        if drive_md5 and drive_md5 in local_md5s:
            # 로컬에 있으면 drive_file_id만 업데이트
            local_path = local_md5s[drive_md5]
            local_fname = os.path.basename(local_path)
            # DB에서 stored_filename으로 검색
            conn = sqlite3.connect(history_db_path())
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT id, drive_file_id FROM sheet_files WHERE stored_filename=? AND status='active'",
                    (local_fname,),
                ).fetchone()
                if row and not row["drive_file_id"]:
                    conn.execute(
                        "UPDATE sheet_files SET drive_file_id=?, drive_web_view_link=?, updated_at=? WHERE id=?",
                        (drive_id, item.get("webViewLink"), _now_iso(), row["id"]),
                    )
                    conn.commit()
            finally:
                conn.close()
            continue

        # 다운로드
        ext = Path(drive_name).suffix or ""
        dest_name = f"{uuid4()}{ext}"
        dest_path = os.path.join(SHEET_DRIVE_DIR, dest_name)
        try:
            _download_file(service, drive_id, dest_path)
            result["downloaded"] += 1
            # DB 등록
            detected_mime = mime or (mimetypes.guess_type(drive_name)[0] or "application/octet-stream")
            registered_id = _register_file_in_db(
                storage_path=dest_path,
                original_filename=drive_name,
                mime_type=detected_mime,
                drive_file_id=drive_id,
                drive_web_view_link=item.get("webViewLink"),
            )
            if registered_id:
                result["registered"] += 1
                local_md5_new = _md5(dest_path)
                if local_md5_new:
                    local_md5s[local_md5_new] = dest_path
        except Exception as e:
            logger.error("gdrive: 다운로드 실패 %s — %s", drive_name, e)
            result["errors"].append(f"다운로드 실패: {drive_name} — {e}")

    # ── 2. 로컬 → Drive (drive_file_id 없는 파일) ─────────────────────────────
    unsynced = _get_unsynced_files()
    for row in unsynced:
        path = row["storage_path"]
        if not os.path.exists(path):
            continue
        fname = row["original_filename"] or os.path.basename(path)
        local_md5 = _md5(path)
        if local_md5 and local_md5 in drive_md5_set:
            continue  # 이미 Drive에 있는 파일
        try:
            up_result = _upload_file(service, folder_id, path, fname)
            if up_result:
                _update_drive_id(row["id"], up_result["id"], up_result.get("webViewLink"))
                drive_md5_set.add(local_md5 or "")
                result["uploaded"] += 1
        except Exception as e:
            logger.error("gdrive: 업로드 실패 %s — %s", fname, e)
            result["errors"].append(f"업로드 실패: {fname} — {e}")

    logger.info(
        "gdrive: sync 완료 — 다운로드=%d 업로드=%d DB등록=%d 오류=%d",
        result["downloaded"], result["uploaded"], result["registered"], len(result["errors"]),
    )
    return result
