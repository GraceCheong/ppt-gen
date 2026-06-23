"""인증 라우터 — 회원가입, 로그인, 로그아웃, 현재 사용자 조회."""
from __future__ import annotations

import re

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from server.app.api.rate_limit import limiter
from server.app.config import HTTPS_MODE
from server.app.services import auth_service

router = APIRouter()

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{3,30}$")
_MIN_PW_LEN = 8
_MAX_CHURCH_LEN = 50
_MAX_NICKNAME_LEN = 50
_SESSION_MAX_AGE = 30 * 24 * 3600  # 30일


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="lax",
        max_age=_SESSION_MAX_AGE,
        secure=HTTPS_MODE,
    )


@router.get("/auth/check-id")
@limiter.limit("20/minute")
def check_id(request: Request, id: str):
    """ID 사용 가능 여부를 반환한다."""
    if not _ID_RE.match(id):
        return {
            "available": False,
            "reason": "ID는 영문·숫자·_·- 만 사용할 수 있으며 3~30자여야 합니다.",
        }
    exists = auth_service.user_id_exists(id)
    return {"available": not exists}


@router.post("/auth/signup")
@limiter.limit("5/minute")
async def signup(request: Request, response: Response):
    """회원가입 후 자동 로그인한다."""
    data = await request.json()
    church = str(data.get("church") or "").strip()
    nickname = str(data.get("nickname") or "").strip()
    user_id = str(data.get("id") or "").strip()
    pw = str(data.get("pw") or "")

    if not church:
        raise HTTPException(400, detail="교회명을 입력하세요.")
    if len(church) > _MAX_CHURCH_LEN:
        raise HTTPException(400, detail=f"교회명은 {_MAX_CHURCH_LEN}자 이하여야 합니다.")
    if not nickname:
        raise HTTPException(400, detail="닉네임을 입력하세요.")
    if len(nickname) > _MAX_NICKNAME_LEN:
        raise HTTPException(400, detail=f"닉네임은 {_MAX_NICKNAME_LEN}자 이하여야 합니다.")
    if not _ID_RE.match(user_id):
        raise HTTPException(
            400,
            detail="ID는 영문·숫자·_·- 만 사용할 수 있으며 3~30자여야 합니다.",
        )
    if len(pw) < _MIN_PW_LEN:
        raise HTTPException(
            400, detail=f"비밀번호는 최소 {_MIN_PW_LEN}자 이상이어야 합니다."
        )
    if auth_service.user_id_exists(user_id):
        raise HTTPException(409, detail="이미 사용 중인 ID입니다.")

    auth_service.create_user(user_id, church, nickname, pw)
    token = auth_service.create_session(user_id)
    _set_session_cookie(response, token)
    return {"ok": True, "user": {"id": user_id, "church": church, "nickname": nickname}}


@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response):
    """로그인 후 세션 쿠키를 발급한다."""
    data = await request.json()
    user_id = str(data.get("id") or "").strip()
    pw = str(data.get("pw") or "")

    user = auth_service.get_user(user_id)
    ok = user is not None and auth_service.verify_password(pw, user["password_hash"])
    if not ok:
        raise HTTPException(401, detail="로그인 정보가 올바르지 않습니다.")

    token = auth_service.create_session(user_id)
    _set_session_cookie(response, token)
    return {
        "ok": True,
        "user": {
            "id": user["id"],
            "church": user["church"],
            "nickname": user["nickname"],
        },
    }


@router.get("/auth/me")
def get_me(session: str | None = Cookie(default=None)):
    """현재 로그인 상태를 반환한다."""
    if session:
        user = auth_service.get_session_user(session)
        if user:
            return {
                "mode": "user",
                "user": {
                    "id": user["id"],
                    "church": user["church"],
                    "nickname": user["nickname"],
                },
            }
    return {"mode": "guest", "user": None}


@router.post("/auth/logout")
def logout(response: Response, session: str | None = Cookie(default=None)):
    """세션을 삭제하고 쿠키를 지운다."""
    if session:
        auth_service.delete_session(session)
    response.delete_cookie("session")
    return {"ok": True}
