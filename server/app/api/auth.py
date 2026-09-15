"""인증 라우터 — 회원가입, 로그인, 로그아웃, 현재 사용자 조회."""
from __future__ import annotations

import re

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from server.app.api.deps import require_admin, require_user
from server.app.api.rate_limit import limiter
from server.app.config import HTTPS_MODE, PASSWORD_RESET_TTL_HOURS, PUBLIC_BASE_URL
from server.app.models.auth import AuthContext
from server.app.services import auth_service, email_service

router = APIRouter()

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{2,30}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
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


@router.get("/auth/churches")
def get_churches():
    """회원가입 시 교회 목록 조회 — 인증 불필요."""
    return {"churches": auth_service.list_churches()}


@router.get("/auth/check-id")
@limiter.limit("20/minute")
def check_id(request: Request, id: str):
    """ID 사용 가능 여부를 반환한다."""
    if not _ID_RE.match(id):
        return {
            "available": False,
            "reason": "ID는 영문·숫자·_·- 만 사용할 수 있으며 2~30자여야 합니다.",
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
    email = str(data.get("email") or "").strip()

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
            detail="ID는 영문·숫자·_·- 만 사용할 수 있으며 2~30자여야 합니다.",
        )
    if len(pw) < _MIN_PW_LEN:
        raise HTTPException(
            400, detail=f"비밀번호는 최소 {_MIN_PW_LEN}자 이상이어야 합니다."
        )
    if not _EMAIL_RE.match(email):
        raise HTTPException(
            400, detail="비밀번호 찾기를 위해 올바른 이메일 주소를 입력해주세요."
        )
    if auth_service.user_id_exists(user_id):
        raise HTTPException(409, detail="이미 사용 중인 ID입니다.")

    auth_service.create_user(user_id, church, nickname, pw, email)
    token = auth_service.create_session(user_id)
    _set_session_cookie(response, token)
    return {
        "ok": True,
        "user": {"id": user_id, "church": church, "nickname": nickname, "email": email},
    }


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
            "email": user["email"],
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
                    "email": user["email"],
                    "is_admin": auth_service.is_admin(user["id"]),
                },
            }
    return {"mode": "guest", "user": None}


@router.put("/auth/password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(require_user),
    session: str | None = Cookie(default=None),
):
    """본인 비밀번호 변경 — 기존 비밀번호 확인 필요. 성공 시 다른 세션은 모두 로그아웃된다."""
    data = await request.json()
    old_pw = str(data.get("old_pw") or "")
    new_pw = str(data.get("new_pw") or "")

    if len(new_pw) < _MIN_PW_LEN:
        raise HTTPException(
            400, detail=f"비밀번호는 최소 {_MIN_PW_LEN}자 이상이어야 합니다."
        )
    if not auth_service.change_password(ctx.user_id, old_pw, new_pw):
        raise HTTPException(401, detail="현재 비밀번호가 올바르지 않습니다.")

    # 모든 세션이 삭제되었으므로 현재 요청용 세션을 새로 발급한다.
    token = auth_service.create_session(ctx.user_id)
    _set_session_cookie(response, token)
    return {"ok": True}


@router.put("/auth/email")
@limiter.limit("10/minute")
async def update_email(request: Request, ctx: AuthContext = Depends(require_user)):
    """본인 이메일 등록/변경 — 비밀번호 찾기 본인 확인용이라 비밀번호 재확인은 요구하지 않는다."""
    data = await request.json()
    email = str(data.get("email") or "").strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, detail="올바른 이메일 주소를 입력해주세요.")
    auth_service.set_email(ctx.user_id, email)
    return {"ok": True, "email": email}


@router.post("/auth/password-reset/request")
@limiter.limit("5/minute")
async def request_password_reset(request: Request):
    """비밀번호 찾기 요청 — 이메일이 등록되어 있으면 관리자 승인 메일을 발송한다."""
    data = await request.json()
    user_id = str(data.get("id") or "").strip()

    user = auth_service.get_user(user_id)
    if user is None:
        raise HTTPException(404, detail="등록되지 않은 아이디입니다.")
    if not user["email"]:
        raise HTTPException(
            400,
            detail="이메일 미등록으로 비밀번호 변경이 불가합니다. 이메일을 입력해주시거나, 관리자에게 문의하세요.",
        )

    token = auth_service.create_password_reset_request(user_id)
    approve_url = f"{PUBLIC_BASE_URL}/auth/admin/password-reset/{token}"
    subject = f"[PO,RR] 비밀번호 초기화 승인 요청 — {user['nickname']} ({user_id})"
    body = (
        f"{user['church']} {user['nickname']}님({user_id})이 비밀번호 초기화를 요청했습니다.\n\n"
        f"아래 링크를 열어 승인 또는 거절을 선택해주세요 (발급 후 {PASSWORD_RESET_TTL_HOURS}시간 동안만 유효합니다):\n"
        f"{approve_url}\n"
    )
    for admin_email in auth_service.list_admin_emails():
        email_service.send_email(admin_email, subject, body)

    return {
        "ok": True,
        "message": "비밀번호 초기화 요청이 접수되었습니다. 관리자 승인 후 이메일로 안내드립니다.",
    }


