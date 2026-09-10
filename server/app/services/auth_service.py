"""인증 서비스 — 비밀번호 해시, 세션 토큰 관리."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

from server.app.config import ADMIN_USERS, PASSWORD_RESET_TTL_HOURS
from server.app.services.db import history_db_path

_ph = PasswordHasher()
SESSION_TTL_DAYS = 30


# ── 비밀번호 ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHash, Exception):
        return False


# ── 세션 토큰 ─────────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: str) -> str:
    """새 세션 토큰을 발급하고 DB에 hash를 저장한다. raw token 반환."""
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=SESSION_TTL_DAYS)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (token_hash, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    return token


def get_session_user(token: str) -> Optional[dict]:
    """토큰으로 유효한 세션의 사용자 정보를 반환한다. 만료되었으면 None."""
    if not token:
        return None
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT u.id, u.church, u.nickname, u.email
            FROM auth_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token_hash = ? AND s.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE auth_sessions SET last_used_at = ? WHERE token_hash = ?",
                (now, token_hash),
            )
            conn.commit()
    return dict(row) if row else None


def delete_session(token: str) -> None:
    if not token:
        return
    token_hash = _hash_token(token)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()


def delete_sessions_for_user(user_id: str) -> None:
    """해당 사용자의 모든 세션을 삭제한다 — 비밀번호 변경/초기화 후 강제 로그아웃용."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        conn.commit()


def cleanup_expired_sessions() -> int:
    """만료된 세션을 삭제하고 삭제된 행 수를 반환한다."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        cur = conn.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
        conn.commit()
        return cur.rowcount


# ── 사용자 CRUD ───────────────────────────────────────────────────────────────

def user_id_exists(user_id: str) -> bool:
    with sqlite3.connect(history_db_path()) as conn:
        row = conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None


def get_user(user_id: str) -> Optional[dict]:
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, church, nickname, password_hash, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_user(user_id: str, church: str, nickname: str, password: str, email: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)
    with sqlite3.connect(history_db_path()) as conn:
        # 교회가 없으면 자동 등록
        conn.execute(
            "INSERT OR IGNORE INTO churches (name, created_at) VALUES (?, ?)",
            (church.strip(), now),
        )
        conn.execute(
            "INSERT INTO users (id, church, nickname, password_hash, email, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, church.strip(), nickname.strip(), pw_hash, email.strip(), now, now),
        )
        conn.commit()


def set_email(user_id: str, email: str) -> None:
    """본인 이메일 등록/변경 — 비밀번호 찾기 본인 확인용이므로 비밀번호 검증은 필요 없다."""
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "UPDATE users SET email = ?, updated_at = ? WHERE id = ?",
            (email.strip(), now, user_id),
        )
        conn.commit()


def list_churches() -> list[str]:
    """등록된 교회명 목록을 알파벳/가나다 순으로 반환한다."""
    with sqlite3.connect(history_db_path()) as conn:
        rows = conn.execute(
            "SELECT name FROM churches ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [r[0] for r in rows]


def list_users() -> list[dict]:
    """관리자 화면용 회원 목록 — 비밀번호 해시는 제외한다."""
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, church, nickname, email, created_at FROM users ORDER BY church, nickname"
        ).fetchall()
    return [
        {**dict(row), "is_admin": is_admin(row["id"])}
        for row in rows
    ]


def list_admin_emails() -> list[str]:
    """이메일이 등록된 관리자의 이메일 목록 — 비밀번호 초기화 승인 알림용."""
    with sqlite3.connect(history_db_path()) as conn:
        rows = conn.execute("SELECT id, email FROM users").fetchall()
    return [email for uid, email in rows if uid in ADMIN_USERS and email]


# ── 관리자 / 비밀번호 변경·초기화 ──────────────────────────────────────────────

def is_admin(user_id: str) -> bool:
    return user_id in ADMIN_USERS


def set_password(user_id: str, new_password: str) -> None:
    """비밀번호 해시를 갱신하고, 탈취된 세션을 막기 위해 기존 세션을 모두 삭제한다."""
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(new_password)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (pw_hash, now, user_id),
        )
        conn.commit()
    delete_sessions_for_user(user_id)


def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """본인 비밀번호 변경 — 기존 비밀번호 검증 후 갱신한다. 실패 시 False."""
    user = get_user(user_id)
    if user is None or not verify_password(old_password, user["password_hash"]):
        return False
    set_password(user_id, new_password)
    return True


def generate_temp_password() -> str:
    """관리자 초기화 시 사용할 임시 비밀번호를 생성한다."""
    return secrets.token_urlsafe(9)


# ── 비밀번호 찾기 (관리자 승인) ──────────────────────────────────────────────

def create_password_reset_request(user_id: str) -> str:
    """비밀번호 초기화 요청을 생성하고, 관리자 승인용 토큰(raw)을 반환한다."""
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=PASSWORD_RESET_TTL_HOURS)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "INSERT INTO password_reset_requests "
            "(token_hash, user_id, status, requested_at, expires_at) VALUES (?, ?, 'pending', ?, ?)",
            (token_hash, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()
    return token


def get_password_reset_request(token: str) -> Optional[dict]:
    """토큰으로 요청과 대상 회원 정보를 함께 반환한다."""
    token_hash = _hash_token(token)
    with sqlite3.connect(history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT r.status, r.requested_at, r.expires_at,
                   u.id AS user_id, u.nickname, u.church, u.email
            FROM password_reset_requests r
            JOIN users u ON r.user_id = u.id
            WHERE r.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
    return dict(row) if row else None


def decide_password_reset_request(token: str, approve: bool) -> Optional[dict]:
    """승인/거절 처리. 이미 처리되었거나 만료된 요청이면 상태만 반환하고 아무 작업도 하지 않는다.
    승인 시 반환값에 임시 비밀번호(temp_password)가 포함된다.
    """
    req = get_password_reset_request(token)
    if req is None:
        return None

    now = datetime.now(timezone.utc)
    if req["status"] != "pending":
        return {**req, "temp_password": None}
    if datetime.fromisoformat(req["expires_at"]) < now:
        _finalize_password_reset_request(token, "expired", now)
        return {**req, "status": "expired", "temp_password": None}

    new_status = "approved" if approve else "rejected"
    _finalize_password_reset_request(token, new_status, now)

    temp_password: str | None = None
    if approve:
        temp_password = generate_temp_password()
        set_password(req["user_id"], temp_password)

    return {**req, "status": new_status, "temp_password": temp_password}


def _finalize_password_reset_request(token: str, status: str, decided_at: datetime) -> None:
    token_hash = _hash_token(token)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "UPDATE password_reset_requests SET status = ?, decided_at = ? WHERE token_hash = ?",
            (status, decided_at.isoformat(), token_hash),
        )
        conn.commit()
