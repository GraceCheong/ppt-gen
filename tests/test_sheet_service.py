"""sheet_service 단위 테스트 — 임시 DB 사용."""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def _patch_db(tmp_path, monkeypatch):
    """모든 테스트에서 임시 DB와 임시 파일 저장소를 사용."""
    db = str(tmp_path / "test.db")
    sheet_dir = str(tmp_path / "sheet_drive" / "files")

    import server.app.services.sheet_service as svc
    import server.app.services.db as db_mod
    import server.app.config as cfg

    monkeypatch.setattr(svc, "history_db_path", lambda: db)
    monkeypatch.setattr(db_mod, "history_db_path", lambda: db)
    monkeypatch.setattr(svc, "SHEET_DRIVE_DIR", sheet_dir)
    monkeypatch.setattr(cfg, "SHEET_DRIVE_DIR", sheet_dir)
    monkeypatch.setattr(svc, "SUPER_USERS", frozenset(["superuser"]))
    monkeypatch.setattr(cfg, "SUPER_USERS", frozenset(["superuser"]))

    db_mod.init_history_db()


# ── format_key ────────────────────────────────────────────────────────────────

def test_format_key_major():
    from server.app.services.sheet_service import format_key
    assert format_key("C", "major") == "C"


def test_format_key_minor():
    from server.app.services.sheet_service import format_key
    assert format_key("B", "minor") == "Bm"


def test_format_key_sharp_minor():
    from server.app.services.sheet_service import format_key
    assert format_key("F#", "minor") == "F#m"


def test_format_key_eb_minor():
    from server.app.services.sheet_service import format_key
    assert format_key("Eb", "minor") == "Ebm"


def test_format_key_d_major():
    from server.app.services.sheet_service import format_key
    assert format_key("D", "major") == "D"


# ── normalize_title ────────────────────────────────────────────────────────────

def test_normalize_title_basic():
    from server.app.services.sheet_service import normalize_title
    assert normalize_title("  주의 은혜라  ") == "주의 은혜라"


def test_normalize_title_lowercase():
    from server.app.services.sheet_service import normalize_title
    assert normalize_title("Amazing Grace") == "amazing grace"


def test_normalize_title_multi_space():
    from server.app.services.sheet_service import normalize_title
    assert normalize_title("주의  은혜라") == "주의 은혜라"


# ── ensure_song_exists ────────────────────────────────────────────────────────

def test_ensure_song_exists_creates_new():
    import sqlite3
    from server.app.services.sheet_service import ensure_song_exists, history_db_path
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        title_key = ensure_song_exists(conn, "주의 은혜라")
        conn.commit()
        row = conn.execute(
            "SELECT * FROM lyrics_catalog WHERE title_key=?", (title_key,)
        ).fetchone()
    assert row is not None
    assert row["source"] == "sheet_upload"
    assert row["lyrics"] == ""
    assert row["sequence"] == ""
    assert row["english_title"] == ""


def test_ensure_song_exists_returns_existing():
    import sqlite3
    from server.app.services.sheet_service import ensure_song_exists, normalize_title, history_db_path
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "INSERT INTO lyrics_catalog (title_key, display_title, english_title, sequence, lyrics, source, created_at_utc, updated_at_utc) VALUES (?, ?, '', '', '가사', 'manual', ?, ?)",
            ("주의 은혜라", "주의 은혜라", now, now),
        )
        conn.commit()
        title_key = ensure_song_exists(conn, "주의 은혜라")
        conn.commit()
        rows = conn.execute(
            "SELECT COUNT(*) FROM lyrics_catalog WHERE title_key='주의 은혜라'"
        ).fetchone()[0]
    assert title_key == "주의 은혜라"
    assert rows == 1  # 중복 생성 없음


# ── upload ────────────────────────────────────────────────────────────────────

def _make_pdf_bytes() -> bytes:
    return b"%PDF-1.4 test content"


def test_upload_no_conflict(tmp_path):
    from server.app.services.sheet_service import upload_sheet, get_sheet
    result = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    assert result.get("conflict") is None
    assert result["status"] == "active"
    assert result["key_root"] == "C"
    sheet = get_sheet(result["id"])
    assert sheet is not None
    assert sheet["status"] == "active"


def test_upload_conflict_returns_conflict_flag():
    from server.app.services.sheet_service import upload_sheet
    upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    result = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test2.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    assert result.get("conflict") is True


def test_upload_on_conflict_replace():
    from server.app.services.sheet_service import upload_sheet, get_sheet
    first = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="v1.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    second = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="v2.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="replace",
    )
    old = get_sheet(first["id"])
    new = get_sheet(second["id"])
    assert old["status"] == "deleted"
    assert new["status"] == "active"
    assert new["version"] == 1


def test_upload_on_conflict_version():
    from server.app.services.sheet_service import upload_sheet, get_sheet
    first = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="v1.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    second = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="v2.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="version",
    )
    old = get_sheet(first["id"])
    new = get_sheet(second["id"])
    assert old["status"] == "active"
    assert new["status"] == "active"
    assert new["version"] == 2


# ── delete / restore ──────────────────────────────────────────────────────────

def test_delete_sets_status_and_records_history():
    import sqlite3
    from server.app.services.sheet_service import upload_sheet, delete_sheet, get_sheet, history_db_path
    sheet = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    delete_sheet(sheet["id"], deleted_by="user1")
    updated = get_sheet(sheet["id"])
    assert updated["status"] == "deleted"
    assert updated["deleted_by"] == "user1"

    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sheet_file_deletions WHERE file_id=?", (sheet["id"],)
        ).fetchone()
    assert row is not None
    assert row["deletion_type"] == "trash"


def test_restore_sets_status_active():
    from server.app.services.sheet_service import upload_sheet, delete_sheet, restore_sheet, get_sheet
    sheet = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    delete_sheet(sheet["id"], deleted_by="user1")
    result = restore_sheet(sheet["id"])
    assert result.get("conflict") is None
    updated = get_sheet(sheet["id"])
    assert updated["status"] == "active"


# ── permanent_delete ──────────────────────────────────────────────────────────

def test_permanent_delete_super_only():
    from server.app.services.sheet_service import upload_sheet, permanent_delete_sheet
    sheet = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    with pytest.raises(PermissionError):
        permanent_delete_sheet(sheet["id"], by_user="normaluser")


def test_permanent_delete_super_succeeds():
    import sqlite3
    from server.app.services.sheet_service import upload_sheet, permanent_delete_sheet, get_sheet, history_db_path
    sheet = upload_sheet(
        display_title="주의 은혜라",
        key_root="C",
        key_mode="major",
        page_number=1,
        page_count=1,
        folder_id=None,
        file_bytes=_make_pdf_bytes(),
        original_filename="test.pdf",
        mime_type="application/pdf",
        uploaded_by="user1",
        on_conflict="error",
    )
    permanent_delete_sheet(sheet["id"], by_user="superuser")
    assert get_sheet(sheet["id"]) is None

    with sqlite3.connect(history_db_path()) as conn:
        row = conn.execute(
            "SELECT deletion_type FROM sheet_file_deletions WHERE file_id=? AND deletion_type='purge'",
            (sheet["id"],),
        ).fetchone()
    assert row is not None


# ── is_super ──────────────────────────────────────────────────────────────────

def test_is_super_true():
    from server.app.services.sheet_service import is_super
    assert is_super("superuser") is True


def test_is_super_false():
    from server.app.services.sheet_service import is_super
    assert is_super("normaluser") is False
