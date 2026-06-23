"""FastAPI 공통 의존성 — 인증 컨텍스트."""
from __future__ import annotations

from fastapi import Cookie, HTTPException

from server.app.models.auth import AuthContext
from server.app.services import auth_service


def get_optional_auth_context(
    session: str | None = Cookie(default=None),
) -> AuthContext:
    """세션이 있으면 user, 없으면 guest AuthContext를 반환한다."""
    if session:
        user = auth_service.get_session_user(session)
        if user:
            return AuthContext(
                mode="user",
                user_id=user["id"],
                church=user["church"],
                nickname=user["nickname"],
            )
    return AuthContext(mode="guest")


def require_user(
    session: str | None = Cookie(default=None),
) -> AuthContext:
    """로그인 사용자만 허용한다. 비로그인이면 401."""
    ctx = get_optional_auth_context(session)
    if ctx.mode != "user":
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return ctx
