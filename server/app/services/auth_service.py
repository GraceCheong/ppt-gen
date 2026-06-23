"""인증 서비스 — 비밀번호 해시, 세션 토큰 관리."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

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
            SELECT u.id, u.church, u.nickname
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
            "SELECT id, church, nickname, password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_user(user_id: str, church: str, nickname: str, password: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)
    with sqlite3.connect(history_db_path()) as conn:
        conn.execute(
            "INSERT INTO users (id, church, nickname, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, church.strip(), nickname.strip(), pw_hash, now, now),
        )
        conn.commit()