@router.get("/auth/admin/password-reset/{token}", response_class=HTMLResponse)
def admin_password_reset_confirm_page(token: str):
    """관리자가 이메일 링크를 클릭했을 때 보여주는 승인/거절 확인 화면."""
    req = auth_service.get_password_reset_request(token)
    if req is None:
        return _reset_html("존재하지 않거나 만료된 요청입니다.")
    if req["status"] != "pending":
        return _reset_html(f"이미 처리된 요청입니다 (상태: {req['status']}).")

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"><title>비밀번호 초기화 승인</title></head>
    <body style="font-family:sans-serif;max-width:480px;margin:60px auto;line-height:1.6;">
      <h2>비밀번호 초기화 요청</h2>
      <p><b>{req['church']} {req['nickname']}</b>님 ({req['user_id']})의 비밀번호 초기화 요청입니다.</p>
      <form method="post" action="/auth/admin/password-reset/{token}/approve" style="display:inline">
        <button type="submit" style="padding:10px 20px;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;">승인</button>
      </form>
      <form method="post" action="/auth/admin/password-reset/{token}/reject" style="display:inline;margin-left:8px">
        <button type="submit" style="padding:10px 20px;background:#fff;color:#dc2626;border:1px solid #dc2626;border-radius:6px;cursor:pointer;">거절</button>
      </form>
    </body></html>
    """)


@router.post("/auth/admin/password-reset/{token}/approve", response_class=HTMLResponse)
def admin_password_reset_approve(token: str):
    """관리자 승인 — 비밀번호를 초기화하고 임시 비밀번호를 사용자 이메일로 발송한다."""
    result = auth_service.decide_password_reset_request(token, approve=True)
    if result is None:
        return _reset_html("존재하지 않는 요청입니다.")
    if result["status"] != "approved":
        return _reset_html(f"처리할 수 없는 요청입니다 (상태: {result['status']}).")

    subject = "[PO,RR] 비밀번호가 초기화되었습니다"
    body = (
        f"{result['nickname']}님, 요청하신 비밀번호 초기화가 승인되었습니다.\n\n"
        f"임시 비밀번호: {result['temp_password']}\n\n"
        f"로그인 후 반드시 비밀번호를 변경해주세요."
    )
    email_service.send_email(result["email"], subject, body)
    return _reset_html("승인되었습니다. 임시 비밀번호를 회원 이메일로 발송했습니다.")


@router.post("/auth/admin/password-reset/{token}/reject", response_class=HTMLResponse)
def admin_password_reset_reject(token: str):
    """관리자 거절 — 사용자에게 거절 사실을 안내 메일로 발송한다."""
    result = auth_service.decide_password_reset_request(token, approve=False)
    if result is None:
        return _reset_html("존재하지 않는 요청입니다.")
    if result["status"] != "rejected":
        return _reset_html(f"처리할 수 없는 요청입니다 (상태: {result['status']}).")

    subject = "[PO,RR] 비밀번호 초기화 요청이 거절되었습니다"
    body = (
        f"{result['nickname']}님, 요청하신 비밀번호 초기화가 거절되었습니다.\n\n"
        f"자세한 사항은 관리자에게 문의해주세요."
    )
    email_service.send_email(result["email"], subject, body)
    return _reset_html("요청을 거절했습니다. 회원에게 안내 메일을 발송했습니다.")


def _reset_html(message: str) -> HTMLResponse:
    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"><title>비밀번호 초기화</title></head>
    <body style="font-family:sans-serif;max-width:480px;margin:60px auto;line-height:1.6;">
      <p>{message}</p>
    </body></html>
    """)


@router.get("/auth/admin/users")
def admin_list_users(ctx: AuthContext = Depends(require_admin)):
    """관리자 전용 — 전체 회원 목록 조회."""
    return {"users": auth_service.list_users()}


@router.post("/auth/admin/users/{user_id}/reset-password")
@limiter.limit("10/minute")
async def admin_reset_password(
    user_id: str, request: Request, ctx: AuthContext = Depends(require_admin)
):
    """관리자 전용 — 회원 비밀번호를 초기화한다. 새 비밀번호를 지정하지 않으면 임시 비밀번호를 생성해 반환한다."""
    if not auth_service.user_id_exists(user_id):
        raise HTTPException(404, detail="존재하지 않는 회원입니다.")

    data = await request.json() if await request.body() else {}
    new_pw = str(data.get("new_pw") or "")
    temp_password: str | None = None
    if new_pw:
        if len(new_pw) < _MIN_PW_LEN:
            raise HTTPException(
                400, detail=f"비밀번호는 최소 {_MIN_PW_LEN}자 이상이어야 합니다."
            )
    else:
        new_pw = auth_service.generate_temp_password()
        temp_password = new_pw

    auth_service.set_password(user_id, new_pw)
    return {"ok": True, "temp_password": temp_password}


@router.post("/auth/logout")
def logout(response: Response, session: str | None = Cookie(default=None)):
    """세션을 삭제하고 쿠키를 지운다."""
    if session:
        auth_service.delete_session(session)
    response.delete_cookie("session")
    return {"ok": True}
