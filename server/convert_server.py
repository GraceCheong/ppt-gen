"""
PPT 생성/변환 서버

실행 방법:
    pip install -r server/requirements.txt
    uvicorn server.convert_server:app --host 0.0.0.0 --port 8010

PNG 변환에는 Windows + Microsoft PowerPoint 또는 LibreOffice가 필요합니다.
"""

import asyncio
import datetime
import json
import logging
import os
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pptx import Presentation

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from constants import ASSETS_DIR_NAME, TEMPLATE_DIR_NAME, TEMPLATE_DOWNLOAD_URL
from ppt_service import (
    LocalOfficeUnavailable,
    NoLyricsError,
    build_integrated_pptx,
    build_songlist_card_png,
)
from powerpoint_com import create_powerpoint_application, open_presentation_hidden

logger = logging.getLogger("ppt_gen.server")

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
TEMPLATE_SYNC_INTERVAL_SECONDS = 10 * 60
GENERATOR_VERSION = "direct-python-pptx-v4"
MAX_ERROR_REPORT_TEXT = 12000

app = FastAPI(title="PO,RR PPT Server", version="1.1.0")

# COM은 단일 스레드에서 직렬로 처리해야 하므로 max_workers=1
_executor = ThreadPoolExecutor(max_workers=1)
_template_executor = ThreadPoolExecutor(max_workers=1)
_template_sync_task: asyncio.Task | None = None
_songlist_template_lock = asyncio.Lock()


def _history_db_path() -> str:
    history_dir = os.path.join(ROOT_DIR, "out", "history")
    os.makedirs(history_dir, exist_ok=True)
    return os.path.join(history_dir, "weekly_repertoire.db")


def _init_history_db() -> None:
    db_path = _history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_repertoire (
                week_end_date TEXT PRIMARY KEY,
                week_start_date TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                sequence_entries_json TEXT NOT NULL,
                lyrics_by_title_json TEXT NOT NULL,
                max_lines_per_slide INTEGER,
                max_chars_per_line INTEGER,
                lyrics_font_size TEXT
            )
            """
        )
        conn.commit()


def _week_end_saturday(source_date: datetime.date) -> datetime.date:
    # Monday=0 ... Saturday=5 ... Sunday=6
    days_until_saturday = (5 - source_date.weekday()) % 7
    return source_date + datetime.timedelta(days=days_until_saturday)


def _save_weekly_repertoire_snapshot(
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
    max_lines_per_slide: int,
    max_chars_per_line: int,
    lyrics_font_size,
) -> str:
    today = datetime.date.today()
    week_end = _week_end_saturday(today)
    week_start = week_end - datetime.timedelta(days=6)
    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    db_path = _history_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO weekly_repertoire (
                week_end_date,
                week_start_date,
                updated_at_utc,
                sequence_entries_json,
                lyrics_by_title_json,
                max_lines_per_slide,
                max_chars_per_line,
                lyrics_font_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(week_end_date) DO UPDATE SET
                week_start_date=excluded.week_start_date,
                updated_at_utc=excluded.updated_at_utc,
                sequence_entries_json=excluded.sequence_entries_json,
                lyrics_by_title_json=excluded.lyrics_by_title_json,
                max_lines_per_slide=excluded.max_lines_per_slide,
                max_chars_per_line=excluded.max_chars_per_line,
                lyrics_font_size=excluded.lyrics_font_size
            """,
            (
                week_end.isoformat(),
                week_start.isoformat(),
                updated_at,
                json.dumps(
                    [
                        {"title": title, "sequence": sequence}
                        for title, sequence in sequence_entries
                    ],
                    ensure_ascii=False,
                ),
                json.dumps(lyrics_by_title, ensure_ascii=False),
                int(max_lines_per_slide),
                int(max_chars_per_line),
                "" if lyrics_font_size is None else str(lyrics_font_size),
            ),
        )
        conn.commit()

    return week_end.isoformat()


