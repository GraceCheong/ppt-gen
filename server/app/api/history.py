import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from server.app.api.deps import get_optional_auth_context, require_user
from server.app.models.auth import AuthContext
from server.app.services.db import history_db_path, init_history_db
from server.app.services.history_service import (
    delete_weekly_entry,
    get_weekly_entry,
    list_weekly_repertoire,
    save_weekly_entry_manual,
    update_weekly_entry,
    update_weekly_roles,
)
from server.app.api.graph import invalidate_graph_cache
from server.app.services.lyrics_service import upsert_lyrics_catalog

router = APIRouter()


@router.get("/history/weekly")
@router.get("/api/history/weekly")
def get_weekly_history(
    year_from: int = 2026,
    auth: AuthContext = Depends(require_user),
):
    try:
        if year_from < 1900:
            year_from = 1900
        return {
            "items": list_weekly_repertoire(year_from=year_from, church=auth.church),
            "year_from": year_from,
        }
    except Exception as e:
        raise HTTPException(500, detail=f"주간 이력 조회 실패: {e}")


@router.post("/api/history/weekly")
async def create_history_entry(
    request: Request,
    auth: AuthContext = Depends(require_user),
):
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 파싱 오류: {e}")

    date_str = str(data.get("week_end_date") or "").strip()
    if not date_str:
        raise HTTPException(400, detail="week_end_date는 필수입니다.")
    try:
        week_end = datetime.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, detail="week_end_date 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    raw = data.get("sequence_entries") or []
    entries = [(str(e.get("title") or "").strip(), str(e.get("sequence") or "").strip())
               for e in raw if str(e.get("title") or "").strip()]
    if not entries:
        raise HTTPException(400, detail="유효한 곡이 없습니다.")

    saved = save_weekly_entry_manual(week_end, entries, church=auth.church)
    invalidate_graph_cache()

    for title, sequence in entries:
        try:
            upsert_lyrics_catalog(title, "", source="history", sequence=sequence)
        except Exception:
            pass

    return {"week_end_date": saved}


@router.put("/api/history/weekly/{week_end_date}/entries")
async def update_history_entries(
    week_end_date: str,
    request: Request,
    auth: AuthContext = Depends(require_user),
):
    """곡 목록 수정 — 세션 인증 후 church 소유권 확인."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 파싱 오류: {e}")

    try:
        datetime.date.fromisoformat(week_end_date)
    except ValueError:
        raise HTTPException(400, detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    existing = get_weekly_entry(week_end_date, auth.church)
    if not existing:
        raise HTTPException(404, detail="해당 날짜의 이력이 없습니다.")

    raw = data.get("sequence_entries") or []
    entries = [(str(e.get("title") or "").strip(), str(e.get("sequence") or "").strip())
               for e in raw if str(e.get("title") or "").strip()]
    if not entries:
        raise HTTPException(400, detail="유효한 곡이 없습니다.")

    update_weekly_entry(week_end_date, entries, church=auth.church)
    invalidate_graph_cache()

    for title, sequence in entries:
        try:
            upsert_lyrics_catalog(title, "", source="history", sequence=sequence)
        except Exception:
            pass

    return {"ok": True, "week_end_date": week_end_date}


@router.put("/api/history/weekly/{week_end_date}/roles")
async def set_weekly_roles(
    week_end_date: str,
    request: Request,
    auth: AuthContext = Depends(require_user),
):
    """담당자 정보 저장 — 세션 인증 후 church 소유권 확인."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 파싱 오류: {e}")

    try:
        datetime.date.fromisoformat(week_end_date)
    except ValueError:
        raise HTTPException(400, detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    update_weekly_roles(
        week_end_date,
        str(data.get("worship_leader") or "").strip(),
        str(data.get("accompanist") or "").strip(),
        str(data.get("prayer_person") or "").strip(),
        church=auth.church,
        event=str(data.get("event") or "").strip(),
    )
    return {"ok": True, "week_end_date": week_end_date}


@router.delete("/api/history/weekly/{week_end_date}")
def delete_history_entry(
    week_end_date: str,
    auth: AuthContext = Depends(require_user),
):
    """이력 삭제 — 세션 인증 후 church 소유권 확인."""
    try:
        datetime.date.fromisoformat(week_end_date)
    except ValueError:
        raise HTTPException(400, detail="날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    existing = get_weekly_entry(week_end_date, auth.church)
    if not existing:
        raise HTTPException(404, detail="해당 날짜의 이력이 없거나 접근 권한이 없습니다.")

    delete_weekly_entry(week_end_date, auth.church)
    invalidate_graph_cache()
    return {"ok": True, "week_end_date": week_end_date}


def _read_db_bytes() -> bytes:
    import os
    db_path = history_db_path()
    if not os.path.exists(db_path):
        init_history_db()
    with open(db_path, "rb") as f:
        return f.read()


@router.get("/history/db", response_class=Response)
def download_history_db_legacy():
    """레거시 GUI 호환용 — 인증 없이 DB 다운로드."""
    return Response(
        content=_read_db_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="weekly_repertoire.db"'},
    )


@router.get("/api/history/db", response_class=Response)
def download_history_db(_auth: AuthContext = Depends(require_user)):
    """로그인 필수 DB 다운로드."""
    return Response(
        content=_read_db_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="weekly_repertoire.db"'},
    )
