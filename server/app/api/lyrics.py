import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from auto_lyrics_downloader import fetch_lyrics_from_bugs
from server.app.services.lyrics_service import (
    search_lyrics_catalog,
    list_recent_lyrics_catalog,
    lookup_lyrics_by_title,
    upsert_lyrics_catalog,
)
from server.app import state

logger = logging.getLogger("ppt_gen.server")
router = APIRouter()


async def _parse_json_body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 형식이 올바르지 않습니다: {e}")
    if not isinstance(data, dict):
        raise HTTPException(400, detail="요청 본문은 JSON object여야 합니다.")
    return data


@router.get("/lyrics/recent")
@router.get("/api/lyrics/recent")
def list_recent_lyrics(limit: int = 50):
    try:
        results = list_recent_lyrics_catalog(limit=limit)
    except Exception as e:
        raise HTTPException(500, detail=f"가사 목록 조회 실패: {e}")
    return {"items": results, "count": len(results)}


@router.get("/lyrics/search")
@router.get("/api/lyrics/search")
def search_lyrics(q: str = "", limit: int = 10):
    if not q.strip():
        raise HTTPException(400, detail="검색어(q)를 입력해 주세요.")
    try:
        results = search_lyrics_catalog(q, limit=limit)
    except Exception as e:
        raise HTTPException(500, detail=f"가사 검색 실패: {e}")
    return {"items": results, "query": q, "count": len(results)}


@router.get("/lyrics/by-title")
@router.get("/api/lyrics/by-title")
def get_lyrics_by_title(title: str = ""):
    if not title.strip():
        raise HTTPException(400, detail="곡명(title)을 입력해 주세요.")
    try:
        result = lookup_lyrics_by_title(title)
    except Exception as e:
        raise HTTPException(500, detail=f"가사 조회 실패: {e}")
    if result is None:
        raise HTTPException(404, detail=f"'{title}' 가사를 찾을 수 없습니다.")
    return result


@router.post("/lyrics")
@router.post("/api/lyrics")
async def upsert_lyrics(request: Request):
    data = await _parse_json_body(request)

    title = str(data.get("title") or "").strip()
    lyrics = str(data.get("lyrics") or "").strip()
    source = str(data.get("source") or "manual").strip()
    sequence = str(data.get("sequence") or "").strip()

    if not title:
        raise HTTPException(400, detail="title은 필수입니다.")
    if not lyrics:
        raise HTTPException(400, detail="lyrics는 필수입니다.")
    if source not in ("manual", "bugs", "history"):
        source = "manual"

    try:
        upsert_lyrics_catalog(title, lyrics, source, sequence=sequence)
    except Exception as e:
        raise HTTPException(500, detail=f"가사 저장 실패: {e}")

    logger.info("[lyrics] upsert title=%s source=%s", title, source)
    return {"status": "ok", "title": title, "source": source}


@router.post("/api/lyrics/bulk")
async def bulk_upsert_lyrics(request: Request):
    """이력 등에서 여러 곡을 한 번에 카탈로그에 저장합니다. 가사 없어도 title+sequence 등록 가능."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 파싱 오류: {e}")

    items = data.get("items") or []
    saved = 0
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        lyrics = str(item.get("lyrics") or "").strip()
        sequence = str(item.get("sequence") or "").strip()
        try:
            upsert_lyrics_catalog(title, lyrics, source="history", sequence=sequence)
            saved += 1
        except Exception as e:
            logger.warning("[lyrics/bulk] skip title=%s err=%s", title, e)

    logger.info("[lyrics/bulk] saved=%d", saved)
    return {"ok": True, "saved": saved}


@router.post("/api/lyrics/download")
async def download_lyrics(request: Request):
    """Bugs Music에서 가사를 크롤링해 반환하고, 성공 시 카탈로그에 저장합니다."""
    data = await _parse_json_body(request)

    title = str(data.get("title") or "").strip()
    if not title:
        raise HTTPException(400, detail="title은 필수입니다.")

    try:
        loop = asyncio.get_running_loop()
        lyrics = await loop.run_in_executor(state.executor, fetch_lyrics_from_bugs, title)
    except Exception as e:
        raise HTTPException(500, detail=f"가사 다운로드 중 오류: {e}")

    if not lyrics:
        return {"found": False, "lyrics": "", "title": title}

    try:
        sequence = str(data.get("sequence") or "").strip()
        upsert_lyrics_catalog(title, lyrics, source="bugs", sequence=sequence)
    except Exception as e:
        logger.warning("[lyrics/download] 카탈로그 저장 실패: %s", e)

    logger.info("[lyrics/download] title=%s found=True", title)
    return {"found": True, "lyrics": lyrics, "title": title}