def _list_weekly_repertoire(year_from: int = 2026) -> list[dict]:
    db_path = _history_db_path()
    min_date = datetime.date(year_from, 1, 1).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                week_end_date,
                week_start_date,
                updated_at_utc,
                sequence_entries_json,
                lyrics_by_title_json,
                max_lines_per_slide,
                max_chars_per_line,
                lyrics_font_size
            FROM weekly_repertoire
            WHERE week_end_date >= ?
            ORDER BY week_end_date DESC
            """,
            (min_date,),
        ).fetchall()

    history = []
    for row in rows:
        history.append(
            {
                "week_end_date": row["week_end_date"],
                "week_start_date": row["week_start_date"],
                "updated_at_utc": row["updated_at_utc"],
                "sequence_entries": json.loads(row["sequence_entries_json"]),
                "lyrics_by_title": json.loads(row["lyrics_by_title_json"]),
                "max_lines_per_slide": row["max_lines_per_slide"],
                "max_chars_per_line": row["max_chars_per_line"],
                "lyrics_font_size": row["lyrics_font_size"] or None,
            }
        )

    return history


def _error_report_dir() -> str:
    path = os.path.join(ROOT_DIR, "out", "error_reports")
    os.makedirs(path, exist_ok=True)
    return path


def _trim_report_text(value, limit: int = MAX_ERROR_REPORT_TEXT) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[trimmed]"


def _sanitize_report(data: dict, request: Request) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    client_host = request.client.host if request.client else ""
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}

    return {
        "received_at": now.isoformat(),
        "client_host": client_host,
        "reported_at": _trim_report_text(data.get("reported_at"), 200),
        "context": _trim_report_text(data.get("context"), 300),
        "message": _trim_report_text(data.get("message"), 1000),
        "traceback": _trim_report_text(data.get("traceback")),
        "extra": extra,
        "log_tail": data.get("log_tail") if isinstance(data.get("log_tail"), list) else [],
        "runtime": data.get("runtime") if isinstance(data.get("runtime"), dict) else {},
    }


def _save_error_report(report: dict) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    file_path = os.path.join(_error_report_dir(), f"{now:%Y-%m-%d}.jsonl")
    with open(file_path, "a", encoding="utf-8") as report_file:
        report_file.write(json.dumps(report, ensure_ascii=False) + "\n")
    return file_path


def _server_template_dir() -> str:
    path = os.path.join(ROOT_DIR, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _server_template_files() -> set[str]:
    template_dir = _server_template_dir()
    result = set()
    for root, _, files in os.walk(template_dir):
        for file_name in files:
            if file_name.lower().endswith(".pptx"):
                result.add(os.path.abspath(os.path.join(root, file_name)))
    return result


def _server_songlist_template_path() -> str:
    return os.path.join(_server_template_dir(), "songlist_template.pptx")


def _sync_templates_once() -> list[str]:
    import gdown

    template_dir = _server_template_dir()
    before = _server_template_files()

    try:
        gdown.download_folder(
            TEMPLATE_DOWNLOAD_URL,
            output=template_dir,
            quiet=True,
            use_cookies=False,
            resume=True,
            remaining_ok=True,
        )
    except TypeError:
        gdown.download_folder(
            TEMPLATE_DOWNLOAD_URL,
            output=template_dir,
            quiet=True,
            use_cookies=False,
            resume=True,
        )

    after = _server_template_files()
    return sorted(os.path.basename(path) for path in after - before)


async def _template_sync_loop() -> None:
    while True:
        try:
            loop = asyncio.get_event_loop()
            added = await loop.run_in_executor(_template_executor, _sync_templates_once)
            if added:
                logger.info("[template-sync] 새 템플릿 %d개 다운로드: %s", len(added), ', '.join(added))
            else:
                logger.debug("[template-sync] 새 템플릿 없음")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[template-sync] 템플릿 확인 실패: %s", e)

        await asyncio.sleep(TEMPLATE_SYNC_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_template_sync() -> None:
    global _template_sync_task
    _init_history_db()
    if _template_sync_task is None or _template_sync_task.done():
        _template_sync_task = asyncio.create_task(_template_sync_loop())


@app.on_event("shutdown")
async def stop_template_sync() -> None:
    if _template_sync_task is not None:
        _template_sync_task.cancel()


def _slide_px(pptx_path: str, long_edge_px: int = 2000) -> tuple[int, int]:
    prs = Presentation(pptx_path)
    w, h = prs.slide_width, prs.slide_height
    if w >= h:
        return long_edge_px, int(long_edge_px * h / w)
    return int(long_edge_px * w / h), long_edge_px


def _convert_sync(pptx_path: str, png_path: str) -> None:
    """PowerPoint COM API로 첫 번째 슬라이드를 PNG로 변환합니다."""
    import comtypes
    import comtypes.client

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


async def _save_upload(upload: UploadFile, path: str) -> None:
    data = await upload.read()
    if not data:
        raise HTTPException(400, detail="업로드된 파일이 비어 있습니다.")

    with open(path, "wb") as f:
        f.write(data)


async def _save_upload_atomic(upload: UploadFile, path: str) -> None:
    data = await upload.read()
    if not data:
        raise HTTPException(400, detail="업로드된 파일이 비어 있습니다.")

    target_abs = os.path.abspath(path)
    target_dir = os.path.dirname(target_abs)
    os.makedirs(target_dir, exist_ok=True)
    temp_path = target_abs + ".tmp"

    with open(temp_path, "wb") as f:
        f.write(data)

    os.replace(temp_path, target_abs)


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
            raise HTTPException(400, detail=f"{index}번째 곡 제목 또는 진행 순서가 비어 있습니다.")
        parsed.append((title, sequence))

    return parsed


@app.get("/health")
def health():
    import importlib.util
    com_available = importlib.util.find_spec("comtypes") is not None
    return {
        "status": "ok",
        "comtypes": com_available,
        "generator": GENERATOR_VERSION,
    }


@app.get("/history/weekly")
def get_weekly_history(year_from: int = 2026):
    try:
        if year_from < 1900:
            year_from = 1900
        return {
            "items": _list_weekly_repertoire(year_from=year_from),
            "year_from": year_from,
        }
    except Exception as e:
        raise HTTPException(500, detail=f"주간 이력 조회 실패: {e}")


@app.get("/history/db", response_class=Response)
def download_history_db():
    db_path = _history_db_path()
    if not os.path.exists(db_path):
        _init_history_db()
    with open(db_path, "rb") as f:
        data = f.read()
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="weekly_repertoire.db"'},
    )


@app.post("/client-error-report")
async def client_error_report(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"오류 리포트 JSON 형식이 올바르지 않습니다: {e}")

    if not isinstance(data, dict):
        raise HTTPException(400, detail="오류 리포트는 JSON object여야 합니다.")

    report = _sanitize_report(data, request)
    file_path = _save_error_report(report)
    logger.info(
        "[client-error-report] context=%s message=%s saved=%s",
        report.get('context'), report.get('message'), file_path,
    )
    return {"status": "ok"}


@app.post("/convert", response_class=Response)
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
            await loop.run_in_executor(_executor, _convert_sync, pptx_path, png_path)
        except Exception as e:
            raise HTTPException(500, detail=f"변환 실패: {e}")

        if not os.path.exists(png_path):
            raise HTTPException(500, detail="PNG 출력 파일을 찾을 수 없습니다.")

        with open(png_path, "rb") as f:
            png_data = f.read()

    logger.info("[convert] 완료 method=PowerPoint COM")
    return Response(content=png_data, media_type="image/png")


@app.post("/generate-ppt", response_class=Response)
async def generate_ppt(payload: str = Form(...), template: UploadFile = File(...)):
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
        lyrics_font_size = None if raw_font_size in (None, "", "default") else float(raw_font_size)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="lyrics_font_size는 숫자여야 합니다.")

    with tempfile.TemporaryDirectory() as tmp:
        template_path = os.path.join(tmp, "template.pptx")
        output_path = os.path.join(tmp, "output.pptx")
        await _save_upload(template, template_path)

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _executor,
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
            raise HTTPException(500, detail=f"PPT 생성 실패: {e}")

        if not os.path.exists(output_path):
            raise HTTPException(500, detail="PPTX 출력 파일을 찾을 수 없습니다.")

        with open(output_path, "rb") as f:
            pptx_data = f.read()

    logger.info(
        "[generate-ppt] 완료 method=python-pptx songs=%d skipped=%d",
        result["appended_count"],
        len(result.get("skipped_titles", [])),
    )
    try:
        saved_week = _save_weekly_repertoire_snapshot(
            sequence_entries=sequence_entries,
            lyrics_by_title=lyrics_by_title,
            max_lines_per_slide=max_lines_per_slide,
            max_chars_per_line=max_chars_per_line,
            lyrics_font_size=lyrics_font_size,
        )
        logger.info("[history] 주간 이력 저장 완료 week_end=%s", saved_week)
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


@app.post("/songlist-card", response_class=Response)
async def songlist_card(payload: str = Form(...), template: UploadFile = File(...)):
    """송리스트 템플릿과 곡 제목 목록을 받아 PNG 카드를 생성해 반환합니다."""
    if not (template.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 템플릿만 허용됩니다.")

    data = _load_payload(payload)
    song_titles = data.get("song_titles")
    if not isinstance(song_titles, list):
        raise HTTPException(400, detail="song_titles는 list여야 합니다.")
    song_titles = [str(title).strip() for title in song_titles if str(title).strip()]
    if not song_titles:
        raise HTTPException(400, detail="song_titles가 비어 있습니다.")

    template_path = _server_songlist_template_path()
    async with _songlist_template_lock:
        await _save_upload_atomic(template, template_path)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "songlist_card.png")

            try:
                loop = asyncio.get_event_loop()
                week_num = await loop.run_in_executor(
                    _executor,
                    build_songlist_card_png,
                    template_path,
                    song_titles,
                    output_path,
                )
            except LocalOfficeUnavailable as e:
                raise HTTPException(503, detail=f"송리스트 카드 생성 실패(로컬 오피스 사용 불가): {e}")
            except Exception as e:
                raise HTTPException(500, detail=f"송리스트 카드 생성 실패: {e}")

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
