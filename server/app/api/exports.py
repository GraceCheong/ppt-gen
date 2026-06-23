"""PPT 생성, 송리스트 카드, PPTX→PNG 변환 엔드포인트."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from server.app.api.deps import get_optional_auth_context
from server.app.config import MAX_UPLOAD_BYTES
from server.app.models.auth import AuthContext
from pptx import Presentation

from server.app import state
from server.app.config import PPTX_MEDIA_TYPE, GENERATOR_VERSION

# config import 후 sys.path(src/)가 설정되어 있어서 ppt_service를 직접 import 가능
from ppt_service import LocalOfficeUnavailable, NoLyricsError  # noqa: E402

from server.app.services.history_service import (
    save_weekly_repertoire_snapshot,
    index_lyrics_from_snapshot,
)
from server.app.services.ppt_generation_service import build_integrated_pptx
from server.app.services.songlist_service import build_songlist_card_png
from server.app.services.template_service import (
    resolve_songlist_template_path,
    resolve_template_path,
    server_songlist_template_path,
)

logger = logging.getLogger("ppt_gen.server")
router = APIRouter()


# ── 공통 헬퍼 ───────────────────────────────────────────────────────────────

def _load_payload(payload: str) -> dict:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise HTTPException(400, detail=f"payload JSON 형식이 올바르지 않습니다: {e}")
    if not isinstance(data, dict):
        raise HTTPException(400, detail="payload는 JSON object여야 합니다.")
    return data


def _sequence_entries_from_payload(data: dict) -> list[tuple[str, str]]:
    entries = data.get("sequence_entries")
    if not isinstance(entries, list) or not entries:
        raise HTTPException(400, detail="sequence_entries가 비어 있습니다.")
    parsed = []
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise HTTPException(400, detail=f"{index}번째 sequence entry가 올바르지 않습니다.")
        title = str(item.get("title", "")).strip()
        sequence = str(item.get("sequence", "")).strip()
        if not title or not sequence:
            raise HTTPException(
                400,
                detail=f"{index}번째 곡 제목 또는 진행 순서가 비어 있습니다.",
            )
        parsed.append((title, sequence))
    return parsed


async def _save_upload(upload: UploadFile, path: str) -> None:
    data = await upload.read()
    if not data:
        raise HTTPException(400, detail="업로드된 파일이 비어 있습니다.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail=f"파일 크기가 {MAX_UPLOAD_BYTES // (1024*1024)}MB를 초과합니다.")
    with open(path, "wb") as f:
        f.write(data)


async def _save_upload_atomic(upload: UploadFile, path: str) -> None:
    data = await upload.read()
    if not data:
        raise HTTPException(400, detail="업로드된 파일이 비어 있습니다.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail=f"파일 크기가 {MAX_UPLOAD_BYTES // (1024*1024)}MB를 초과합니다.")
    target_abs = os.path.abspath(path)
    target_dir = os.path.dirname(target_abs)
    os.makedirs(target_dir, exist_ok=True)
    temp_path = target_abs + ".tmp"
    try:
        os.remove(temp_path)
    except (FileNotFoundError, PermissionError):
        pass
    with open(temp_path, "wb") as f:
        f.write(data)
    for _attempt in range(4):
        try:
            os.replace(temp_path, target_abs)
            break
        except PermissionError:
            if _attempt < 3:
                time.sleep(0.25)
    else:
        try:
            os.remove(target_abs)
        except (FileNotFoundError, PermissionError):
            pass
        try:
            os.replace(temp_path, target_abs)
        except (PermissionError, FileExistsError):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise HTTPException(
                503,
                detail="템플릿 파일이 다른 프로그램에서 사용 중입니다. "
                       "PowerPoint 등을 닫은 후 다시 시도해 주세요.",
            )


def _slide_px(pptx_path: str, long_edge_px: int = 2000) -> tuple[int, int]:
    prs = Presentation(pptx_path)
    w, h = prs.slide_width, prs.slide_height
    if w >= h:
        return long_edge_px, int(long_edge_px * h / w)
    return int(long_edge_px * w / h), long_edge_px


def _convert_sync(pptx_path: str, png_path: str) -> None:
    """PowerPoint COM API로 첫 번째 슬라이드를 PNG로 변환."""
    import comtypes
    import comtypes.client
    from powerpoint_com import create_powerpoint_application, open_presentation_hidden

    width_px, height_px = _slide_px(pptx_path)
    pptx_abs = os.path.abspath(pptx_path)
    png_abs = os.path.abspath(png_path)

    comtypes.CoInitialize()
    try:
        ppt = create_powerpoint_application(comtypes.client)
        try:
            prs_com = open_presentation_hidden(ppt, pptx_abs)
            try:
                prs_com.Slides(1).Export(png_abs, "PNG", width_px, height_px)
            finally:
                prs_com.Close()
        finally:
            ppt.Quit()
    finally:
        comtypes.CoUninitialize()


# ── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.post("/convert", response_class=Response)
async def convert(file: UploadFile = File(...)):
    """PPTX 파일을 받아 첫 번째 슬라이드를 PNG로 변환해 반환합니다."""
    if not (file.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 파일만 허용됩니다.")

    data = await file.read()

    with tempfile.TemporaryDirectory() as tmp:
        pptx_path = os.path.join(tmp, "input.pptx")
        png_path = os.path.join(tmp, "output.png")

        with open(pptx_path, "wb") as f:
            f.write(data)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(state.executor, _convert_sync, pptx_path, png_path)
        except Exception as e:
            logger.error("[convert] 변환 실패: %s", e)
            raise HTTPException(500, detail="슬라이드 변환에 실패했습니다.")

        if not os.path.exists(png_path):
            raise HTTPException(500, detail="PNG 출력 파일을 찾을 수 없습니다.")

        with open(png_path, "rb") as f:
            png_data = f.read()

    logger.info("[convert] 완료 method=PowerPoint COM")
    return Response(content=png_data, media_type="image/png")


@router.post("/generate-ppt", response_class=Response)
async def generate_ppt(
    payload: str = Form(...),
    template: UploadFile = File(...),
    auth: AuthContext = Depends(get_optional_auth_context),
):
    """템플릿과 레파토리/가사 데이터를 받아 PPTX 파일을 생성해 반환합니다."""
    if not (template.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 템플릿만 허용됩니다.")

    data = _load_payload(payload)
    sequence_entries = _sequence_entries_from_payload(data)
    lyrics_by_title = data.get("lyrics_by_title") or {}
    if not isinstance(lyrics_by_title, dict):
        raise HTTPException(400, detail="lyrics_by_title은 JSON object여야 합니다.")

    try:
        max_lines_per_slide = int(data.get("max_lines_per_slide") or 2)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="max_lines_per_slide는 숫자여야 합니다.")

    try:
        max_chars_per_line = int(data.get("max_chars_per_line") or 18)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="max_chars_per_line은 숫자여야 합니다.")

    raw_font_size = data.get("lyrics_font_size")
    try:
        lyrics_font_size = (
            None if raw_font_size in (None, "", "default") else float(raw_font_size)
        )
    except (TypeError, ValueError):
        raise HTTPException(400, detail="lyrics_font_size는 숫자여야 합니다.")

    with tempfile.TemporaryDirectory() as tmp:
        template_path = os.path.join(tmp, "template.pptx")
        output_path = os.path.join(tmp, "output.pptx")
        await _save_upload(template, template_path)

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                state.executor,
                build_integrated_pptx,
                template_path,
                sequence_entries,
                lyrics_by_title,
                output_path,
                max_lines_per_slide,
                max_chars_per_line,
                lyrics_font_size,
            )
        except NoLyricsError as e:
            raise HTTPException(400, detail=str(e))
        except Exception as e:
            logger.error("[generate-ppt] PPT 생성 실패: %s", e)
            raise HTTPException(500, detail="PPT 생성에 실패했습니다.")

        if not os.path.exists(output_path):
            raise HTTPException(500, detail="PPTX 출력 파일을 찾을 수 없습니다.")

        with open(output_path, "rb") as f:
            pptx_data = f.read()

    logger.info(
        "[generate-ppt] 완료 method=python-pptx songs=%d skipped=%d",
        result["appended_count"],
        len(result.get("skipped_titles", [])),
    )
    if auth.mode == "user" and auth.church:
        try:
            saved_week = save_weekly_repertoire_snapshot(
                sequence_entries=sequence_entries,
                lyrics_by_title=lyrics_by_title,
                max_lines_per_slide=max_lines_per_slide,
                max_chars_per_line=max_chars_per_line,
                lyrics_font_size=lyrics_font_size,
                church=auth.church,
            )
            logger.info("[history] 주간 이력 저장 완료 week_end=%s church=%s", saved_week, auth.church)
            index_lyrics_from_snapshot(sequence_entries, lyrics_by_title)
        except Exception as e:
            logger.warning("[history] 주간 이력 저장 실패: %s", e)

    return Response(
        content=pptx_data,
        media_type=PPTX_MEDIA_TYPE,
        headers={
            "X-Appended-Count": str(result["appended_count"]),
            "X-PORR-Generator": GENERATOR_VERSION,
            "X-PORR-Slide-Plan": "Home,Worship,TitleLyricsRepeated,PrayerOrHome",
        },
    )


@router.post("/songlist-card", response_class=Response)
async def songlist_card(
    request: Request,
    payload: str = Form(...),
    template: UploadFile = File(...),
):
    """송리스트 템플릿과 곡 제목 목록을 받아 PNG 카드를 생성해 반환합니다."""
    if not (template.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 템플릿만 허용됩니다.")

    data = _load_payload(payload)
    song_titles = data.get("song_titles")
    if not isinstance(song_titles, list):
        raise HTTPException(400, detail="song_titles는 list여야 합니다.")
    song_titles = [str(t).strip() for t in song_titles if str(t).strip()]
    if not song_titles:
        raise HTTPException(400, detail="song_titles가 비어 있습니다.")

    template_path = server_songlist_template_path()
    songlist_lock = request.app.state.songlist_lock
    async with songlist_lock:
        await _save_upload_atomic(template, template_path)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "songlist_card.png")

            try:
                loop = asyncio.get_event_loop()
                week_num = await loop.run_in_executor(
                    state.executor,
                    build_songlist_card_png,
                    template_path,
                    song_titles,
                    output_path,
                )
            except LocalOfficeUnavailable as e:
                raise HTTPException(
                    503,
                    detail=f"로컬 오피스(LibreOffice/PowerPoint)를 사용할 수 없습니다: {e}",
                )
            except Exception as e:
                logger.error("[songlist-card] 생성 실패: %s", e)
                raise HTTPException(500, detail="송리스트 카드 생성에 실패했습니다.")

            if not os.path.exists(output_path):
                raise HTTPException(500, detail="PNG 출력 파일을 찾을 수 없습니다.")

            with open(output_path, "rb") as f:
                output_data = f.read()

    logger.info(
        "[songlist-card] 완료 week=%d songs=%d",
        week_num,
        len(song_titles),
    )
    return Response(
        content=output_data,
        media_type="image/png",
        headers={"X-Week-Number": str(week_num)},
    )


# ── 비동기 Job 기반 API ──────────────────────────────────────────────────────

@router.post("/api/exports/pptx")
async def api_export_pptx(
    request: Request,
    auth: AuthContext = Depends(get_optional_auth_context),
):
    """JSON 기반 비동기 PPT 생성 Job API.

    template_id로 서버에 있는 템플릿을 지정한다 (파일 업로드 불필요).
    즉시 job_id를 반환하고, GET /api/jobs/{job_id}로 상태를 확인한다.
    """
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 형식이 올바르지 않습니다: {e}")

    songs = data.get("songs")
    if not isinstance(songs, list) or not songs:
        raise HTTPException(400, detail="songs가 비어 있습니다.")

    sequence_entries: list[tuple[str, str]] = []
    lyrics_by_title: dict[str, str] = {}
    for idx, song in enumerate(songs, start=1):
        if not isinstance(song, dict):
            raise HTTPException(400, detail=f"{idx}번째 곡 데이터가 올바르지 않습니다.")
        title = str(song.get("title") or "").strip()
        sequence = str(song.get("sequence") or "").strip()
        if not title or not sequence:
            raise HTTPException(
                400,
                detail=f"{idx}번째 곡 제목 또는 진행 순서가 비어 있습니다.",
            )
        sequence_entries.append((title, sequence))
        lyrics = str(song.get("lyrics") or "").strip()
        if lyrics:
            lyrics_by_title[title] = lyrics

    settings = data.get("settings") or {}
    try:
        max_lines_per_slide = int(settings.get("max_lines_per_slide") or 2)
        max_chars_per_line = int(settings.get("max_chars_per_line") or 18)
    except (TypeError, ValueError) as e:
        raise HTTPException(400, detail=f"settings 값이 올바르지 않습니다: {e}")

    raw_font_size = settings.get("lyrics_font_size")
    try:
        lyrics_font_size = (
            None if raw_font_size in (None, "", "default") else float(raw_font_size)
        )
    except (TypeError, ValueError):
        raise HTTPException(400, detail="lyrics_font_size는 숫자여야 합니다.")

    template_id = str(data.get("template_id") or "").strip() or None
    try:
        template_path = resolve_template_path(template_id)
    except FileNotFoundError as e:
        raise HTTPException(400, detail=str(e))

    from server.app.jobs.job_store import create_job
    from server.app.workers.ppt_worker import run_pptx_job

    job = create_job("pptx")
    asyncio.create_task(
        run_pptx_job(
            job_id=job.id,
            template_path=template_path,
            sequence_entries=sequence_entries,
            lyrics_by_title=lyrics_by_title,
            max_lines_per_slide=max_lines_per_slide,
            max_chars_per_line=max_chars_per_line,
            lyrics_font_size=lyrics_font_size,
        )
    )
    logger.info("[api/exports/pptx] job_id=%s songs=%d", job.id, len(songs))
    return {"job_id": job.id}


@router.post("/api/exports/songlist-card")
async def api_export_songlist_card(request: Request):
    """JSON 기반 비동기 송리스트 카드 생성 Job API.

    template_id를 지정하거나 생략 시 songlist_template.pptx를 사용한다.
    """
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 형식이 올바르지 않습니다: {e}")

    song_titles = data.get("song_titles")
    if not isinstance(song_titles, list):
        raise HTTPException(400, detail="song_titles는 list여야 합니다.")
    song_titles = [str(t).strip() for t in song_titles if str(t).strip()]
    if not song_titles:
        raise HTTPException(400, detail="song_titles가 비어 있습니다.")

    template_id = str(data.get("template_id") or "").strip() or None
    try:
        template_path = resolve_songlist_template_path(template_id)
    except FileNotFoundError as e:
        raise HTTPException(400, detail=str(e))

    from server.app.jobs.job_store import create_job
    from server.app.workers.songlist_worker import run_songlist_job

    job = create_job("songlist_card")
    asyncio.create_task(
        run_songlist_job(
            job_id=job.id,
            template_path=template_path,
            song_titles=song_titles,
        )
    )
    logger.info("[api/exports/songlist-card] job_id=%s songs=%d", job.id, len(song_titles))
    return {"job_id": job.id}
