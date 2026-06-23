"""auth_service 단위 테스트 — 임시 DB 사용."""
import sys
import os
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def _patch_db(tmp_path, monkeypatch):
    """모든 테스트에서 임시 DB를 사용하도록 패치."""
    db = str(tmp_path / "test.db")
    import server.app.services.auth_service as svc
    import server.app.services.db as db_mod
    monkeypatch.setattr(svc, "history_db_path", lambda: db)
    monkeypatch.setattr(db_mod, "history_db_path", lambda: db)
    db_mod.init_history_db()


# ── 비밀번호 해싱 ──────────────────────────────────────────────────────────────

def test_password_round_trip():
    from server.app.services.auth_service import hash_password, verify_password
    hashed = hash_password("testpass1")
    assert verify_password("testpass1", hashed) is True


def test_wrong_password_returns_false():
    from server.app.services.auth_service import hash_password, verify_password
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_invalid_hash_returns_false():
    from server.app.services.auth_service import verify_password
    assert verify_password("pw", "not-a-valid-hash") is False


# ── 사용자 CRUD ────────────────────────────────────────────────────────────────

def test_create_and_get_user():
    from server.app.services.auth_service import create_user, get_user
    create_user("testuser", "테스트교회", "테스트닉네임", "password1")
    user = get_user("testuser")
    assert user is not None
    assert user["id"] == "testuser"
    assert user["church"] == "테스트교회"
    assert user["nickname"] == "테스트닉네임"
    assert "password" not in user  # 원문 비밀번호 미포함


def test_get_nonexistent_user_returns_none():
    from server.app.services.auth_service import get_user
    assert get_user("nobody") is None


def test_user_id_exists_true():
    from server.app.services.auth_service import create_user, user_id_exists
    create_user("exists_user", "교회", "닉네임", "pw12345678")
    assert user_id_exists("exists_user") is True


def test_user_id_exists_false():
    from server.app.services.auth_service import user_id_exists
    assert user_id_exists("no_such_user") is False


# ── 세션 ──────────────────────────────────────────────────────────────────────

def test_create_and_get_session():
    from server.app.services.auth_service import create_user, create_session, get_session_user
    create_user("sess_user", "교회", "닉네임", "pw12345678")
    token = create_session("sess_user")
    assert isinstance(token, str) and len(token) > 10
    user = get_session_user(token)
    assert user is not None
    assert user["id"] == "sess_user"


def test_get_session_wrong_token_returns_none():
    from server.app.services.auth_service import get_session_user
    assert get_session_user("completely-wrong-token") is None


def test_delete_session():
    from server.app.services.auth_service import create_user, create_session, delete_session, get_session_user
    create_user("del_user", "교회", "닉네임", "pw12345678")
    token = create_session("del_user")
    delete_session(token)
    assert get_session_user(token) is None


def test_expired_session_returns_none():
    """만료된 세션은 None 반환."""
    import sqlite3
    from server.app.services.auth_service import create_user, create_session, get_session_user, history_db_path, _hash_token
    create_user("exp_user", "교회", "닉네임", "pw12345678")
    token = create_session("exp_user")
    token_hash = _hash_token(token)

    # expires_at을 과거로 조작
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute("UPDATE auth_sessions SET expires_at=? WHERE token_hash=?", (past, token_hash))
        conn.commit()

    assert get_session_user(token) is None


# ── 만료 세션 정리 ─────────────────────────────────────────────────────────────

def test_cleanup_expired_sessions():
    import sqlite3
    from server.app.services.auth_service import (
        create_user, create_session, cleanup_expired_sessions, history_db_path, _hash_token
    )
    create_user("cleanup_user", "교회", "닉네임", "pw12345678")
    token = create_session("cleanup_user")
    token_hash = _hash_token(token)

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute("UPDATE auth_sessions SET expires_at=? WHERE token_hash=?", (past, token_hash))
        conn.commit()

    removed = cleanup_expired_sessions()
    assert removed >= 1

    with sqlite3.connect(history_db_path()) as conn:
        row = conn.execute("SELECT 1 FROM auth_sessions WHERE token_hash=?", (token_hash,)).fetchone()
    assert row is None


def test_cleanup_keeps_valid_sessions():
    from server.app.services.auth_service import create_user, create_session, cleanup_expired_sessions, get_session_user
    create_user("valid_user", "교회", "닉네임", "pw12345678")
    token = create_session("valid_user")

    removed = cleanup_expired_sessions()
    assert removed == 0
    assert get_session_user(token) is not None


# ── 전체 흐름 ─────────────────────────────────────────────────────────────────

def test_full_auth_flow():
    """회원가입 → 로그인 검증 → 세션 발급 → 조회 → 로그아웃."""
    from server.app.services.auth_service import (
        create_user, get_user, verify_password,
        create_session, get_session_user, delete_session,
    )
    create_user("flow_user", "흐름교회", "흐름닉", "securepass!")
    user = get_user("flow_user")
    assert verify_password("securepass!", user["password_hash"])

    token = create_session("flow_user")
    sess = get_session_user(token)
    assert sess["church"] == "흐름교회"

    delete_session(token)
    assert get_session_user(token) is None
